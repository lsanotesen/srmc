from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from models.app_service import AppService
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt
from core.database import get_db
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger("shell")


async def authenticate_token(token: str, db: Session = None):
    from services.auth_service import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        return None
    return payload.get("sub")


@router.websocket("/shell/ws/{service_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    service_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    logger.info(f"WebSocket connection attempt for service_id: {service_id}")
    
    conn = None
    shell = None
    read_task = None
    heartbeat_task = None
    last_activity = asyncio.get_event_loop().time()
    
    try:
        await websocket.accept()
        logger.info("WebSocket accepted")
        
        # 并行执行认证和数据库查询，减少等待时间
        auth_task = asyncio.create_task(authenticate_token(token, db))
        db_task = asyncio.create_task(fetch_service(db, service_id))
        
        user_id, service = await asyncio.gather(auth_task, db_task)
        
        if not user_id:
            logger.warning("Invalid token")
            await websocket.send_text("[错误] 无效的认证token")
            await websocket.close(code=1008)
            return
        
        if not service:
            logger.warning(f"Service not found: {service_id}")
            await websocket.send_text("[错误] 服务不存在")
            await websocket.close(code=1008)
            return
        
        logger.info(f"Found service: {service.func_desc}, IP: {service.ip}, Port: {service.ssh_port}")
        
        password = decrypt(service.password) if service.password else None
        
        try:
            # 设置较短的SSH连接超时
            conn = await asyncio.wait_for(
                ssh_pool.get_connection(
                    service.ip, 
                    service.ssh_port, 
                    service.username, 
                    password, 
                    None
                ),
                timeout=15  # 15秒超时
            )
            
            if not conn:
                logger.error(f"Failed to establish SSH connection to {service.ip}")
                await websocket.send_text("[错误] 无法连接到服务器，请检查SSH配置")
                await websocket.close(code=1011)
                return
            
            # 请求PTY伪终端
            shell = await asyncio.wait_for(
                conn.invoke_shell(term_type='xterm', width=80, height=24),
                timeout=10  # 10秒超时
            )
            
            if not shell:
                logger.error(f"Failed to invoke shell on {service.ip}")
                await websocket.send_text("[错误] 无法打开shell会话")
                conn.close()
                await websocket.close(code=1011)
                return
            
            logger.info(f"Shell session established for service {service_id}")
            
            # 等待shell初始化
            await asyncio.sleep(0.2)
            
            # 如果有程序路径，自动cd到该目录
            if service.program_path:
                program_dir = service.program_path
                if program_dir.startswith('~'):
                    program_dir = program_dir.replace('~', '$HOME')
                shell.send(f'cd {program_dir}\n')
                logger.info(f"Auto cd to program path: {program_dir}")
            
            # 心跳任务
            async def heartbeat():
                nonlocal last_activity
                while True:
                    try:
                        if asyncio.get_event_loop().time() - last_activity > 300:
                            logger.warning("Connection timeout due to inactivity")
                            await websocket.send_text("[警告] 连接超时，即将断开...")
                            break
                        await asyncio.sleep(30)
                    except Exception as e:
                        logger.debug(f"Heartbeat error: {e}")
                        break
            
            heartbeat_task = asyncio.create_task(heartbeat())
            
            # 读取输出任务
            async def read_output():
                nonlocal last_activity
                while True:
                    try:
                        if shell.recv_ready():
                            data = shell.recv(8192)
                            if data:
                                try:
                                    output = data.decode('utf-8')
                                except UnicodeDecodeError:
                                    try:
                                        output = data.decode('gbk')
                                    except:
                                        output = data.decode('utf-8', errors='replace')
                                await websocket.send_text(output)
                                last_activity = asyncio.get_event_loop().time()
                        await asyncio.sleep(0.02)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error reading output: {e}")
                        break
            
            read_task = asyncio.create_task(read_output())
            
            # 主循环：接收客户端消息
            try:
                while True:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=350)
                    last_activity = asyncio.get_event_loop().time()
                    logger.debug(f"Received command: {data[:50]}...")
                    if data.strip().lower() == 'exit':
                        break
                    shell.send(data)
            except asyncio.TimeoutError:
                logger.info("WebSocket timeout")
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected by client")
            except Exception as e:
                logger.error(f"Error during WebSocket communication: {e}")
                try:
                    await websocket.send_text(f"[错误] {str(e)}")
                except:
                    pass
            finally:
                logger.info(f"Closing connection for service {service_id}")
                
        except asyncio.TimeoutError:
            logger.error(f"SSH connection timeout for service {service_id}")
            await websocket.send_text("[错误] 连接超时，请检查网络或稍后重试")
            await websocket.close(code=1011)
            return
        except Exception as ssh_error:
            logger.error(f"SSH connection error: {ssh_error}")
            await websocket.send_text(f"[错误] SSH连接失败: {str(ssh_error)[:50]}...")
            await websocket.close(code=1011)
            return
            
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket endpoint: {e}")
        try:
            await websocket.send_text(f"[错误] {str(e)[:50]}...")
        except:
            pass
    finally:
        if read_task:
            read_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if shell:
            try:
                shell.close()
            except:
                pass
        if conn:
            conn.close()
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"Connection fully closed for service {service_id}")


async def fetch_service(db: Session, service_id: int):
    """异步获取服务信息"""
    try:
        return db.query(AppService).filter(AppService.id == service_id).first()
    except Exception as e:
        logger.error(f"Database error in fetch_service: {e}")
        return None