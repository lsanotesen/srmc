"""Agent 批量更新：文件、SHA256、下载令牌、权限可见范围、进度与统计（纯逻辑，不依赖 WebSocket 层）"""
import os
import uuid
import json
import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from models.agent_update import AgentUpdateTask, AgentUpdateTaskItem
from models.app_service import AppService
from services.data_scope_service import DataScopeService
from utils.redis_client import redis_client

UPLOAD_ROOT = os.environ.get("SRMC_UPDATE_DIR", "/tmp/srmc-updates")
DOWNLOAD_TOKEN_TTL = 24 * 3600  # 下载令牌有效期（秒）


def ensure_upload_root():
    os.makedirs(UPLOAD_ROOT, exist_ok=True)


def staging_path(file_ref: str) -> str:
    return os.path.join(UPLOAD_ROOT, f"{file_ref}.bin")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def save_upload_stream(file, file_ref: str) -> dict:
    """流式保存上传文件并计算 SHA256，避免一次性读入内存（支持 GB 级镜像）。"""
    ensure_upload_root()
    target = staging_path(file_ref)
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


def move_file_to_task(file_ref: str, task_id: str) -> str:
    """把暂存文件移动到任务目录，返回最终路径（失败则回落到暂存路径）。"""
    ensure_upload_root()
    src = staging_path(file_ref)
    if not os.path.exists(src):
        return src
    task_dir = os.path.join(UPLOAD_ROOT, "tasks", task_id)
    os.makedirs(task_dir, exist_ok=True)
    dst = os.path.join(task_dir, os.path.basename(src))
    try:
        os.rename(src, dst)
        return dst
    except OSError:
        return src


def issue_download_token(task_id: str, file_path: str, file_name: str) -> str:
    """下发一次性下载令牌，供 Agent 通过 HTTP 拉取文件。"""
    token = uuid.uuid4().hex
    payload = json.dumps({
        "task_id": task_id,
        "file_path": file_path,
        "file_name": file_name,
    })
    redis_client.set(f"update_download:{token}", payload, ex=DOWNLOAD_TOKEN_TTL)
    return token


def resolve_download_token(token: str):
    """校验下载令牌，返回 dict 或 None。"""
    raw = redis_client.get(f"update_download:{token}")
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def get_visible_agent_uuids(db: Session, user) -> list:
    """返回当前用户有数据权限的 Agent UUID 列表；None 表示不过滤（ADMIN）。"""
    if DataScopeService._is_super_admin(user):
        return None
    pids = DataScopeService.get_user_project_ids(db, user)
    if not pids:
        return []
    rows = (
        db.query(AppService.agent_uuid)
        .filter(
            AppService.project_id.in_(pids),
            AppService.agent_uuid.isnot(None),
            AppService.agent_uuid != "",
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _recompute_task_status(db: Session, task: AgentUpdateTask):
    """根据明细终态汇总任务状态与计数。"""
    items = db.query(AgentUpdateTaskItem).filter(AgentUpdateTaskItem.task_id == task.task_id).all()
    total = len(items)
    success = sum(1 for i in items if i.status == "success")
    failed = sum(1 for i in items if i.status == "failed")
    cancelled = sum(1 for i in items if i.status in ("cancelled", "skipped"))
    running = sum(1 for i in items if i.status == "running")
    waiting = sum(1 for i in items if i.status == "waiting")

    task.total_count = total
    task.success_count = success
    task.failed_count = failed
    task.cancelled_count = cancelled
    task.running_count = running
    task.waiting_count = waiting

    if running > 0 or waiting > 0:
        task.status = "running"
    elif cancelled == total:
        task.status = "cancelled"
    elif success == total:
        task.status = "success"
    elif failed == total:
        task.status = "failed"
    else:
        task.status = "partial"
    task.updated_at = datetime.now()


def update_item_progress(
    db: Session,
    task_id: str,
    agent_uuid: str,
    step: str = None,
    status: str = None,
    progress: int = None,
    error: str = None,
) -> AgentUpdateTaskItem:
    """Agent 上报进度时更新明细与任务统计。"""
    task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
    if not task:
        return None
    item = (
        db.query(AgentUpdateTaskItem)
        .filter(
            AgentUpdateTaskItem.task_id == task_id,
            AgentUpdateTaskItem.agent_uuid == agent_uuid,
        )
        .first()
    )
    if not item:
        return None

    if step is not None:
        item.current_step = step
    if progress is not None:
        item.progress = max(0, min(100, int(progress)))
    if status is not None and status in ("waiting", "running", "success", "failed", "cancelled", "skipped"):
        item.status = status
        if status == "running" and item.started_at is None:
            item.started_at = datetime.now()
        if status in ("success", "failed", "cancelled", "skipped"):
            item.finished_at = datetime.now()
    if error is not None:
        item.error_message = (error or "")[:2000]

    _recompute_task_status(db, task)
    db.commit()
    return item