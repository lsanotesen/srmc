from typing import Optional

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
    cols: int = Query(80, ge=1, le=1000),
    rows: int = Query(24, ge=1, le=500),
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
        
        # 数据范围校验：token 校验通过后，还要确认用户对该服务所属项目有权限
        from models.user import User
        from api.permission_dependencies import user_can_access_project
        user = db.query(User).filter(User.username == user_id).first()
        if not user or not user.is_active or not user_can_access_project(db, user, service.project_id):
            logger.warning(f"Data scope denied: user={user_id}, service_id={service_id}")
            await websocket.send_text("[错误] 无权访问该服务")
            await websocket.close(code=1008)
            return
        
        # 功能权限校验（RBAC）：WebShell 登录需 webshell:login；以 root 登录时额外需 webshell:root-login
        from services.permission_service import PermissionService
        if not PermissionService.user_has_permission(db, user.id, "webshell:login"):
            logger.warning(f"RBAC denied (webshell:login): user={user_id}, service_id={service_id}")
            await websocket.send_text("[错误] 无 WebShell 登录权限")
            await websocket.close(code=1008)
            return
        if (service.username or "").strip() == "root" and not PermissionService.user_has_permission(db, user.id, "webshell:root-login"):
            logger.warning(f"RBAC denied (webshell:root-login): user={user_id}, service_id={service_id}")
            await websocket.send_text("[错误] 无 Root WebShell 登录权限")
            await websocket.close(code=1008)
            return

        # 项目级高风险独立授权：仅共享访问的用户，需共享记录中明确勾选 webshell / root
        from models.project import Project
        from services.data_scope_service import DataScopeService
        project = db.query(Project).filter(Project.id == service.project_id).first()
        if project:
            if not DataScopeService.has_high_risk_grant(db, user, project, "webshell"):
                logger.warning(f"High-risk grant denied (webshell): user={user_id}, service_id={service_id}")
                await websocket.send_text("[错误] 该项目共享未授予 WebShell 权限")
                await websocket.close(code=1008)
                return
            if (service.username or "").strip() == "root" and not DataScopeService.has_high_risk_grant(db, user, project, "root"):
                logger.warning(f"High-risk grant denied (root): user={user_id}, service_id={service_id}")
                await websocket.send_text("[错误] 该项目共享未授予 Root 登录权限")
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
            
            # 请求PTY伪终端：按前端传入的实际终端尺寸创建，
            # 避免首次提示符按 80x24 绘制、后续 resize 前长输入错位
            logger.info(f"Request PTY with initial size {cols}x{rows} for service {service_id}")
            shell = await asyncio.wait_for(
                conn.invoke_shell(term_type='xterm', width=cols, height=rows),
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
            # 用单个 receive() 按消息类型分发，避免并发 receive_text/receive_bytes
            # 消费同一接收队列导致字符丢失（pending task 越积越多，消息被错误分发）
            try:
                while True:
                    message = await websocket.receive()
                    last_activity = asyncio.get_event_loop().time()

                    if message.get("type") == "websocket.disconnect":
                        logger.info("WebSocket disconnected by client")
                        break

                    if "text" in message and message["text"] is not None:
                        # 文本消息：键盘输入，直接转发到 shell
                        data = message["text"]
                        logger.debug(f"Received keystroke: {data[:50]}...")
                        if data.strip().lower() == 'exit':
                            break
                        shell.send(data)
                    elif "bytes" in message and message["bytes"] is not None:
                        # 二进制消息：控制指令（resize 等）
                        try:
                            result = bytearray(message["bytes"])
                            if len(result) >= 5 and result[0] == 0x01:
                                # resize: [0x01][cols_le][rows_le]
                                new_cols = int.from_bytes(result[1:3], 'little')
                                new_rows = int.from_bytes(result[3:5], 'little')
                                if new_cols <= 0 or new_rows <= 0:
                                    logger.warning(f"Ignore invalid PTY size {new_cols}x{new_rows} for service {service_id}")
                                else:
                                    try:
                                        loop = asyncio.get_event_loop()
                                        await loop.run_in_executor(
                                            None,
                                            lambda c=new_cols, r=new_rows: shell.resize_pty(width=c, height=r)
                                        )
                                        logger.info(f"Resize PTY to {new_cols}x{new_rows} for service {service_id}")
                                    except Exception as resize_err:
                                        logger.warning(f"Failed to resize PTY to {new_cols}x{new_rows} for service {service_id}: {resize_err}")
                            else:
                                logger.debug(f"Unknown binary control: {result[:10]}")
                        except Exception as bin_err:
                            logger.warning(f"Binary message error: {bin_err}")
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


async def _bridge_shell(websocket: WebSocket, conn, shell, label: str):
    """在已建立的 SSH shell 与 WebSocket 之间双向转发数据。"""
    read_task = None
    heartbeat_task = None
    last_activity = asyncio.get_event_loop().time()

    async def heartbeat():
        nonlocal last_activity
        while True:
            try:
                if asyncio.get_event_loop().time() - last_activity > 300:
                    logger.warning(f"Connection timeout due to inactivity: {label}")
                    await websocket.send_text("[警告] 连接超时，即将断开...")
                    break
                await asyncio.sleep(30)
            except Exception:
                break

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
                            except Exception:
                                output = data.decode('utf-8', errors='replace')
                        await websocket.send_text(output)
                        last_activity = asyncio.get_event_loop().time()
                await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading output: {e}")
                break

    try:
        heartbeat_task = asyncio.create_task(heartbeat())
        read_task = asyncio.create_task(read_output())

        while True:
            message = await websocket.receive()
            last_activity = asyncio.get_event_loop().time()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text") is not None:
                data = message["text"]
                if data.strip().lower() == 'exit':
                    break
                shell.send(data)
            elif message.get("bytes") is not None:
                try:
                    result = bytearray(message["bytes"])
                    if len(result) >= 5 and result[0] == 0x01:
                        new_cols = int.from_bytes(result[1:3], 'little')
                        new_rows = int.from_bytes(result[3:5], 'little')
                        if new_cols <= 0 or new_rows <= 0:
                            logger.warning(f"Ignore invalid PTY size {new_cols}x{new_rows} ({label})")
                        else:
                            loop = asyncio.get_event_loop()
                            try:
                                await loop.run_in_executor(
                                    None, lambda c=new_cols, r=new_rows: shell.resize_pty(width=c, height=r)
                                )
                                logger.info(f"Resize PTY to {new_cols}x{new_rows} ({label})")
                            except Exception as resize_err:
                                logger.warning(f"Failed to resize PTY to {new_cols}x{new_rows} ({label}): {resize_err}")
                    else:
                        logger.debug(f"Unknown binary control: {result[:10]}")
                except Exception as bin_err:
                    logger.warning(f"Binary message error: {bin_err}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected by client: {label}")
    except Exception as e:
        logger.error(f"Error during WebSocket communication ({label}): {e}")
        try:
            await websocket.send_text(f"[错误] {str(e)}")
        except Exception:
            pass
    finally:
        if read_task:
            read_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if shell:
            try:
                shell.close()
            except Exception:
                pass
        if conn:
            conn.close()


@router.websocket("/shell/server/ws/{server_id}")
async def server_websocket_endpoint(
    websocket: WebSocket,
    server_id: int,
    token: str = Query(...),
    cols: int = Query(80, ge=1, le=1000),
    rows: int = Query(24, ge=1, le=500),
    account_id: Optional[int] = Query(None, description="指定 SSH 账号；缺省使用默认账号"),
    db: Session = Depends(get_db)
):
    """服务器管理页的远程登录：按服务器记录建立 SSH shell。

    与服务 WebShell 一致使用 webshell:login / webshell:root-login 权限，
    数据范围按服务器的组织隔离校验；不涉及项目共享高风险授权。
    account_id 可指定服务器下的某个 SSH 账号，缺省使用默认账号。
    """
    logger.info(f"Server WebSocket connection attempt for server_id: {server_id}")
    await websocket.accept()

    try:
        username = await authenticate_token(token, db)
        if not username:
            await websocket.send_text("[错误] 无效的认证token")
            await websocket.close(code=1008)
            return

        from models.user import User
        from models.server import Server, ServerSshAccount
        from api.server import _scope_server_query
        from services.permission_service import PermissionService
        from services.audit_service import log_audit

        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            await websocket.send_text("[错误] 用户不存在或已停用")
            await websocket.close(code=1008)
            return

        server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
        if not server:
            await websocket.send_text("[错误] 服务器不存在或无权访问")
            await websocket.close(code=1008)
            return

        if not PermissionService.user_has_permission(db, user.id, "webshell:login"):
            await websocket.send_text("[错误] 无 WebShell 登录权限")
            await websocket.close(code=1008)
            return

        # 缺省使用默认账号（servers 兼容字段即默认账号镜像）；account_id 可指定多账号中的某一个
        login_username = server.username
        stored_password, stored_private_key = server.password, server.private_key
        if account_id is not None:
            account = db.query(ServerSshAccount).filter(
                ServerSshAccount.id == account_id,
                ServerSshAccount.server_id == server.id,
            ).first()
            if not account:
                await websocket.send_text("[错误] SSH 账号不存在或不属于该服务器")
                await websocket.close(code=1008)
                return
            login_username = account.username
            stored_password, stored_private_key = account.password, account.private_key

        if (login_username or "").strip() == "root" and not PermissionService.user_has_permission(db, user.id, "webshell:root-login"):
            await websocket.send_text("[错误] 无 Root WebShell 登录权限")
            await websocket.close(code=1008)
            return

        password = decrypt(stored_password) if stored_password else None
        private_key = decrypt(stored_private_key) if stored_private_key else None
        if not password and not private_key:
            await websocket.send_text("[错误] 该 SSH 账号未配置密码或私钥")
            await websocket.close(code=1008)
            return

        try:
            conn = await asyncio.wait_for(
                ssh_pool.get_connection(server.ip, server.ssh_port, login_username, password, private_key),
                timeout=15
            )
            if not conn:
                await websocket.send_text("[错误] 无法连接到服务器，请检查SSH配置")
                await websocket.close(code=1011)
                return

            logger.info(f"Request PTY with initial size {cols}x{rows} for server {server_id}")
            shell = await asyncio.wait_for(
                conn.invoke_shell(term_type='xterm', width=cols, height=rows),
                timeout=10
            )
            if not shell:
                await websocket.send_text("[错误] 无法打开shell会话")
                conn.close()
                await websocket.close(code=1011)
                return

            log_audit(db, user.id, user.username, "SHELL",
                      server_id=server.id, ip=server.ip, result="success",
                      output=f"SSH账号: {login_username}",
                      request_url=f"/api/shell/server/ws/{server_id}")
            await asyncio.sleep(0.2)
            await _bridge_shell(websocket, conn, shell, f"server#{server_id}")
        except asyncio.TimeoutError:
            await websocket.send_text("[错误] 连接超时，请检查网络或稍后重试")
            await websocket.close(code=1011)
        except Exception as ssh_error:
            logger.error(f"SSH connection error (server {server_id}): {ssh_error}")
            await websocket.send_text(f"[错误] SSH连接失败: {str(ssh_error)[:50]}...")
            await websocket.close(code=1011)
    except Exception as e:
        logger.error(f"Unexpected error in server WebSocket endpoint: {e}")
        try:
            await websocket.send_text(f"[错误] {str(e)[:50]}...")
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"Server WebSocket fully closed for server {server_id}")