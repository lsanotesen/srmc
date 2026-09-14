"""
数据库备份服务层
- 引擎：容器内 mysqldump（Dockerfile 已安装 default-mysql-client）
- 输出：gzip 压缩的标准 SQL dump 文件，目录挂载到宿主机 backend/backups
- 并发锁：Redis SETNX 防止手动/定时同时执行
- 恢复：恢复前自动做 pre_restore 快照，失败可回退
"""
import os
import io
import time
import gzip
import shlex
import logging
import threading
import subprocess
from datetime import datetime

from sqlalchemy import text
from apscheduler.triggers.cron import CronTrigger

from core.database import SessionLocal, engine
from core.config import settings
from models.db_backup import DbBackupConfig, DbBackupRecord

logger = logging.getLogger(__name__)

# 备份文件存放目录（docker-compose 将宿主机 backend 目录挂载到 /app）
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups'))

# 排除的表（运行时状态/日志类表不参与备份与恢复：
# - audit_logs        审计日志量大且不影响功能
# - db_backup_*       备份自身的配置/记录，恢复时被覆盖会导致状态错乱
# - import_batches*   撤销依赖的批次明细同理
EXCLUDED_TABLES = {
    'audit_logs',
    'db_backup_configs',
    'db_backup_records',
    'import_batches',
    'import_batch_operations',
}

# 定时任务名 & Redis 锁
JOB_ID = 'db_backup_scheduled'
LOCK_KEY = 'srmc:backup_lock'
LOCK_TTL = 600  # 秒

_scheduler = None


def _materialize_record(record, filepath=None):
    """将 ORM 备份记录物化为普通对象，供 Session 关闭后安全使用"""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=record.id,
        filename=record.filename,
        file_path=filepath or record.file_path,
        file_size=record.file_size,
        backup_type=record.backup_type,
        status=record.status,
        table_count=record.table_count,
        duration_ms=record.duration_ms,
    )


def _get_db_conn_params():
    """从 DATABASE_URL 解析连接参数"""
    url = engine.url
    return {
        'host': url.host or 'mysql',
        'port': str(url.port or 3306),
        'user': url.username,
        'password': url.password or '',
        'database': url.database,
    }


def _get_redis():
    try:
        from utils.cache import redis_client
        return redis_client
    except Exception:
        logger.warning("redis_client unavailable, running without lock")
        return None


def get_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


_gtid_purged_support = None


def _mysqldump_supports_gtid_purged():
    """检测 mysqldump 是否支持 --set-gtid-purged（MySQL 支持，MariaDB 不支持）"""
    global _gtid_purged_support
    if _gtid_purged_support is None:
        try:
            out = subprocess.run(
                ['mysqldump', '--version'], capture_output=True, timeout=5)
            ver = (out.stdout + out.stderr).decode('utf-8', 'ignore')
            _gtid_purged_support = 'MariaDB' not in ver
        except Exception:
            _gtid_purged_support = False
    return _gtid_purged_support


def list_dump_tables(db):
    """查询当前库所有业务表（排除黑名单）"""
    rows = db.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = DATABASE() ORDER BY table_name"
    )).fetchall()
    tables = []
    for r in rows:
        name = r[0]
        if name.lower() in EXCLUDED_TABLES:
            continue
        tables.append(name)
    return tables


def _acquire_lock(rds):
    if not rds:
        return True
    return bool(rds.set(LOCK_KEY, '1', nx=True, ex=LOCK_TTL))


def _release_lock(rds):
    if rds:
        try:
            rds.delete(LOCK_KEY)
        except Exception:
            pass


def run_backup(backup_type='manual', created_by=None):
    """
    执行一次全量逻辑备份。
    返回成功创建的 DbBackupRecord；失败抛异常并落 failed 记录。
    """
    rds = _get_redis()
    if not _acquire_lock(rds):
        raise RuntimeError('已有备份任务在执行中，请稍后再试')

    db = SessionLocal()
    started = time.time()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"srmc_backup_{backup_type}_{ts}.sql.gz"
    filepath = os.path.join(get_backup_dir(), filename)

    conn = _get_db_conn_params()
    record = DbBackupRecord(
        filename=filename, file_path=filepath, file_size=0,
        backup_type=backup_type, status='running',
        created_by=created_by, created_at=datetime.now()
    )
    try:
        tables = list_dump_tables(db)
        record.table_count = len(tables)
        db.add(record)
        db.commit()

        # mysqldump 命令（显式列出表，避免 --databases 带建库语句）
        # MariaDB 版 mysqldump 不支持 --set-gtid-purged，按需追加
        cmd = [
            'mysqldump',
            '-h', conn['host'], '-P', conn['port'],
            '-u', conn['user'], f'-p{conn["password"]}',
            '--single-transaction',
            '--skip-lock-tables',
            '--no-tablespaces',
            '--skip-add-locks',
            '--skip-ssl',
        ]
        if _mysqldump_supports_gtid_purged():
            cmd.append('--set-gtid-purged=OFF')
        cmd += [
            '--hex-blob',
            '--default-character-set=utf8mb4',
            conn['database'],
        ] + tables

        proc_out = ''
        with gzip.open(filepath, 'wb', compresslevel=6) as gz:
            p = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                while True:
                    chunk = p.stdout.read(1024 * 256)
                    if not chunk:
                        break
                    gz.write(chunk)
                _, stderr = p.communicate(timeout=600)
                if p.returncode != 0:
                    err = stderr.decode('utf-8', 'ignore')[:2000]
                    # 过滤密码告警行
                    err_lines = [l for l in err.splitlines() if 'password' not in l.lower()]
                    proc_out = '\n'.join(err_lines)
                    raise RuntimeError(f'mysqldump exited {p.returncode}: {proc_out}')
            finally:
                pass

        size = os.path.getsize(filepath)
        if size <= 100:
            os.remove(filepath)
            raise RuntimeError('备份输出为空，疑似表列表为空或权限问题')

        record.status = 'success'
        record.file_size = size
        record.duration_ms = int((time.time() - started) * 1000)
        db.commit()

        cfg = db.query(DbBackupConfig).first()
        if cfg:
            cfg.last_run_at = datetime.now()
            db.commit()

        _apply_retention(cfg.retention_count if cfg else 10)
        logger.info(f"backup ok: {filename} ({size} bytes)")
        # Session 即将关闭，物化为普通对象避免 DetachedInstanceError
        return _materialize_record(record, filepath)
    except Exception as e:
        try:
            record.status = 'failed'
            record.error_message = str(e)[:1900]
            record.duration_ms = int((time.time() - started) * 1000)
            db.commit()
        except Exception:
            db.rollback()
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        logger.exception('backup failed')
        raise
    finally:
        _release_lock(rds)
        db.close()


def _apply_retention(retention_count):
    """滚动清理旧的 manual/scheduled 备份，保留最近 N 份（快照类型不受影响）"""
    if not retention_count or retention_count < 1:
        retention_count = 10
    db = SessionLocal()
    try:
        keep_ids = {r.id for r in (
            db.query(DbBackupRecord.id)
            .filter(DbBackupRecord.status == 'success')
            .filter(DbBackupRecord.backup_type.in_(['pre_import', 'pre_restore']))
            .all())}
        rows = (
            db.query(DbBackupRecord)
            .filter(DbBackupRecord.status == 'success')
            .filter(DbBackupRecord.backup_type.in_(['manual', 'scheduled']))
            .order_by(DbBackupRecord.created_at.desc())
            .all())
        overflow = [r for i, r in enumerate(rows) if i >= retention_count]
        removed = 0
        for r in overflow:
            if r.id in keep_ids:
                continue
            try:
                if os.path.exists(r.file_path):
                    os.remove(r.file_path)
            except OSError:
                pass
            db.delete(r)
            removed += 1
        if removed:
            db.commit()
    except Exception:
        db.rollback()
        logger.exception('retention cleanup failed')
    finally:
        db.close()


def _kill_idle_transactions(min_seconds=10):
    """清理长期未提交的空闲事务（Sleep 状态），
    避免 metadata lock (MDL) 阻塞恢复过程中的 DROP/CREATE TABLE"""
    killed = 0
    try:
        with engine.connect() as c:
            rows = c.execute(text(
                "SELECT t.trx_mysql_thread_id FROM information_schema.processlist p "
                "JOIN information_schema.innodb_trx t ON t.trx_mysql_thread_id = p.id "
                "WHERE p.command = 'Sleep' AND p.db = :db "
                "AND t.trx_started < NOW() - INTERVAL :sec SECOND"),
                {"db": engine.url.database, "sec": min_seconds}).fetchall()
            for (tid,) in rows:
                try:
                    c.execute(text(f'KILL {int(tid)}'))
                    killed += 1
                except Exception:
                    pass
    except Exception:
        logger.exception('[restore] kill idle transactions failed')
    return killed


class _IdleTransactionKiller:
    """恢复期间周期性清理空闲长事务的守护线程"""

    def __init__(self, min_seconds=10, interval=20):
        self._stop = threading.Event()
        self._min_seconds = min_seconds
        self._interval = interval
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.wait(self._interval):
            n = _kill_idle_transactions(self._min_seconds)
            if n:
                logger.warning(f'[restore] killed {n} idle transaction(s)')

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)


def restore_from_record(record_id, confirmed_filename):
    """
    从指定备份记录恢复整库业务表。
    安全措施：
      1. 必须精确输入待恢复文件名确认
      2. 恢复前自动 pre_restore 快照
      3. 执行失败时留下 failed 记录供排查
    """
    db = SessionLocal()
    try:
        rec = db.query(DbBackupRecord).filter(
            DbBackupRecord.id == record_id).first()
        if not rec:
            raise RuntimeError('备份记录不存在')
        if rec.status != 'success':
            raise RuntimeError('仅支持从成功的备份恢复')
        if os.path.basename(confirmed_filename or '').strip() != rec.filename:
            raise RuntimeError('确认文件名不匹配，拒绝恢复')
        if not os.path.exists(rec.file_path):
            raise RuntimeError(f'备份文件已丢失: {rec.filename}')
    finally:
        db.close()

    # 恢复前先对当前状态做一次快照兜底
    snap = run_backup(backup_type='pre_restore', created_by=confirmed_filename)
    if snap.status != 'success':
        raise RuntimeError('恢复前快照失败，为安全起见已取消恢复操作')

    conn = _get_db_conn_params()
    # 恢复期间持续清理空闲长事务（应用侧存在偶发 long idle transaction，
    # 会以 metadata lock 卡死 DROP/CREATE，见 2026-08-27 排障记录）
    killer = _IdleTransactionKiller(min_seconds=10, interval=20)
    _kill_idle_transactions(min_seconds=5)
    cmd = (
        f'gzip -dc {shlex.quote(rec.file_path)} | '
        f'mysql -h {conn["host"]} -P {conn["port"]} --skip-ssl '
        f'--init-command="SET SESSION lock_wait_timeout=60" '
        f'-u {conn["user"]} -p{shlex.quote(conn["password"])} '
        f'{conn["database"]}'
    )
    t0 = time.time()
    try:
        with killer:
            # 恢复为逐表 DROP/CREATE + 重灌数据，容器磁盘较慢时可能超过 10 分钟
            p = subprocess.run(['sh', '-c', cmd], capture_output=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise RuntimeError('恢复超时（30 分钟），请检查数据库状态后重试')
    err = (p.stderr or b'').decode('utf-8', 'ignore')
    err_clean = '\n'.join(l for l in err.splitlines() if 'password' not in l.lower())

    if p.returncode != 0:
        raise RuntimeError(f'restore failed ({p.returncode}): {err_clean[:1500]}')

    # 清理相关缓存
    try:
        from utils.cache import invalidate_projects_tree, invalidate_services_list
        invalidate_projects_tree()
        invalidate_services_list()
    except Exception:
        pass

    logger.info(f"restore done in {int((time.time()-t0)*1000)}ms from {rec.filename}")
    return {
        'restored_from': rec.filename,
        'pre_snapshot_id': snap.id,
        'duration_ms': int((time.time() - t0) * 1000),
    }


def delete_record(record_id):
    db = SessionLocal()
    try:
        rec = db.query(DbBackupRecord).filter(
            DbBackupRecord.id == record_id).first()
        if not rec:
            raise RuntimeError('记录不存在')
        if os.path.exists(rec.file_path):
            try:
                os.remove(rec.file_path)
            except OSError:
                pass
        db.delete(rec)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------- 调度

def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler


_WEEK_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def apply_schedule_from_config():
    """按配置注册/移除定时任务（启动时与配置更新时调用）"""
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(JOB_ID)
    except Exception:
        pass

    db = SessionLocal()
    try:
        cfg = db.query(DbBackupConfig).first()
        if not cfg or not cfg.enabled:
            logger.info('[backup] schedule disabled')
            return None

        t = cfg.schedule_time or datetime.strptime('02:00', '%H:%M').time()
        if cfg.schedule_type == 'weekly':
            wd = max(0, min(6, int(cfg.week_day or 1)))
            trigger = CronTrigger(hour=t.hour, minute=t.minute,
                                  day_of_week=_WEEK_DAYS[wd])
        else:
            trigger = CronTrigger(hour=t.hour, minute=t.minute)

        _scheduler.add_job(scheduled_backup_job, trigger,
                           id=JOB_ID, max_instances=1,
                           misfire_grace_time=3600)
        logger.info(f'[backup] scheduled: type={cfg.schedule_type} time={t}')
        return cfg
    finally:
        db.close()


def scheduled_backup_job():
    """定时触发入口"""
    try:
        logger.info('[backup] scheduled job start')
        rec = run_backup(backup_type='scheduled', created_by='system')
        return f"ok: {rec.filename}"
    except Exception as e:
        logger.exception('scheduled backup failed')
        raise


def ensure_default_config():
    """确保配置存在单行默认记录"""
    db = SessionLocal()
    try:
        cfg = db.query(DbBackupConfig).first()
        if not cfg:
            cfg = DbBackupConfig(
                enabled=0,
                schedule_type='daily',
                schedule_time=datetime.strptime('02:00', '%H:%M').time(),
                week_day=1,
                retention_count=10,
                updated_at=datetime.now(),
            )
            db.add(cfg)
            db.commit()
    finally:
        db.close()
