from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from utils.ssh_pool import ssh_pool
from models.app_service import AppService
from utils.crypto import decrypt
from core.database import get_db
import os
import tempfile

router = APIRouter()

def resolve_path(path: str, username: str) -> str:
    """解析路径中的波浪号，~ 代表用户主目录"""
    if path.startswith('~'):
        return path.replace('~', '/home/' + username)
    return path

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

async def sftp_makedirs(sftp, remote_dir):
    """递归创建远程目录"""
    dirs = remote_dir.strip('/').split('/')
    current_dir = ''
    for dir_name in dirs:
        if dir_name:
            current_dir += '/' + dir_name
            try:
                sftp.stat(current_dir)
            except FileNotFoundError:
                sftp.mkdir(current_dir)

@router.post("/upload")
async def upload_file(service_id: int, remote_path: str, preserve_path: str = 'false', file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传文件到远程服务器"""
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 解析波浪号路径
    remote_path = resolve_path(remote_path, service.username)
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(await file.read())
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
        
        sftp = await conn.open_sftp()
        if not sftp:
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail="无法打开SFTP连接")
        
        try:
            # 如果需要保持路径结构，先创建目录
            if preserve_path.lower() == 'true':
                await sftp_makedirs(sftp, remote_path)
            
            # 构建完整的远程路径
            full_remote_path = os.path.join(remote_path, file.filename)
            
            sftp.put(tmp_path, full_remote_path)
            conn.last_used = datetime.now()
        finally:
            sftp.close()
        
        # 清理临时文件
        os.unlink(tmp_path)
        
        return {"code": 0, "message": "上传成功", "data": {"remote_path": full_remote_path}}
    except HTTPException:
        raise
    except Exception as e:
        if 'tmp_path' in locals():
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
