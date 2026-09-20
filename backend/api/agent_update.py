"""Agent 批量更新 API：文件上传、任务创建/查询/取消、Agent 拉取文件"""
import asyncio
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from core.config import settings
from models.agent import Agent
from models.agent_update import AgentUpdateTask, AgentUpdateTaskItem, AgentUpdatePackage
from schemas.common import ResponseModel
from api.dependencies import require_permission
from api.agent import manager
from services.audit_service import log_audit
from utils.version import normalize_version
import services.agent_update_service as aus

router = APIRouter()

_run_semaphore = asyncio.Semaphore(settings.BATCH_MAX_WORKERS)
_running_tasks: dict = {}


# ==================== 更新包管理 ====================

@router.post("/packages")
async def upload_update_package(
    file: UploadFile = File(...),
    update_type: str = Form(...),
    version: str = Form(""),
    name: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """上传 Agent 更新包（Docker 镜像 tar / 二进制文件），持久保留可复用。"""
    if update_type not in ("docker", "binary"):
        raise HTTPException(status_code=400, detail="update_type 必须为 docker 或 binary")
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    package_id = uuid.uuid4().hex
    meta = await aus.save_package_stream(file, package_id)

    pkg = AgentUpdatePackage(
        package_id=package_id,
        name=(name or file.filename)[:128],
        update_type=update_type,
        version=normalize_version(version) if version.strip() else None,
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

    log_audit(db, user.id, user.username, "AGENT_UPDATE_PACKAGE_UPLOAD",
              result="success",
              output=f"上传Agent更新包 type={update_type} version={version} size={meta['file_size']}")
    return ResponseModel(data=_serialize_package(pkg), message="更新包上传成功")


@router.get("/packages")
async def list_update_packages(
    update_type: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    q = db.query(AgentUpdatePackage)
    if update_type in ("docker", "binary"):
        q = q.filter(AgentUpdatePackage.update_type == update_type)
    pkgs = q.order_by(AgentUpdatePackage.created_at.desc()).all()
    return ResponseModel(data=[_serialize_package(p) for p in pkgs])


@router.delete("/packages/{package_id}")
async def delete_update_package(
    package_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    pkg = db.query(AgentUpdatePackage).filter(AgentUpdatePackage.package_id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="更新包不存在")
    db.delete(pkg)
    db.commit()
    aus.delete_package_files(package_id)
    log_audit(db, user.id, user.username, "AGENT_UPDATE_PACKAGE_DELETE",
              result="success", output=f"删除Agent更新包 {package_id} version={pkg.version}")
    return ResponseModel(message="更新包已删除")


# ==================== 任务管理 ====================

@router.post("/tasks")
async def create_update_task(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """创建批量更新任务并启动后台执行。复用已上传的更新包（package_id）。"""
    package_id = payload.get("package_id")
    update_type = payload.get("update_type")
    agent_uuids = payload.get("agent_uuids", [])

    if not package_id:
        raise HTTPException(status_code=400, detail="缺少更新包 package_id")
    if update_type not in ("docker", "binary"):
        raise HTTPException(status_code=400, detail="update_type 必须为 docker 或 binary")
    if not agent_uuids:
        raise HTTPException(status_code=400, detail="未选择目标 Agent")

    pkg = db.query(AgentUpdatePackage).filter(
        AgentUpdatePackage.package_id == package_id
    ).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="更新包不存在")
    if pkg.update_type != update_type:
        raise HTTPException(status_code=400, detail="更新包类型与所选更新类型不一致")

    staging = pkg.file_path
    file_name = pkg.file_name
    file_size = pkg.file_size
    file_sha256 = pkg.file_sha256

    if not os.path.exists(staging):
        raise HTTPException(status_code=404, detail="更新包文件已丢失，请重新上传")

    # 权限：校验目标 Agent 均在当前用户可见范围内
    visible = aus.get_visible_agent_uuids(db, user)
    agent_uuids = list(dict.fromkeys(agent_uuids))  # 去重保持顺序
    if visible is not None:
        visible_set = set(visible)
        not_allowed = [u for u in agent_uuids if u not in visible_set]
        if not_allowed:
            raise HTTPException(status_code=403, detail="包含无权限访问的 Agent")

    agents = db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all()
    agent_map = {a.uuid: a for a in agents}
    if not agents:
        raise HTTPException(status_code=400, detail="所选 Agent 不存在")

    task_id = uuid.uuid4().hex
    # 直接引用更新包内文件，不移动（包需长期保留供后续复用）
    file_path = staging

    task = AgentUpdateTask(
        task_id=task_id,
        update_type=update_type,
        file_name=file_name,
        file_path=file_path,
        file_size=file_size,
        file_sha256=file_sha256,
        # 版本以更新包为准，避免前端传参与包记录不一致
        version=pkg.version or normalize_version(payload.get("version")),
        image_name=payload.get("image_name") or "",
        image_tag=payload.get("image_tag") or "",
        container_name=payload.get("container_name") or "",
        binary_target_path=payload.get("binary_target_path") or "",
        binary_service_name=payload.get("binary_service_name") or "",
        backup_before_update=1 if payload.get("backup_before_update", True) else 0,
        auto_stop_old=1 if payload.get("auto_stop_old", True) else 0,
        auto_start_after=1 if payload.get("auto_start_after", True) else 0,
        compose_file_content=(payload.get("compose_file") or "").strip() or None,
        config_file_content=(payload.get("config_file") or "").strip() or None,
        service_file_content=(payload.get("service_file") or "").strip() or None,
        total_count=len(agent_uuids),
        status="waiting",
        created_by=user.username,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(task)

    for u in agent_uuids:
        a = agent_map.get(u)
        db.add(AgentUpdateTaskItem(
            task_id=task_id,
            agent_uuid=u,
            hostname=a.hostname if a else "",
            ip=a.ip if a else "",
            status="waiting",
            progress=0,
            created_at=datetime.now(),
        ))
    db.commit()

    log_audit(db, user.id, user.username, "AGENT_UPDATE",
              result="success",
              output=f"创建批量更新任务 task_id={task_id}, 类型={update_type}, 目标Agent数={len(agent_uuids)}")

    # 启动后台执行器
    _spawn_task(task_id)

    return ResponseModel(data={"task_id": task_id}, message="任务已创建")


def _spawn_task(task_id: str):
    t = asyncio.create_task(_run_update_task(task_id))
    _running_tasks[task_id] = t
    t.add_done_callback(lambda _t: _running_tasks.pop(task_id, None))


async def _run_update_task(task_id: str):
    async with _run_semaphore:
        db = SessionLocal()
        try:
            task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
            if not task:
                return
            task.status = "running"
            task.updated_at = datetime.now()
            db.commit()

            token = aus.issue_download_token(task_id, task.file_path, task.file_name)

            items = (
                db.query(AgentUpdateTaskItem)
                .filter(AgentUpdateTaskItem.task_id == task_id)
                .order_by(AgentUpdateTaskItem.id)
                .all()
            )

            for idx, item in enumerate(items):
                # 每次循环开始结束当前事务，读取最新任务状态（取消检测）与 Agent 在线状态
                db.rollback()
                task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
                if task and task.status == "cancelled":
                    # 任务已取消：把本台及后续所有未开始的明细标记取消，并终止整个循环
                    for rest in items[idx:]:
                        if rest.status in ("waiting", "running"):
                            aus.update_item_progress(db, task_id, rest.agent_uuid,
                                                     step="任务已取消", status="cancelled")
                    break

                agent = db.query(Agent).filter(Agent.uuid == item.agent_uuid).first()
                if not agent or not manager.is_online(agent.uuid, agent.last_heartbeat):
                    aus.update_item_progress(db, task_id, item.agent_uuid,
                                             step="Agent 离线", status="failed",
                                             error="Agent 不在线，无法下发更新指令")
                    continue

                aus.update_item_progress(db, task_id, item.agent_uuid,
                                         step="下发更新指令", status="running", progress=1)

                msg = _build_update_message(task, token, agent)
                sent = await manager.send_message(item.agent_uuid, msg)
                if not sent:
                    aus.update_item_progress(db, task_id, item.agent_uuid,
                                             step="下发失败", status="failed",
                                             error="Agent 连接不可用")
                    continue

                await _wait_item_terminal(db, task_id, item.agent_uuid, timeout=1800)
        finally:
            db.close()


def _build_update_message(task: AgentUpdateTask, token: str, agent: Agent) -> dict:
    """构建按 Agent 个性化的更新指令：compose_file / binary_path / service_name 优先用 Agent 自报值。"""
    data = {
        "task_id": task.task_id,
        "update_type": task.update_type,
        "download_token": token,
        "file_sha256": task.file_sha256,
        "file_name": task.file_name,
        "version": task.version,
    }
    if task.update_type == "docker":
        data["image_name"] = task.image_name
        data["image_tag"] = task.image_tag
        data["container_name"] = task.container_name
        data["compose_file"] = agent.compose_file or ""
    else:
        data["binary_target_path"] = task.binary_target_path or agent.binary_path or ""
        data["binary_service_name"] = task.binary_service_name or agent.service_name or "srmc-agent"
        data["backup_before_update"] = bool(task.backup_before_update)
        data["auto_stop_old"] = bool(task.auto_stop_old)
        data["auto_start_after"] = bool(task.auto_start_after)

    # 可选同步配置文件（前端批量更新弹窗上传的 yml）
    if task.compose_file_content:
        data["compose_file_content"] = task.compose_file_content
    if task.config_file_content:
        data["config_file_content"] = task.config_file_content
    if task.service_file_content:
        data["service_file_content"] = task.service_file_content

    return {
        "type": "update",
        "request_id": uuid.uuid4().hex,
        "timestamp": datetime.now().timestamp(),
        "data": data,
    }


async def _wait_item_terminal(db: Session, task_id: str, agent_uuid: str, timeout: int = 1800):
    """轮询明细状态直到终态或超时。

    两层判定：
    1. Agent 主动上报 update_progress status=success → 判成功
    2. Agent 重连 + agent_version == task.version → 判成功（兜底，解决自杀悖论）
    """
    import asyncio as _asyncio
    from api.agent import manager as agent_manager
    elapsed = 0
    terminal = ("success", "failed", "cancelled", "skipped")
    while elapsed < timeout:
        await _asyncio.sleep(2)
        elapsed += 2
        db.rollback()
        item = (
            db.query(AgentUpdateTaskItem)
            .filter(
                AgentUpdateTaskItem.task_id == task_id,
                AgentUpdateTaskItem.agent_uuid == agent_uuid,
            )
            .first()
        )
        if item and item.status in terminal:
            return

        # 兜底判定：Agent 重连 + 版本号 == 目标版本 → 判成功
        if item and item.status == "running":
            db2 = SessionLocal()
            try:
                task = db2.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
                agent = db2.query(Agent).filter(Agent.uuid == agent_uuid).first()
                if task and agent and task.version and agent.agent_version:
                    if normalize_version(task.version) == normalize_version(agent.agent_version) and agent_manager.is_online(agent_uuid, agent.last_heartbeat):
                        aus.update_item_progress(db2, task_id, agent_uuid,
                                                 step="重连+版本匹配", status="success", progress=100,
                                                 error="Agent 重连后版本号与目标版本一致，判更新成功")
                        db2.commit()
                        return
            finally:
                db2.close()

    aus.update_item_progress(db, task_id, agent_uuid,
                             step="执行超时", status="failed", error="更新执行超时")


@router.get("/tasks")
async def list_update_tasks(
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """任务列表（按用户可见 Agent 过滤）。"""
    visible = aus.get_visible_agent_uuids(db, user)
    tasks = db.query(AgentUpdateTask).order_by(AgentUpdateTask.created_at.desc()).all()

    result = []
    for t in tasks:
        if visible is not None:
            item_uuids = [
                i.agent_uuid for i in
                db.query(AgentUpdateTaskItem.agent_uuid)
                .filter(AgentUpdateTaskItem.task_id == t.task_id).all()
            ]
            if not any(u in visible for u in item_uuids):
                continue
        result.append(_serialize_task(t))
    return ResponseModel(data=result)


@router.get("/tasks/{task_id}")
async def get_update_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    visible = aus.get_visible_agent_uuids(db, user)
    items = (
        db.query(AgentUpdateTaskItem)
        .filter(AgentUpdateTaskItem.task_id == task_id)
        .order_by(AgentUpdateTaskItem.id)
        .all()
    )
    if visible is not None:
        items = [i for i in items if i.agent_uuid in visible]

    data = _serialize_task(task)
    data["items"] = [_serialize_item(i) for i in items]
    return ResponseModel(data=data)


@router.post("/tasks/{task_id}/cancel")
async def cancel_update_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("success", "failed", "partial", "cancelled"):
        raise HTTPException(status_code=400, detail="任务已结束，无法取消")

    task.status = "cancelled"
    task.updated_at = datetime.now()
    # 未开始/进行中的明细标记取消，已成功的保留
    for item in (
        db.query(AgentUpdateTaskItem)
        .filter(AgentUpdateTaskItem.task_id == task_id)
        .all()
    ):
        if item.status in ("waiting", "running"):
            item.status = "cancelled"
            item.finished_at = datetime.now()
            item.current_step = "任务已取消"
    db.commit()

    log_audit(db, user.id, user.username, "AGENT_UPDATE_CANCEL",
              result="success", output=f"取消批量更新任务 task_id={task_id}")
    return ResponseModel(message="任务已取消")


@router.post("/tasks/{task_id}/retry")
async def retry_update_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """重试失败/取消的 Agent 更新。"""
    task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("running",):
        raise HTTPException(status_code=400, detail="任务正在执行中，无法重试")
    if task.status == "waiting":
        raise HTTPException(status_code=400, detail="任务尚未开始，无需重试")

    retry_count = 0
    items = (
        db.query(AgentUpdateTaskItem)
        .filter(AgentUpdateTaskItem.task_id == task_id)
        .all()
    )
    for item in items:
        if item.status in ("failed", "skipped", "cancelled"):
            item.status = "waiting"
            item.progress = 0
            item.current_step = ""
            item.error_message = ""
            item.started_at = None
            item.finished_at = None
            retry_count += 1

    if retry_count == 0:
        raise HTTPException(status_code=400, detail="没有可重试的 Agent（全部成功）")

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

    log_audit(db, user.id, user.username, "AGENT_UPDATE",
              result="success", output=f"重试批量更新任务 task_id={task_id} 重试Agent数={retry_count}")
    return ResponseModel(message=f"已提交 {retry_count} 台 Agent 的重试任务")


@router.post("/tasks/batch-delete")
async def batch_delete_update_tasks(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """批量删除更新任务（连同 Agent 明细一起删）。执行中的任务需先取消。"""
    task_ids = payload.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        raise HTTPException(status_code=400, detail="未选择要删除的任务")

    tasks = (
        db.query(AgentUpdateTask)
        .filter(AgentUpdateTask.task_id.in_(task_ids))
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
        db.query(AgentUpdateTaskItem).filter(
            AgentUpdateTaskItem.task_id == t.task_id
        ).delete(synchronize_session=False)
        db.delete(t)
        deleted += 1
    db.commit()

    log_audit(db, user.id, user.username, "DELETE",
              result="success", output=f"删除批量更新任务 {deleted} 个")
    return ResponseModel(message=f"已删除 {deleted} 个更新任务")


@router.delete("/tasks/{task_id}")
async def delete_update_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """删除单个更新任务（连同 Agent 明细一起删）。执行中的任务需先取消。"""
    task = db.query(AgentUpdateTask).filter(AgentUpdateTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("waiting", "running"):
        raise HTTPException(status_code=400, detail="任务正在执行，请先取消再删除")

    db.query(AgentUpdateTaskItem).filter(
        AgentUpdateTaskItem.task_id == task_id
    ).delete(synchronize_session=False)
    db.delete(task)
    db.commit()

    log_audit(db, user.id, user.username, "DELETE",
              result="success", output=f"删除批量更新任务 task_id={task_id}")
    return ResponseModel(message="任务已删除")


# ==================== Agent 拉取文件 ====================

@router.get("/files/{token}")
async def download_update_file(token: str):
    """Agent 通过一次性令牌拉取更新文件（不依赖 JWT）。"""
    meta = aus.resolve_download_token(token)
    if not meta:
        raise HTTPException(status_code=404, detail="下载令牌无效或已过期")
    file_path = meta.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        file_path,
        filename=meta.get("file_name", os.path.basename(file_path)),
        media_type="application/octet-stream",
    )


# ==================== 序列化 ====================

def _serialize_package(p: AgentUpdatePackage) -> dict:
    return {
        "package_id": p.package_id,
        "name": p.name,
        "update_type": p.update_type,
        "version": p.version,
        "file_name": p.file_name,
        "file_size": p.file_size,
        "file_sha256": p.file_sha256,
        "description": p.description,
        "created_by": p.created_by,
        "created_at": p.created_at,
    }


def _serialize_task(t: AgentUpdateTask) -> dict:
    return {
        "task_id": t.task_id,
        "update_type": t.update_type,
        "file_name": t.file_name,
        "file_size": t.file_size,
        "file_sha256": t.file_sha256,
        "version": t.version,
        "image_name": t.image_name,
        "image_tag": t.image_tag,
        "container_name": t.container_name,
        "binary_target_path": t.binary_target_path,
        "binary_service_name": t.binary_service_name,
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


def _serialize_item(i: AgentUpdateTaskItem) -> dict:
    return {
        "id": i.id,
        "task_id": i.task_id,
        "agent_uuid": i.agent_uuid,
        "hostname": i.hostname,
        "ip": i.ip,
        "status": i.status,
        "current_step": i.current_step,
        "progress": i.progress,
        "error_message": i.error_message,
        "started_at": i.started_at,
        "finished_at": i.finished_at,
        "created_at": i.created_at,
    }