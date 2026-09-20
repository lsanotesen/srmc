"""容器/服务业务状态计算（领域层）

背景：Agent 只上报原始 Docker 状态（state / exit_code），不判断容器是常驻还是一次性。
本模块根据 run_mode + Docker 实际状态计算业务状态，供心跳处理与查询接口复用。

运行类型（run_mode）：
- permanent（常驻服务，默认）：应持续运行，exited 即异常
- oneshot（一次性任务）：跑完即退出，exited + exit_code=0 属正常"已完成"
- inactive（未启用/停止）：长期处于 exited 是预期状态，不告警、不计入异常

业务状态取值：
- RUNNING      运行中（常驻 running / 一次性 running / inactive running）
- COMPLETED    已完成（一次性 exited + exit_code=0）
- INACTIVE     未启用/已停止（inactive 的预期终态，正常）
- STOPPED      已停止（常驻 exited，或一次性 created 待执行）
- PARTIAL      部分运行（常驻容器有未满足预期，但并非全部停止）
- FAILED       异常（常驻 exited / 一次性 exit_code≠0 / restarting 异常）
- UNKNOWN      未知（无容器数据）
"""
from typing import Optional

RUN_MODE_PERMANENT = "permanent"
RUN_MODE_ONESHOT = "oneshot"
RUN_MODE_INACTIVE = "inactive"

# 服务级默认运行类型的容器名占位符。
# 物理机（HOST/PROCESS）服务没有容器概念，只能用服务级默认值；
# Compose/Docker 服务在容器级未配置时也回退到它。
SERVICE_LEVEL_KEY = "*"

# 业务状态
ST_RUNNING = "RUNNING"
ST_COMPLETED = "COMPLETED"
ST_INACTIVE = "INACTIVE"
ST_STOPPED = "STOPPED"
ST_PARTIAL = "PARTIAL"
ST_FAILED = "FAILED"
ST_UNKNOWN = "UNKNOWN"

# 视为"正常"的业务状态（不进入异常统计/告警）
HEALTHY_STATUSES = {ST_RUNNING, ST_COMPLETED, ST_INACTIVE}


def normalize_run_mode(value: Optional[str]) -> str:
    """归一化运行类型；未知/空值一律按常驻服务处理（默认值）。"""
    if value in (RUN_MODE_ONESHOT, RUN_MODE_INACTIVE):
        return value
    return RUN_MODE_PERMANENT


def resolve_run_mode(run_mode_map: dict, container_name: Optional[str]) -> str:
    """按优先级解析运行类型：容器级配置 → 服务级默认('*') → permanent。

    run_mode_map: {container_name: run_mode}，可能含 SERVICE_LEVEL_KEY。
    """
    if not run_mode_map:
        return RUN_MODE_PERMANENT
    if container_name and container_name in run_mode_map:
        return normalize_run_mode(run_mode_map.get(container_name))
    if SERVICE_LEVEL_KEY in run_mode_map:
        return normalize_run_mode(run_mode_map.get(SERVICE_LEVEL_KEY))
    return RUN_MODE_PERMANENT


def compute_container_status(container: dict, run_mode: str) -> str:
    """计算单个容器的业务状态。

    container 为 Agent 上报的原始容器信息，关键字段：
      state: running/exited/created/paused/restarting/dead
      exit_code: 退出码（-1 表示未知）
    """
    state = (container.get("state") or "").strip().lower()
    exit_code = container.get("exit_code", -1)
    try:
        exit_code = int(exit_code)
    except (TypeError, ValueError):
        exit_code = -1

    if run_mode == RUN_MODE_INACTIVE:
        # 未启用/停止：长期 exited 是预期状态，属正常，不告警、不计入异常
        if state == "running":
            return ST_RUNNING
        if state in ("exited", "dead"):
            return ST_INACTIVE
        if state == "created":
            return ST_INACTIVE  # 待启动，正常
        if state == "paused":
            return ST_INACTIVE
        if state == "restarting":
            return ST_FAILED  # 重启中按现有规范视为异常
        return ST_UNKNOWN

    if run_mode == RUN_MODE_ONESHOT:
        # 一次性任务：跑完即退出，exited+0 是正常终态
        if state == "running":
            return ST_RUNNING
        if state == "exited":
            if exit_code == 0:
                return ST_COMPLETED
            if exit_code == -1:
                # 退出码未知，无法判定成功，按异常处理（保守）
                return ST_FAILED
            return ST_FAILED
        if state == "created":
            return ST_STOPPED  # 待执行
        if state in ("restarting", "dead"):
            return ST_FAILED
        if state == "paused":
            return ST_STOPPED
        return ST_UNKNOWN

    # 常驻服务：应持续运行，exited 即异常（即使 exit_code=0）
    if state == "running":
        return ST_RUNNING
    if state == "restarting":
        return ST_FAILED
    if state in ("exited", "dead"):
        return ST_STOPPED
    if state == "paused":
        return ST_STOPPED
    if state == "created":
        return ST_STOPPED
    return ST_UNKNOWN


def compute_service_status(containers: list, run_mode_map: dict) -> str:
    """根据容器业务状态汇总出服务整体状态。

    run_mode_map: {container_name: run_mode}，缺省按 permanent 处理。

    规则：
    - 无容器 → UNKNOWN
    - 存在 FAILED → FAILED（有真正异常）
    - 全部 RUNNING → RUNNING
    - 全部 COMPLETED → COMPLETED（一次性任务全部跑完）
    - 全部 INACTIVE → INACTIVE（全部未启用）
    - RUNNING + COMPLETED + INACTIVE 组合 → RUNNING（正常，无异常）
    - 存在 STOPPED（常驻停止）→ 若还有 RUNNING 则 PARTIAL，否则 STOPPED
    - 其余组合 → PARTIAL

    注意：INACTIVE（未启用/停止）是预期状态，不参与"运行中数量不足"判断，
    也不会导致 PARTIAL/FAILED。
    """
    if not containers:
        return ST_UNKNOWN

    statuses = []
    for c in containers:
        name = c.get("name") or ""
        mode = resolve_run_mode(run_mode_map, name)
        statuses.append(compute_container_status(c, mode))

    total = len(statuses)
    running = statuses.count(ST_RUNNING)
    completed = statuses.count(ST_COMPLETED)
    inactive = statuses.count(ST_INACTIVE)
    failed = statuses.count(ST_FAILED)
    stopped = statuses.count(ST_STOPPED)

    if failed > 0:
        return ST_FAILED
    if running == total:
        return ST_RUNNING
    if completed == total:
        return ST_COMPLETED
    if inactive == total:
        return ST_INACTIVE
    # 运行中 + 已完成 + 未启用 的任意组合 → 正常
    if running + completed + inactive == total:
        return ST_RUNNING
    if stopped > 0 and running > 0:
        return ST_PARTIAL
    if stopped == total:
        return ST_STOPPED
    if running > 0 or completed > 0 or inactive > 0:
        return ST_PARTIAL
    return ST_UNKNOWN


def compute_host_service_status(agent_status: str, run_mode: str) -> str:
    """计算无容器服务（物理机 HOST/PROCESS）的业务状态。

    Agent 上报的 agent_status 为 Running/Stopped/Unknown 等。
    inactive 时未运行属预期状态，返回 INACTIVE（正常，不告警）。
    """
    s = (agent_status or "").strip().lower()
    if s == "running":
        return ST_RUNNING
    if run_mode == RUN_MODE_INACTIVE:
        # 未启用/停止：未运行是预期状态
        return ST_INACTIVE
    if s in ("stopped", "exited", "dead"):
        return ST_STOPPED
    if s in ("partial", "restarting"):
        return ST_PARTIAL
    return ST_UNKNOWN


def is_healthy(status: str) -> bool:
    """业务状态是否属于"正常"（不进入异常统计/告警）。"""
    return status in HEALTHY_STATUSES
