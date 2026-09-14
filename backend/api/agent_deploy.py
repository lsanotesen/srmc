"""Agent 批量装机 API：安装包管理 + SSH 推送装机任务"""
import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from models.agent_deploy import AgentPackage, AgentDeployTask, AgentDeployTaskItem
from schemas.common import ResponseModel
from api.dependencies import require_permission
from services.audit_service import log_audit
from utils.crypto import encrypt
import services.agent_deploy_service as ads

router = APIRouter()

_run_semaphore = asyncio.Semaphore(3)  # SSH 装机并发（大文件传输，不宜过高）
_running_tasks: dict = {}

MAX_HOSTS_PER_TASK = 100


# ==================== 安装包管理 ====================

@router.post("/packages")
async def upload_package(
    file: UploadFile = File(...),
    package_type: str = Form(...),
    version: str = Form(...),
    name: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """上传 Agent 安装包（Docker 镜像 tar 或二进制可执行文件）。"""
    if package_type not in ("docker", "binary"):
        raise HTTPException(status_code=400, detail="package_type 必须为 docker 或 binary")
    if not version.strip():
        raise HTTPException(status_code=400, detail="版本号不能为空")
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    package_id = uuid.uuid4().hex
    meta = await ads.save_package_stream(file, package_id)

    pkg = AgentPackage(
        package_id=package_id,
        name=(name or file.filename)[:128],
        package_type=package_type,
        version=version.strip(),
        file_name=file.filename,
        file_path=meta["file_path"],
        file_size=meta["file_size"],
        file_sha256=meta["file_sha256"],
        description=(description or "")[:500],
        created_by=user.username,
        created_at=datetime.now(),
    )
    db.add(pkg)
    db.commit()

    log_audit(db, user.id, user.username, "AGENT_PACKAGE_UPLOAD",
              result="success",
              output=f"上传Agent安装包 type={package_type} version={version} size={meta['file_size']}")
    return ResponseModel(data=_serialize_package(pkg), message="安装包上传成功")


@router.get("/packages")
async def list_packages(
    package_type: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    q = db.query(AgentPackage)
    if package_type in ("docker", "binary"):
        q = q.filter(AgentPackage.package_type == package_type)
    pkgs = q.order_by(AgentPackage.created_at.desc()).all()
    return ResponseModel(data=[_serialize_package(p) for p in pkgs])


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    pkg = db.query(AgentPackage).filter(AgentPackage.package_id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="安装包不存在")
    db.delete(pkg)
    db.commit()
    ads.delete_package_files(package_id)
    log_audit(db, user.id, user.username, "AGENT_PACKAGE_DELETE",
              result="success", output=f"删除Agent安装包 {package_id} version={pkg.version}")
    return ResponseModel(message="安装包已删除")


# ==================== 装机任务 ====================

@router.post("/tasks")
async def create_deploy_task(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """创建批量装机任务，逐台通过 SSH 推送安装。"""
    package_id = payload.get("package_id")
    hosts = payload.get("hosts", [])
    deploy_dir = (payload.get("deploy_dir") or "/etc/srmc-agent").strip()
    server_url = (payload.get("server_url") or "").strip()

    if not package_id:
        raise HTTPException(status_code=400, detail="缺少安装包 package_id")
    if not server_url:
        raise HTTPException(status_code=400, detail="缺少后端 WebSocket 地址 server_url")
    if not server_url.startswith(("ws://", "wss://")):
        raise HTTPException(status_code=400, detail="server_url 必须以 ws:// 或 wss:// 开头")
    if not deploy_dir:
        raise HTTPException(status_code=400, detail="部署目录不能为空")
    if not hosts or not isinstance(hosts, list):
        raise HTTPException(status_code=400, detail="未配置目标主机")
    if len(hosts) > MAX_HOSTS_PER_TASK:
        raise HTTPException(status_code=400, detail=f"单次装机主机数不能超过 {MAX_HOSTS_PER_TASK}")

    pkg = db.query(AgentPackage).filter(AgentPackage.package_id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="安装包不存在")

    # 校验 + 去重（同 IP:端口 只保留第一条）
    seen = set()
    norm_hosts = []
    for h in hosts:
        ip = (h.get("ip") or "").strip()
        port = int(h.get("port") or 22)
        username = (h.get("username") or "root").strip()
        password = h.get("password") or ""
        if not ip:
            raise HTTPException(status_code=400, detail="存在空的主机 IP")
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=400, detail=f"主机 {ip} 端口非法: {port}")
        if not username or not password:
            raise HTTPException(status_code=400, detail=f"主机 {ip} 缺少 SSH 用户名或密码")
        key = (ip, port)
        if key in seen:
            continue
        seen.add(key)
        norm_hosts.append({
            "ip": ip, "port": port, "username": username, "password": password,
            "agent_name": (h.get("agent_name") or "").strip()[:128],
            # Agent IP 默认 = SSH 连接 IP，避免留空后 Agent 自动探测在多网卡机器上选错网卡
            "agent_ip": (h.get("agent_ip") or "").strip()[:45] or ip,
        })

    task_id = uuid.uuid4().hex
    task = AgentDeployTask(
        task_id=task_id,
        package_id=package_id,
        package_type=pkg.package_type,
        version=pkg.version,
        deploy_dir=deploy_dir,
        server_url=server_url,
        compose_file_content=(payload.get("compose_file") or "").strip() or None,
        config_file_content=(payload.get("config_file") or "").strip() or None,
        total_count=len(norm_hosts),
        waiting_count=len(norm_hosts),
        status="waiting",
        created_by=user.username,
        organization_id=user.organization_id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(task)

    for h in norm_hosts:
        db.add(AgentDeployTaskItem(
            task_id=task_id,
            host=h["ip"],
            port=h["port"],
            ssh_username=h["username"],
            ssh_password=encrypt(h["password"]),
            agent_name=h["agent_name"],
            agent_ip=h["agent_ip"],
            status="waiting",
            progress=0,
            created_at=datetime.now(),
        ))
    db.commit()

    log_audit(db, user.id, user.username, "AGENT_DEPLOY",
              result="success",
              output=f"创建批量装机任务 task_id={task_id} 方式={pkg.package_type} 版本={pkg.version} 主机数={len(norm_hosts)}")

    _spawn_task(task_id)
    return ResponseModel(data={"task_id": task_id}, message="装机任务已创建")


def _spawn_task(task_id: str):
    t = asyncio.create_task(_run_deploy_task(task_id))
    _running_tasks[task_id] = t
    t.add_done_callback(lambda _t: _running_tasks.pop(task_id, None))


async def _run_deploy_task(task_id: str):
    """并发调度：信号量限流，逐台在线程中执行阻塞 SSH 装机。"""
    db = SessionLocal()
    try:
        task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
        if not task:
            return
        task.status = "running"
        task.updated_at = datetime.now()
        db.commit()

        items = (
            db.query(AgentDeployTaskItem)
            .filter(AgentDeployTaskItem.task_id == task_id)
            .order_by(AgentDeployTaskItem.id)
            .all()
        )
        item_ids = [i.id for i in items]
    finally:
        db.close()

    async def run_one(item_id: int):
        async with _run_semaphore:
            # 取消检测
            chk = SessionLocal()
            try:
                t = chk.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
                if t and t.status == "cancelled":
                    it = chk.query(AgentDeployTaskItem).filter(AgentDeployTaskItem.id == item_id).first()
                    if it and it.status == "waiting":
                        ads.update_item_progress(chk, task_id, item_id, step="任务已取消", status="cancelled")
                    return
            finally:
                chk.close()
            await asyncio.to_thread(ads.deploy_host, task_id, item_id)

    await asyncio.gather(*[run_one(iid) for iid in item_ids])


@router.get("/tasks")
async def list_deploy_tasks(
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    tasks = db.query(AgentDeployTask).order_by(AgentDeployTask.created_at.desc()).all()
    return ResponseModel(data=[_serialize_task(t) for t in tasks])


@router.get("/tasks/{task_id}")
async def get_deploy_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    items = (
        db.query(AgentDeployTaskItem)
        .filter(AgentDeployTaskItem.task_id == task_id)
        .order_by(AgentDeployTaskItem.id)
        .all()
    )
    data = _serialize_task(task)
    data["items"] = [_serialize_item(i) for i in items]
    return ResponseModel(data=data)


@router.post("/tasks/{task_id}/cancel")
async def cancel_deploy_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("success", "failed", "partial", "cancelled"):
        raise HTTPException(status_code=400, detail="任务已结束，无法取消")

    task.status = "cancelled"
    task.updated_at = datetime.now()
    for item in (
        db.query(AgentDeployTaskItem)
        .filter(AgentDeployTaskItem.task_id == task_id)
        .all()
    ):
        if item.status in ("waiting",):
            item.status = "cancelled"
            item.finished_at = datetime.now()
            item.current_step = "任务已取消"
    db.commit()

    log_audit(db, user.id, user.username, "AGENT_DEPLOY_CANCEL",
              result="success", output=f"取消批量装机任务 task_id={task_id}")
    return ResponseModel(message="任务已取消，进行中的主机将在完成当前步骤后停止")


@router.post("/tasks/{task_id}/retry")
async def retry_deploy_task(
    task_id: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """重试失败/跳过的主机。仅重新执行 status=failed/skipped/cancelled 的 item，已成功的不动。
    可选 payload: {"ssh_password": "xxx"} —— 旧任务密码可能已被清除，重试时重新填写。
    """
    task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("running",):
        raise HTTPException(status_code=400, detail="任务正在执行中，无法重试")
    if task.status == "waiting":
        raise HTTPException(status_code=400, detail="任务尚未开始，无需重试")

    ssh_password = (payload or {}).get("ssh_password") or ""

    retry_count = 0
    missing_pwd = 0
    items = (
        db.query(AgentDeployTaskItem)
        .filter(AgentDeployTaskItem.task_id == task_id)
        .all()
    )
    retry_items = [i for i in items if i.status in ("failed", "skipped", "cancelled")]
    for item in retry_items:
        # 旧记录密码可能已被清除：优先用本次提交的密码，否则报错
        if not item.ssh_password and not ssh_password:
            missing_pwd += 1
            continue
        if ssh_password:
            item.ssh_password = encrypt(ssh_password)
        item.status = "waiting"
        item.progress = 0
        item.current_step = ""
        item.error_message = ""
        item.started_at = None
        item.finished_at = None
        retry_count += 1

    if missing_pwd and not ssh_password:
        raise HTTPException(
            status_code=400,
            detail=f"有 {missing_pwd} 台主机的 SSH 密码已被清除，请重新输入密码后重试",
        )
    if retry_count == 0:
        raise HTTPException(status_code=400, detail="没有可重试的主机（全部成功）")

    # 重新计算计数
    task.total_count = len(items)
    task.success_count = sum(1 for i in items if i.status == "success")
    task.failed_count = 0
    task.running_count = 0
    task.waiting_count = sum(1 for i in items if i.status == "waiting")
    task.cancelled_count = 0
    task.status = "waiting"
    task.updated_at = datetime.now()
    db.commit()

    _spawn_task(task_id)

    log_audit(db, user.id, user.username, "AGENT_DEPLOY",
              result="success", output=f"重试批量装机任务 task_id={task_id} 重试主机数={retry_count}")
    return ResponseModel(message=f"已提交 {retry_count} 台失败主机的重试任务")


@router.post("/tasks/batch-delete")
async def batch_delete_deploy_tasks(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """批量删除装机任务（连同主机明细一起删）。执行中的任务需先取消。"""
    task_ids = payload.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        raise HTTPException(status_code=400, detail="未选择要删除的任务")

    tasks = (
        db.query(AgentDeployTask)
        .filter(AgentDeployTask.task_id.in_(task_ids))
        .all()
    )
    running = [t.task_id for t in tasks if t.status in ("waiting", "running")]
    if running:
        raise HTTPException(
            status_code=400,
            detail=f"有 {len(running)} 个任务正在执行，请先取消再删除",
        )

    deleted = 0
    for t in tasks:
        db.query(AgentDeployTaskItem).filter(
            AgentDeployTaskItem.task_id == t.task_id
        ).delete(synchronize_session=False)
        db.delete(t)
        deleted += 1
    db.commit()

    log_audit(db, user.id, user.username, "DELETE",
              result="success", output=f"删除批量装机任务 {deleted} 个")
    return ResponseModel(message=f"已删除 {deleted} 个装机任务")


@router.delete("/tasks/{task_id}")
async def delete_deploy_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """删除单个装机任务（连同主机明细一起删）。执行中的任务需先取消。"""
    task = db.query(AgentDeployTask).filter(AgentDeployTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("waiting", "running"):
        raise HTTPException(status_code=400, detail="任务正在执行，请先取消再删除")

    db.query(AgentDeployTaskItem).filter(
        AgentDeployTaskItem.task_id == task_id
    ).delete(synchronize_session=False)
    db.delete(task)
    db.commit()

    log_audit(db, user.id, user.username, "DELETE",
              result="success", output=f"删除批量装机任务 task_id={task_id}")
    return ResponseModel(message="任务已删除")


# ==================== 序列化 ====================

def _serialize_package(p: AgentPackage) -> dict:
    return {
        "package_id": p.package_id,
        "name": p.name,
        "package_type": p.package_type,
        "version": p.version,
        "file_name": p.file_name,
        "file_size": p.file_size,
        "file_sha256": p.file_sha256,
        "description": p.description,
        "created_by": p.created_by,
        "created_at": p.created_at,
    }


def _serialize_task(t: AgentDeployTask) -> dict:
    return {
        "task_id": t.task_id,
        "package_id": t.package_id,
        "package_type": t.package_type,
        "version": t.version,
        "deploy_dir": t.deploy_dir,
        "server_url": t.server_url,
        "total_count": t.total_count,
        "success_count": t.success_count,
        "failed_count": t.failed_count,
        "running_count": t.running_count,
        "waiting_count": t.waiting_count,
        "cancelled_count": t.cancelled_count,
        "status": t.status,
        "created_by": t.created_by,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _serialize_item(i: AgentDeployTaskItem) -> dict:
    return {
        "id": i.id,
        "task_id": i.task_id,
        "host": i.host,
        "port": i.port,
        "ssh_username": i.ssh_username,
        "agent_name": i.agent_name,
        "agent_ip": i.agent_ip,
        "agent_uuid": i.agent_uuid,
        "hostname": i.hostname,
        "status": i.status,
        "current_step": i.current_step,
        "progress": i.progress,
        "error_message": i.error_message,
        "started_at": i.started_at,
        "finished_at": i.finished_at,
        "created_at": i.created_at,
    }
