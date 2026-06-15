from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from utils.ssh_pool import ssh_pool
from models.app_service import AppService
from utils.crypto import decrypt
from core.database import get_db
import os
import tempfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def resolve_path(path: str, username: str, home_dir: str = None) -> str:
    """解析路径中的波浪号，~ 代表用户主目录"""
    if not path:
        return '/'
    
    # 如果提供了真实的主目录，使用它
    if home_dir and home_dir.startswith('/'):
        # 处理单独的波浪号
        if path == '~':
            return home_dir
        
        # 处理 ~/ 开头的路径
        if path.startswith('~/'):
            return home_dir + path[1:]
    else:
        # 回退到默认的 /home/username 路径
        # 处理单独的波浪号
        if path == '~':
            return '/home/' + username
        
        # 处理 ~/ 开头的路径
        if path.startswith('~/'):
            return '/home/' + username + path[1:]
    
    # 处理 ~username 格式（如果需要）
    if path.startswith('~') and not path.startswith('~/'):
        end_idx = path.find('/')
        if end_idx == -1:
            # ~username 形式
            other_username = path[1:]
            return '/home/' + other_username
        else:
            # ~username/path 形式
            other_username = path[1:end_idx]
            return '/home/' + other_username + path[end_idx:]
    
    return path

@router.get("/exists")
async def check_file_exists(service_id: int, path: str, db: Session = Depends(get_db)):
    """检查远程文件或目录是否存在"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    try:
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        sftp = await conn.open_sftp()
        if not sftp:
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        
        try:
            sftp.stat(path)
            exists = True
        except Exception:
            exists = False
        
        sftp.close()
        return {"code": 0, "message": "success", "data": {"exists": exists}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/listdir")
async def list_directory(service_id: int, path: str = '.', db: Session = Depends(get_db)):
    """列出远程服务器目录内容"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    try:
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        # 处理波浪号路径，~ 代表用户主目录
        if path.startswith('~'):
            path = path.replace('~', '/home/' + service.username)
        
        files, error = await conn.sftp_listdir(path)
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        return {"code": 0, "message": "success", "data": {"files": files}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def sftp_makedirs(sftp, remote_dir):
    """递归创建远程目录"""
    logger.info(f"sftp_makedirs: 开始创建目录结构: {remote_dir}")
    dirs = remote_dir.strip('/').split('/')
    logger.info(f"sftp_makedirs: 目录列表: {dirs}")
    current_dir = ''
    for dir_name in dirs:
        if dir_name:
            current_dir += '/' + dir_name
            logger.info(f"sftp_makedirs: 检查目录: {current_dir}")
            try:
                sftp.stat(current_dir)
                logger.info(f"sftp_makedirs: 目录已存在: {current_dir}")
            except Exception as e:  # paramiko 使用的是自己的异常类型
                logger.info(f"sftp_makedirs: 目录不存在，创建: {current_dir}, 异常: {str(e)}")
                sftp.mkdir(current_dir)
                logger.info(f"sftp_makedirs: 目录创建成功: {current_dir}")
    logger.info(f"sftp_makedirs: 目录结构创建完成")

@router.post("/upload")
async def upload_file(service_id: int, remote_path: str, preserve_path: str = 'false', file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传文件到远程服务器"""
    logger.info(f"========== 开始上传文件 ==========")
    logger.info(f"service_id: {service_id}")
    logger.info(f"原始remote_path: {remote_path}")
    logger.info(f"preserve_path: {preserve_path}")
    logger.info(f"filename: {file.filename}")
    logger.info(f"preserve_path type: {type(preserve_path)}")
    logger.info(f"preserve_path.lower(): {preserve_path.lower()}")
    
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        logger.error(f"服务不存在: service_id={service_id}")
        raise HTTPException(status_code=404, detail="服务不存在")
    
    tmp_path = None
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name
        logger.info(f"临时文件创建成功: {tmp_path}")
        
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            logger.error(f"无法建立SSH连接: {service.ip}:{service.ssh_port or 22}")
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        logger.info(f"SSH连接成功: {service.ip}:{service.ssh_port or 22}")
        
        # 获取用户真实的主目录
        home_dir = None
        try:
            stdin, stdout, stderr = conn.client.exec_command('echo $HOME')
            home_dir = stdout.read().decode().strip()
            logger.info(f"获取用户主目录: {home_dir}")
        except Exception as e:
            logger.warning(f"获取主目录失败，使用默认路径: {str(e)}")
        
        # 解析波浪号路径
        remote_path = resolve_path(remote_path, service.username, home_dir)
        logger.info(f"解析后路径: {remote_path}")
        
        sftp = await conn.open_sftp()
        if not sftp:
            logger.error(f"无法打开SFTP连接")
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        logger.info(f"SFTP连接成功")
        
        try:
            # 构建完整的远程路径
            full_remote_path = os.path.join(remote_path, file.filename)
            
            # 确保目标目录存在
            target_dir = os.path.dirname(full_remote_path)
            if target_dir and target_dir != '/':
                # 递归创建目录
                dirs = target_dir.strip('/').split('/')
                current_dir = ''
                for dir_name in dirs:
                    if dir_name:
                        current_dir += '/' + dir_name
                        try:
                            sftp.stat(current_dir)
                        except Exception:
                            sftp.mkdir(current_dir)
            
            sftp.put(tmp_path, full_remote_path)
            conn.last_used = datetime.now()
            logger.info(f"文件上传成功: {full_remote_path}")
        finally:
            sftp.close()
        
        # 清理临时文件
        os.unlink(tmp_path)
        
        return {"code": 0, "message": "上传成功", "data": {"remote_path": full_remote_path}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传失败: {str(e)}", exc_info=True)
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download_file(service_id: int, remote_path: str, db: Session = Depends(get_db)):
    """从远程服务器下载文件"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 解析波浪号路径
    remote_path = resolve_path(remote_path, service.username)
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.basename(remote_path)) as tmp_file:
            tmp_path = tmp_file.name
        
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        success, message = await conn.sftp_download(remote_path, tmp_path)
        
        if not success:
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail=message)
        
        return FileResponse(
            tmp_path,
            filename=os.path.basename(remote_path),
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        if 'tmp_path' in locals():
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete")
async def delete_file(service_id: int, remote_path: str, db: Session = Depends(get_db)):
    """删除远程服务器上的文件"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 解析波浪号路径
    remote_path = resolve_path(remote_path, service.username)
    
    try:
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        sftp = await conn.open_sftp()
        if not sftp:
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        
        try:
            sftp.remove(remote_path)
            return {"code": 0, "message": "删除成功"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            sftp.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rename")
async def rename_file(service_id: int, old_path: str, new_path: str, db: Session = Depends(get_db)):
    """重命名远程服务器上的文件或目录"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 解析波浪号路径
    old_path = resolve_path(old_path, service.username)
    new_path = resolve_path(new_path, service.username)
    
    try:
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        sftp = await conn.open_sftp()
        if not sftp:
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        
        try:
            sftp.rename(old_path, new_path)
            return {"code": 0, "message": "重命名成功"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            sftp.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mkdir")
async def create_directory(service_id: int, remote_path: str, db: Session = Depends(get_db)):
    """在远程服务器创建目录"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 解析波浪号路径
    remote_path = resolve_path(remote_path, service.username)
    
    try:
        conn = await ssh_pool.get_connection(
            host=service.ip,
            port=service.ssh_port or 22,
            username=service.username,
            password=decrypt(service.password)
        )
        
        if not conn:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        sftp = await conn.open_sftp()
        if not sftp:
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        
        try:
            sftp.mkdir(remote_path)
            return {"code": 0, "message": "目录创建成功"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            sftp.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
