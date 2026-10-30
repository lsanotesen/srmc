"""Agent 批量装机：安装包存储、模板渲染、SSH 推送安装（阻塞逻辑，供后台线程调用）"""
import hashlib
import os
import shlex
import time
from datetime import datetime, timedelta

import paramiko
import socket

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from core.config import settings
from core.database import SessionLocal
from models.agent import Agent
from models.agent_deploy import AgentPackage, AgentDeployTask, AgentDeployTaskItem
from models.server import Server
from utils.crypto import decrypt, encrypt
from utils.version import normalize_version

# 安装包持久化目录（默认 backend/data/agent-packages，容器内为 /app/data/...）
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_ROOT = os.environ.get("SRMC_PACKAGE_DIR", os.path.join(_BACKEND_ROOT, "data", "agent-packages"))
TEMPLATE_DIR = os.environ.get("SRMC_TEMPLATE_DIR", os.path.join(_BACKEND_ROOT, "agent_templates"))

# 服务启动后等待 Agent 注册心跳：低配机器/跨网段主机启动与首包上报较慢，
# 60s 容易误判失败，放宽到 180s；等待期间每 15s 刷新一次进度文案
REGISTER_WAIT_SECONDS = 180
REGISTER_PROGRESS_INTERVAL = 15


class TaskDeletedError(Exception):
    """任务或明细记录已被删除，后台作业应立即停止（不再写库、不再继续远程操作）。"""
    pass


# ==================== 安装包存储 ====================

def ensure_package_root():
    os.makedirs(PACKAGE_ROOT, exist_ok=True)


def package_dir(package_id: str) -> str:
    return os.path.join(PACKAGE_ROOT, package_id)


def package_file_path(package_id: str, file_name: str) -> str:
    return os.path.join(package_dir(package_id), file_name)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def save_package_stream(file, package_id: str) -> dict:
    """流式保存安装包并计算 SHA256。"""
    ensure_package_root()
    os.makedirs(package_dir(package_id), exist_ok=True)
    target = package_file_path(package_id, file.filename)
    h = hashlib.sha256()
    size = 0
    try:
        with open(target, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                size += len(chunk)
    except Exception:
        if os.path.exists(target):
            os.unlink(target)
        raise
    return {"file_path": target, "file_size": size, "file_sha256": h.hexdigest()}


def delete_package_files(package_id: str):
    d = package_dir(package_id)
    if os.path.isdir(d):
        for name in os.listdir(d):
            try:
                os.unlink(os.path.join(d, name))
            except OSError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass


# ==================== 模板渲染 ====================

def _read_template(name: str) -> str:
    with open(os.path.join(TEMPLATE_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _yaml_escape(v: str) -> str:
    """双引号 YAML 转义（防注入换行/引号）。"""
    return (v or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def render_compose(deploy_dir: str, image: str = "srmc-agent:latest") -> str:
    """渲染 docker-compose.yml。

    image 必须与 docker load 载入的镜像名一致（由 tar 包 RepoTags 决定），
    否则 compose up 会去远端拉取不存在的镜像。arm64 等不同架构的镜像名不同，
    版本 tag 也会变化，因此不能硬编码。
    """
    return _read_template("docker-compose.yml.tmpl").format(
        DEPLOY_DIR=deploy_dir, IMAGE=_yaml_escape(image)
    )


def read_image_name_from_tar(tar_path: str) -> str:
    """从 docker save 生成的 tar 包中解析镜像名（manifest.json 的 RepoTags[0]）。

    只读取 manifest.json，不解压全部层，开销很小。
    解析失败返回空串，由调用方决定兜底值。
    """
    import json
    import tarfile

    try:
        with tarfile.open(tar_path, "r") as tf:
            member = None
            for m in tf.getmembers():
                # manifest.json 在 tar 根目录
                if m.name in ("manifest.json", "./manifest.json"):
                    member = m
                    break
            if member is None:
                return ""
            f = tf.extractfile(member)
            if f is None:
                return ""
            data = json.loads(f.read().decode("utf-8"))
        if isinstance(data, list) and data:
            tags = data[0].get("RepoTags") or []
            if tags:
                return str(tags[0]).strip()
    except Exception as e:
        print(f"read_image_name_from_tar failed: {e}")
    return ""


def render_service_unit(deploy_dir: str) -> str:
    return _read_template("srmc-agent.service.tmpl").format(DEPLOY_DIR=deploy_dir)


def render_init_script(deploy_dir: str) -> str:
    """渲染 SysV init 脚本（CentOS 6 等无 systemd 的系统）。

    用 replace 而非 str.format：脚本里有 shell 函数花括号（start() { ... }），
    format 会把它们当成占位符解析并抛 KeyError。
    """
    return _read_template("srmc-agent.init.tmpl").replace("{DEPLOY_DIR}", deploy_dir)


def has_systemd(ssh) -> bool:
    """探测目标机是否有 systemd（systemctl 可用）。"""
    rc, _, _ = run_remote(ssh, "command -v systemctl >/dev/null 2>&1")
    return rc == 0


def render_config(server_url: str, agent_token: str, agent_name: str, agent_ip: str,
                  deploy_dir: str, deploy_type: str, agent_version: str) -> str:
    return _read_template("config.yaml.tmpl").format(
        SERVER_URL=_yaml_escape(server_url),
        AGENT_TOKEN=_yaml_escape(agent_token),
        AGENT_NAME=_yaml_escape(agent_name),
        AGENT_IP=_yaml_escape(agent_ip),
        DEPLOY_DIR=_yaml_escape(deploy_dir),
        DEPLOY_TYPE=_yaml_escape(deploy_type),
        AGENT_VERSION=_yaml_escape(agent_version),
    )


def merge_user_config(user_content: str, server_url: str, agent_token: str,
                      agent_name: str, agent_ip: str, deploy_dir: str,
                      deploy_type: str, agent_version: str) -> str:
    """解析用户上传的 config.yaml，注入每台机器的私有字段，再序列化返回。

    注入字段：server.url / server.token / agent.uuid(置空) / agent.name / agent.ip /
    deploy.deploy_dir / deploy.method / deploy.version
    其他字段（collector / manager / docker / systemd / deploy.backup_keep 等）保留用户上传的值。
    deploy.version 以本次装机包的版本为准，因为 Agent 上报的 agent_version 取自该字段。
    """
    import yaml
    try:
        cfg = yaml.safe_load(user_content)
        if not isinstance(cfg, dict):
            return user_content
    except Exception:
        # 解析失败，回退到模板渲染
        return render_config(server_url, agent_token, agent_name, agent_ip, deploy_dir,
                             deploy_type, agent_version)

    # 注入私有字段
    if "server" not in cfg or not isinstance(cfg["server"], dict):
        cfg["server"] = {}
    cfg["server"]["url"] = server_url
    cfg["server"]["token"] = agent_token

    if "agent" not in cfg or not isinstance(cfg["agent"], dict):
        cfg["agent"] = {}
    cfg["agent"]["uuid"] = ""           # 首次部署没有 uuid
    cfg["agent"]["name"] = agent_name
    cfg["agent"]["ip"] = agent_ip

    if "deploy" not in cfg or not isinstance(cfg["deploy"], dict):
        cfg["deploy"] = {}
    cfg["deploy"]["deploy_dir"] = deploy_dir
    if deploy_type:
        cfg["deploy"]["method"] = deploy_type
    if agent_version:
        cfg["deploy"]["version"] = agent_version

    return yaml.safe_dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ==================== 任务状态 ====================

def update_item_progress(db: Session, task_id: str, item_id: int, step=None, status=None,
                         progress=None, error=None, hostname=None, agent_uuid=None):
    """回写明细与任务进度。

    任务/明细已被删除（含并发删除导致的 StaleDataError）时抛 TaskDeletedError，
    由 deploy_host 捕获后静默终止该主机的后台作业。
    """
    try:
        task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
        if not task:
            db.rollback()
            raise TaskDeletedError(f"任务 {task_id} 已被删除")
        item = db.query(AgentDeployTaskItem).filter(AgentDeployTaskItem.id == item_id).first()
        if not item:
            db.rollback()
            raise TaskDeletedError(f"任务 {task_id} 的明细 {item_id} 已被删除")

        if step is not None:
            item.current_step = step
        if progress is not None:
            item.progress = max(0, min(100, int(progress)))
        if hostname is not None:
            item.hostname = hostname
        if agent_uuid is not None:
            item.agent_uuid = agent_uuid
        if status is not None and status in ("waiting", "running", "success", "failed", "cancelled", "skipped"):
            item.status = status
            if status == "running" and item.started_at is None:
                item.started_at = datetime.now()
            if status in ("success", "failed", "cancelled", "skipped"):
                item.finished_at = datetime.now()
        if error is not None:
            item.error_message = (error or "")[:2000]

        items = db.query(AgentDeployTaskItem).filter(AgentDeployTaskItem.task_id == task_id).all()
        total = len(items)
        task.total_count = total
        task.success_count = sum(1 for i in items if i.status == "success")
        task.failed_count = sum(1 for i in items if i.status == "failed")
        task.cancelled_count = sum(1 for i in items if i.status in ("cancelled", "skipped"))
        task.running_count = sum(1 for i in items if i.status == "running")
        task.waiting_count = sum(1 for i in items if i.status == "waiting")
        # 已取消的任务保持“已取消”：进行中的主机跑完后只更新计数，不再改写整体状态
        if task.status != "cancelled":
            if task.running_count > 0 or task.waiting_count > 0:
                task.status = "running"
            elif task.cancelled_count == total:
                task.status = "cancelled"
            elif task.success_count == total:
                task.status = "success"
            elif task.failed_count == total:
                task.status = "failed"
            else:
                task.status = "partial"
        task.updated_at = datetime.now()
        db.commit()
    except StaleDataError:
        # 行已被并发删除：UPDATE 未匹配到任何记录
        db.rollback()
        raise TaskDeletedError(f"任务 {task_id} 已被删除")


# ==================== SSH 装机（阻塞，在线程中执行） ====================

class Privilege:
    """目标机提权方式。

    - root：登录用户就是 root，命令直接执行
    - sudo_nopass：普通用户 + NOPASSWD sudo，命令用 `sudo -n` 执行
    - sudo_password：普通用户 + 需要密码的 sudo，用 `sudo -S` 并从 stdin 喂密码
      （密码复用 SSH 登录密码）
    """

    ROOT = "root"
    SUDO_NOPASS = "sudo_nopass"
    SUDO_PASSWORD = "sudo_password"

    def __init__(self, mode: str, password: str | None = None, login_user: str = "root"):
        self.mode = mode
        self.password = password
        self.login_user = login_user

    def is_root(self) -> bool:
        return self.mode == self.ROOT

    def wrap(self, cmd: str) -> str:
        """给整条命令（含 && 链）套上提权，避免 sudo 只作用于第一段。

        用 `sudo ... sh -c '<cmd>'` 而不是简单加前缀：`sudo a && b` 里的 b 不会提权。
        """
        if self.mode == self.ROOT:
            return cmd
        flag = "-n" if self.mode == self.SUDO_NOPASS else "-S -p ''"
        return "sudo %s sh -c %s" % (flag, shlex.quote(cmd))

    def needs_password(self) -> bool:
        return self.mode == self.SUDO_PASSWORD

    def label(self) -> str:
        if self.mode == self.ROOT:
            return "root"
        if self.mode == self.SUDO_NOPASS:
            return "%s + sudo 免密" % self.login_user
        return "%s + sudo 密码提权" % self.login_user


def detect_privilege(ssh: paramiko.SSHClient, login_user: str, password: str | None) -> Privilege:
    """判定提权方式：root 直连 → sudo 免密 → sudo 密码（复用 SSH 密码）。

    返回的 Privilege.mode 为 None 表示都不可用；异常信息通过 Privilege.error 带回。
    """
    if login_user == "root":
        return Privilege(Privilege.ROOT, login_user=login_user)

    rc, _, _ = run_remote(ssh, "sudo -n true")
    if rc == 0:
        return Privilege(Privilege.SUDO_NOPASS, login_user=login_user)

    if not password:
        priv = Privilege("", login_user=login_user)
        priv.error = ("登录用户 %s 非 root，且 sudo 未配置免密；"
                      "缺少 SSH 密码无法尝试 sudo 提权" % login_user)
        return priv

    # 用 SSH 密码验证能否提权到 root
    probe = Privilege(Privilege.SUDO_PASSWORD, password, login_user)
    rc, out, err = run_remote(ssh, "id -un", priv=probe)
    if rc == 0 and out.strip() == "root":
        return probe

    priv = Privilege("", login_user=login_user)
    priv.error = ("登录用户 %s 非 root，sudo 免密不可用，且用 SSH 密码 sudo 提权失败：%s"
                  % (login_user, (err or out or "").strip()[:200] or "密码错误或用户不在 sudoers"))
    return priv


def deploy_host(task_id: str, item_id: int):
    """单台主机装机完整流程。每个线程使用独立 DB 会话。"""
    db = SessionLocal()
    ssh = None
    try:
        item = db.query(AgentDeployTaskItem).filter(AgentDeployTaskItem.id == item_id).first()
        task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
        if not item or not task:
            return
        if item.status in ("cancelled", "skipped"):
            return

        try:
            password = decrypt(item.ssh_password) if item.ssh_password else None
        except Exception:
            password = None

        deploy_dir = task.deploy_dir or "/etc/srmc-agent"
        package = db.query(AgentPackage).filter(AgentPackage.package_id == task.package_id).first()
        if not package:
            update_item_progress(db, task_id, item_id, step="安装包不存在", status="failed",
                                 error=f"安装包 {task.package_id} 已被删除")
            _clear_password(db, item_id)
            return

        # 1. 建立 SSH 连接
        update_item_progress(db, task_id, item_id, step="SSH 连接中", status="running", progress=2)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=item.host,
                port=item.port or 22,
                username=item.ssh_username or "root",
                password=password,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
                look_for_keys=False,
                allow_agent=False,
            )
        except (paramiko.AuthenticationException,) as e:
            update_item_progress(db, task_id, item_id, step="SSH 认证失败", status="failed",
                                 error=f"SSH 认证失败：{e}")
            _clear_password(db, item_id)
            return
        except (paramiko.SSHException, socket.error, OSError) as e:
            update_item_progress(db, task_id, item_id, step="SSH 连接失败", status="failed",
                                 error=f"无法连接 {item.host}:{item.port or 22}：{e}")
            _clear_password(db, item_id)
            return

        # 主机名校验（采集真实主机名）
        rc, out, _ = run_remote(ssh, "hostname")
        real_hostname = out.strip() or item.host
        update_item_progress(db, task_id, item_id, step="SSH 连接成功", progress=5, hostname=real_hostname)

        # 校验最终 Agent IP（默认=SSH IP）是否真实存在于目标机网卡，
        # 不在则疑似 NAT/端口映射或多网卡，落一条警告（不中断装机）
        final_agent_ip = (item.agent_ip or item.host).strip()
        rc, ips_out, _ = run_remote(ssh, "hostname -I")
        local_ips = ips_out.split()
        if local_ips and final_agent_ip not in local_ips:
            sample = "、".join(local_ips[:6])
            update_item_progress(
                db, task_id, item_id,
                error=f"[警告] Agent IP {final_agent_ip} 不在目标机网卡上（检测到：{sample}），"
                      f"疑似 NAT/端口映射或多网卡，Agent 可能无法被正常监控，建议手工指定 Agent IP 后重试",
            )
        else:
            # 之前可能有残留警告，网卡校验通过则清除
            if item.error_message and item.error_message.startswith("[警告]"):
                update_item_progress(db, task_id, item_id, error="")

        # 权限判定：root 直连 → sudo 免密 → sudo 密码（复用 SSH 密码）
        rc, who, _ = run_remote(ssh, "id -un")
        login_user = who.strip() or (item.ssh_username or "root")
        priv = detect_privilege(ssh, login_user, password)
        if not priv.mode:
            update_item_progress(db, task_id, item_id, step="权限不足", status="failed",
                                 error=getattr(priv, "error", "无法获得目标机 root 权限"))
            _clear_password(db, item_id)
            return
        update_item_progress(db, task_id, item_id, step="权限校验通过（%s）" % priv.label(), progress=6)

        # SSH 认证成功：将验证通过的凭据回写到 servers 表（learn-once，按组织隔离）
        _write_back_server_credential(db, task, item, password, real_hostname)

        if task.package_type == "docker":
            _deploy_docker(db, task_id, item_id, task, item, package, deploy_dir, ssh, priv)
        else:
            _deploy_binary(db, task_id, item_id, task, item, package, deploy_dir, ssh, priv)
    except TaskDeletedError:
        # 任务/明细已被删除（多为取消后立即删除），静默收尾，不再写库
        pass
    finally:
        if ssh:
            try:
                ssh.close()
            except Exception:
                pass
        db.close()


def _deploy_docker(db, task_id, item_id, task, item, package, deploy_dir, ssh, priv):
    host = item.host
    try:
        # 2. 检查 docker
        update_item_progress(db, task_id, item_id, step="检查 Docker 环境", progress=8)
        rc, out, err = run_remote(ssh, "docker --version")
        if rc != 0:
            raise DeployError("目标机未安装 Docker，请先安装 Docker 后重试")

        # 3. 建目录：非 root 登录时把目录交给登录用户，否则后面 SFTP 无法写入
        update_item_progress(db, task_id, item_id, step="创建部署目录", progress=12)
        mk = "mkdir -p '%s'" % deploy_dir
        if not priv.is_root():
            mk += " && chown %s '%s'" % (shlex.quote(priv.login_user), deploy_dir)
        rc, out, err = run_remote(ssh, mk, priv=priv)
        if rc != 0:
            raise DeployError("创建目录失败：%s" % err.strip())

        # 4. 上传镜像 tar
        remote_tar = "%s/srmc-agent.tar" % deploy_dir
        update_item_progress(db, task_id, item_id, step="上传镜像包", progress=15)
        sftp = ssh.open_sftp()
        try:
            upload_with_progress(db, task_id, item_id, sftp, package.file_path, remote_tar, 15, 55)
            # 上传 compose / config：优先用用户自定义内容，否则渲染系统模板
            compose_yaml = (task.compose_file_content or "").strip() if task.compose_file_content else None
            if not compose_yaml:
                # 镜像名从 tar 包解析（RepoTags），保证与 docker load 载入的名字一致。
                # 不同架构（arm64）与不同版本 tag 的镜像名不同，不能硬编码。
                image_name = read_image_name_from_tar(package.file_path)
                if not image_name:
                    image_name = "srmc-agent:latest"
                    print(f"[deploy] 无法从 tar 解析镜像名，回退默认值 {image_name}: {package.file_path}")
                else:
                    print(f"[deploy] 从 tar 解析镜像名: {image_name}")
                compose_yaml = render_compose(deploy_dir, image_name)
            # config：用户上传则注入每台机器私有字段，否则渲染系统模板
            if task.config_file_content and task.config_file_content.strip():
                config_yaml = merge_user_config(
                    task.config_file_content,
                    task.server_url, settings.AGENT_TOKEN or "",
                    item.agent_name or item.hostname or "",
                    item.agent_ip or "",
                    deploy_dir, "docker",
                    normalize_version(task.version),
                )
            else:
                config_yaml = render_config(
                    task.server_url, settings.AGENT_TOKEN or "",
                    item.agent_name or item.hostname or "",
                    item.agent_ip or "",
                    deploy_dir, "docker",
                    normalize_version(task.version),
                )
            put_content(sftp, compose_yaml, "%s/docker-compose.yml" % deploy_dir)
            put_content(sftp, config_yaml, "%s/config.yaml" % deploy_dir)
        finally:
            sftp.close()

        # 5. docker load
        update_item_progress(db, task_id, item_id, step="docker load 载入镜像", progress=60)
        rc, out, err = run_remote(ssh, "docker load -i '%s'" % remote_tar, timeout=900, priv=priv)
        if rc != 0:
            raise DeployError("docker load 失败：%s %s" % (out.strip()[-500:], err.strip()[-500:]))

        # 删除 tar 节省磁盘
        run_remote(ssh, "rm -f '%s'" % remote_tar, priv=priv)

        # 6. compose down + up -d（V1/V2 自适应，down 覆盖旧容器）
        update_item_progress(db, task_id, item_id, step="启动容器（compose down）", progress=72)
        compose_cmd = _compose_cmd(ssh, deploy_dir)
        run_remote(ssh, "%s down" % compose_cmd, timeout=180, priv=priv)
        # 清理游离的同名容器：手动 docker run / 旧方式部署的 srmc-agent 不属于 compose 项目，
        # compose down 删不掉，会导致 up 时报 "container name already in use"
        run_remote(ssh, "docker rm -f srmc-agent >/dev/null 2>&1 || true", priv=priv)
        update_item_progress(db, task_id, item_id, step="启动容器（compose up -d）", progress=80)
        rc, out, err = run_remote(ssh, "%s up -d" % compose_cmd, timeout=300, priv=priv)
        if rc != 0:
            # 再次兜底：若仍有容器名冲突，强删后重试一次
            if "already in use" in (out + err):
                run_remote(ssh, "docker rm -f srmc-agent >/dev/null 2>&1 || true", priv=priv)
                rc, out, err = run_remote(ssh, "%s up -d" % compose_cmd, timeout=300, priv=priv)
            if rc != 0:
                raise DeployError("compose up 失败：%s %s" % (out.strip()[-500:], err.strip()[-500:]))

        # 7. 验证容器运行
        update_item_progress(db, task_id, item_id, step="验证容器状态", progress=88)
        if not _wait_container_running(ssh, "srmc-agent", timeout=30, priv=priv):
            raise DeployError("容器启动后未处于 running 状态，请检查目标机日志：docker logs srmc-agent")

        # 8. 等待 Agent 注册
        update_item_progress(db, task_id, item_id, step="等待 Agent 注册", progress=95)
        agent_uuid = wait_registration_with_progress(db, task_id, item_id, item.agent_ip or host)
        if not agent_uuid:
            update_item_progress(db, task_id, item_id, step="容器已启动，Agent 未在 %ds 内注册" % REGISTER_WAIT_SECONDS,
                                 status="failed", progress=100,
                                 error="容器运行正常，但 Agent 未注册，请检查网络连通性或 Token 配置")
            _clear_password(db, item_id)
            return

        update_item_progress(db, task_id, item_id, step="装机完成", status="success", progress=100,
                             agent_uuid=agent_uuid)
        _clear_password(db, item_id)
    except TaskDeletedError:
        # 任务已被删除：直接上抛交给 deploy_host 静默收尾，不再尝试写库
        raise
    except DeployError as e:
        update_item_progress(db, task_id, item_id, step="装机失败", status="failed", error=str(e))
        _clear_password(db, item_id)
    except Exception as e:
        update_item_progress(db, task_id, item_id, step="装机异常", status="failed", error=str(e))
        _clear_password(db, item_id)


def _deploy_binary(db, task_id, item_id, task, item, package, deploy_dir, ssh, priv):
    host = item.host
    try:
        # 探测 init 系统：CentOS 6 等老系统只有 SysV init，没有 systemd
        use_systemd = has_systemd(ssh)

        # 2. 建目录：非 root 登录时把目录交给登录用户，否则后面 SFTP 无法写入
        update_item_progress(db, task_id, item_id, step="创建部署目录", progress=8)
        mk = "mkdir -p '%s'" % deploy_dir
        if not priv.is_root():
            mk += " && chown %s '%s'" % (shlex.quote(priv.login_user), deploy_dir)
        rc, out, err = run_remote(ssh, mk, priv=priv)
        if rc != 0:
            raise DeployError("创建目录失败：%s" % err.strip())

        # 3. 停止旧服务（覆盖安装）
        update_item_progress(db, task_id, item_id, step="停止旧服务", progress=12)
        if use_systemd:
            run_remote(ssh, "systemctl stop srmc-agent", timeout=60, priv=priv)
        else:
            run_remote(ssh, "service srmc-agent stop", timeout=60, priv=priv)

        # 4. 上传二进制
        remote_bin = "%s/srmc-agent" % deploy_dir
        update_item_progress(db, task_id, item_id, step="上传二进制文件", progress=15)
        sftp = ssh.open_sftp()
        try:
            upload_with_progress(db, task_id, item_id, sftp, package.file_path, remote_bin + ".new", 15, 55)
            # 上传 config / service：优先用用户自定义内容，否则渲染系统模板
            if task.config_file_content and task.config_file_content.strip():
                config_yaml = merge_user_config(
                    task.config_file_content,
                    task.server_url, settings.AGENT_TOKEN or "",
                    item.agent_name or item.hostname or "",
                    item.agent_ip or "",
                    deploy_dir, "binary",
                    normalize_version(task.version),
                )
            else:
                config_yaml = render_config(
                    task.server_url, settings.AGENT_TOKEN or "",
                    item.agent_name or item.hostname or "",
                    item.agent_ip or "",
                    deploy_dir, "binary",
                    normalize_version(task.version),
                )
            put_content(sftp, config_yaml, "%s/config.yaml" % deploy_dir)
            # 服务文件：systemd 用 unit，老系统用 SysV init 脚本
            if use_systemd:
                put_content(sftp, render_service_unit(deploy_dir), "%s/srmc-agent.service" % deploy_dir)
            else:
                put_content(sftp, render_init_script(deploy_dir), "%s/srmc-agent.init" % deploy_dir)
        finally:
            sftp.close()

        # 5. 替换 + 授权（\mv 绕过可能的 mv -i 别名，避免 SSH 无 stdin 时卡住）
        update_item_progress(db, task_id, item_id, step="安装二进制", progress=60)
        rc, out, err = run_remote(
            ssh,
            "\\mv -f '%s.new' '%s' && chmod 755 '%s'" % (remote_bin, remote_bin, remote_bin),
            priv=priv,
        )
        if rc != 0:
            raise DeployError("安装二进制失败：%s" % err.strip())

        # 6. 安装服务并启动
        update_item_progress(db, task_id, item_id, step="安装系统服务", progress=72)
        if use_systemd:
            cmd = (
                "cp -f '%s/srmc-agent.service' /etc/systemd/system/ && systemctl daemon-reload "
                "&& systemctl enable srmc-agent && systemctl restart srmc-agent" % deploy_dir
            )
        else:
            # SysV：装到 /etc/init.d，chkconfig 注册开机自启，service 启动。
            # 用 \cp 绕过 CentOS 6 默认的 cp -i 别名：覆盖已存在文件时会等待交互输入，
            # 而 SSH 执行没有 stdin，会导致命令卡住或失败。
            # chkconfig 只影响开机自启，失败不应阻断启动，用 `|| true` 兜底。
            cmd = (
                "\\cp -f '%s/srmc-agent.init' /etc/init.d/srmc-agent && chmod 755 /etc/init.d/srmc-agent "
                "&& (chkconfig --add srmc-agent 2>&1 || true) "
                "&& (chkconfig srmc-agent on 2>&1 || true) "
                "&& service srmc-agent restart" % deploy_dir
            )
        rc, out, err = run_remote(ssh, cmd, timeout=120, priv=priv)
        if rc != 0:
            raise DeployError("安装/启动服务失败：%s %s" % (out.strip()[-500:], err.strip()[-500:]))

        # 7. 验证服务 active
        update_item_progress(db, task_id, item_id, step="验证服务状态", progress=88)
        if not _wait_service_active(ssh, "srmc-agent", timeout=20, use_systemd=use_systemd):
            hint = ("journalctl -u srmc-agent -n 50" if use_systemd
                    else "tail -n 50 /var/log/srmc-agent.log")
            raise DeployError("服务未正常运行，请检查目标机日志：%s" % hint)

        # 8. 等待注册
        update_item_progress(db, task_id, item_id, step="等待 Agent 注册", progress=95)
        agent_uuid = wait_registration_with_progress(db, task_id, item_id, item.agent_ip or host)
        if not agent_uuid:
            update_item_progress(db, task_id, item_id, step="服务已启动，Agent 未在 %ds 内注册" % REGISTER_WAIT_SECONDS,
                                 status="failed", progress=100,
                                 error="服务运行正常，但 Agent 未注册，请检查网络连通性或 Token 配置")
            _clear_password(db, item_id)
            return

        update_item_progress(db, task_id, item_id, step="装机完成", status="success", progress=100,
                             agent_uuid=agent_uuid)
        _clear_password(db, item_id)
    except TaskDeletedError:
        # 任务已被删除：直接上抛交给 deploy_host 静默收尾，不再尝试写库
        raise
    except DeployError as e:
        update_item_progress(db, task_id, item_id, step="装机失败", status="failed", error=str(e))
        _clear_password(db, item_id)
    except Exception as e:
        update_item_progress(db, task_id, item_id, step="装机异常", status="failed", error=str(e))
        _clear_password(db, item_id)


# ==================== SSH 辅助 ====================

class DeployError(Exception):
    pass


def run_remote(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120, priv: Privilege | None = None):
    """执行远程命令，返回 (rc, stdout, stderr)。

    priv 不为 None 时按该提权方式执行；sudo 需要密码时从 stdin 喂入。
    """
    if priv is not None:
        cmd = priv.wrap(cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    if priv is not None and priv.needs_password():
        try:
            stdin.write(priv.password + "\n")
            stdin.flush()
            stdin.channel.shutdown_write()
        except Exception:
            pass
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def _compose_cmd(ssh: paramiko.SSHClient, deploy_dir: str) -> str:
    """探测 compose V2/V1，返回带工作目录的命令前缀。"""
    rc, _, _ = run_remote(ssh, "docker compose version")
    if rc == 0:
        return "cd '%s' && docker compose" % deploy_dir
    return "cd '%s' && docker-compose -f docker-compose.yml" % deploy_dir


def _wait_container_running(ssh: paramiko.SSHClient, name: str, timeout: int = 30,
                            priv: Privilege | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rc, out, _ = run_remote(
            ssh,
            "docker ps --filter 'name=^/%s$' --filter 'status=running' --format '{{.Names}}'" % name,
            priv=priv,
        )
        if rc == 0 and name in out.split():
            return True
        time.sleep(2)
    return False


def _wait_service_active(ssh: paramiko.SSHClient, name: str, timeout: int = 20,
                         use_systemd: bool = True) -> bool:
    """等待服务进入运行状态。systemd 用 systemctl is-active，SysV 用 pgrep 兜底。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if use_systemd:
            rc, out, _ = run_remote(ssh, "systemctl is-active %s" % name)
            if rc == 0 and out.strip() == "active":
                return True
        else:
            # SysV：init 脚本的 status 退出码 0 表示运行中；再用 pgrep 兜底
            rc, out, _ = run_remote(ssh, "service %s status" % name)
            if rc == 0:
                return True
            rc2, _, _ = run_remote(ssh, "pgrep -f 'srmc-agent' >/dev/null 2>&1")
            if rc2 == 0:
                return True
        time.sleep(2)
    return False


def upload_with_progress(db, task_id, item_id, sftp, local_path, remote_path, pct_from, pct_to):
    """SFTP 上传并按区间回写进度（节流，每 5% 写一次库）。"""
    total = os.path.getsize(local_path)
    state = {"last_pct": -1, "done": 0}

    def cb(done, _total):
        state["done"] = done
        if total <= 0:
            return
        ratio = done / total
        pct = int(pct_from + (pct_to - pct_from) * ratio)
        if pct >= state["last_pct"] + 5 or pct >= pct_to:
            state["last_pct"] = pct
            update_item_progress(db, task_id, item_id, step="上传文件 %d%%" % int(ratio * 100),
                                 progress=pct)

    sftp.put(local_path, remote_path, callback=cb)


def put_content(sftp, content: str, remote_path: str):
    """将字符串内容写到远程文件。"""
    with sftp.file(remote_path, "w") as f:
        f.write(content)
    # 确保文件权限可读
    try:
        sftp.chmod(remote_path, 0o644)
    except IOError:
        pass


def wait_registration_with_progress(db: Session, task_id: str, item_id: int, agent_ip: str) -> str:
    """等待注册，期间按间隔刷新进度文案，避免长时间停在 95% 让人误以为卡死。"""
    waited = 0
    while waited < REGISTER_WAIT_SECONDS:
        chunk = min(REGISTER_PROGRESS_INTERVAL, REGISTER_WAIT_SECONDS - waited)
        agent_uuid = wait_registration(db, agent_ip, timeout=chunk)
        if agent_uuid:
            return agent_uuid
        waited += chunk
        update_item_progress(db, task_id, item_id,
                             step="等待 Agent 注册（已等待 %ds）" % waited, progress=95)
    return ""


def wait_registration(db: Session, agent_ip: str, timeout: int = REGISTER_WAIT_SECONDS) -> str:
    """等待该 IP 的 Agent 注册上线，返回 agent_uuid；超时返回空串。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        db.rollback()
        since = datetime.now() - timedelta(seconds=90)
        agent = (
            db.query(Agent)
            .filter(Agent.ip == agent_ip, Agent.last_heartbeat >= since)
            .order_by(Agent.last_heartbeat.desc())
            .first()
        )
        if agent:
            return agent.uuid
        time.sleep(3)
    return ""


def _clear_password(db: Session, item_id: int):
    """终态后清除 SSH 密码，避免长期留存。
    已改为空操作：密码用 AES 加密存储，重试需要原始密码，不清更合理。
    """
    pass


def _write_back_server_credential(db: Session, task, item, password, real_hostname: str):
    """SSH 认证且提权校验通过后，把凭据回写到 servers 表（learn-once）。

    - 支持 root 与「普通用户 + sudo」两种凭据：目标是很多机器禁 root 远程登录
    - 按组织隔离：同一组织下已存在该 IP 记录则不覆盖，避免冲掉手工维护的凭据
    - 回写失败（如并发唯一冲突）不中断装机流程
    """
    username = (item.ssh_username or "root").strip()
    if not password or not username:
        return
    org_id = getattr(task, "organization_id", None)
    try:
        existing = db.query(Server).filter(
            Server.ip == item.host,
            Server.organization_id == org_id,
        ).first()
        if existing:
            return
        db.add(Server(
            hostname=(real_hostname or item.host)[:128],
            ip=item.host,
            ssh_port=item.port or 22,
            username=username,
            password=encrypt(password),
            os_type="LINUX",
            organization_id=org_id,
        ))
        db.commit()
    except Exception:
        db.rollback()
