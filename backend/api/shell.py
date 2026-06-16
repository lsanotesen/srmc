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
        
        user_id = await authenticate_token(token, db)
        if not user_id:
            logger.warning("Invalid token")
            await websocket.send_text("[错误] 无效的认证token")
            await websocket.close(code=1008)
            return
        
        try:
            service = db.query(AppService).filter(AppService.id == service_id).first()
            if not service:
                logger.warning(f"Service not found in app_services: {service_id}")
                await websocket.send_text("[错误] 服务不存在")
                await websocket.close(code=1008)
                return
            
            logger.info(f"Found service: {service.func_desc}, IP: {service.ip}, Port: {service.ssh_port}")
            
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            await websocket.send_text(f"[错误] 数据库连接失败: {str(db_error)[:50]}...")
            await websocket.close(code=1011)
            return
        
        logger.info(f"Connecting to server: {service.ip}:{service.ssh_port}")
        
        password = decrypt(service.password) if service.password else None
        
        try:
            conn = await ssh_pool.get_connection(
                service.ip, 
                service.ssh_port, 
                service.username, 
                password, 
                None
            )
            
            if not conn:
                logger.error(f"Failed to establish SSH connection to {service.ip}")
                await websocket.send_text("[错误] 无法连接到服务器，请检查SSH配置")
                await websocket.close(code=1011)
                return
            
            # 请求PTY伪终端（关键！），没有PTY就没有命令补全、颜色等功能
            shell = await conn.invoke_shell(term_type='xterm', width=80, height=24)
            if not shell:
                logger.error(f"Failed to invoke shell on {service.ip}")
                await websocket.send_text("[错误] 无法打开shell会话")
                conn.close()
                await websocket.close(code=1011)
                return
            
            logger.info(f"Shell session established for service {service_id}")
            # 等待shell初始化完成，不需要发送换行，bash会自动显示提示符
            await asyncio.sleep(0.5)
            
            # 如果有程序路径，自动cd到该目录
            if service.program_path:
                program_dir = service.program_path
                if program_dir.startswith('~'):
                    program_dir = program_dir.replace('~', '$HOME')
                shell.send(f'cd {program_dir}\n')
                logger.info(f"Auto cd to program path: {program_dir}")
            
            # 心跳任务：定期发送心跳防止连接断开
            async def heartbeat():
                nonlocal last_activity
                while True:
                    try:
                        # 检查是否超过5分钟无活动
                        if asyncio.get_event_loop().time() - last_activity > 300:
                            logger.warning("Connection timeout due to inactivity")
                            await websocket.send_text("[警告] 连接超时，即将断开...")
                            break
                        # 发送心跳（空消息或ping）
                        await asyncio.sleep(30)
                    except Exception as e:
                        logger.debug(f"Heartbeat error: {e}")
                        break
            
            heartbeat_task = asyncio.create_task(heartbeat())
            
            # 读取输出任务
            async def read_output():
                nonlocal last_activity
                buffer = ""
                while True:
                    try:
                        if shell.recv_ready():
                            data = shell.recv(8192)
                            if data:
                                # 尝试解码，优先utf-8，失败则用gbk
                                try:
                                    output = data.decode('utf-8')
                                except UnicodeDecodeError:
                                    try:
                                        output = data.decode('gbk')
                                    except:
                                        output = data.decode('utf-8', errors='replace')
                                # 直接发送原始输出，不做任何修改
                                await websocket.send_text(output)
                                last_activity = asyncio.get_event_loop().time()
                        await asyncio.sleep(0.02)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error reading output: {e}")
                        break
                if buffer:
                    await websocket.send_text(buffer)
            
            read_task = asyncio.create_task(read_output())
            
            # 主循环：接收客户端消息
            try:
                while True:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=350)
                    last_activity = asyncio.get_event_loop().time()
                    logger.debug(f"Received command: {data[:50]}...")
                    if data.strip().lower() == 'exit':
                        break
                    # 发送数据到shell（xterm会自动处理换行，不需要额外添加\n）
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
        # 清理资源
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