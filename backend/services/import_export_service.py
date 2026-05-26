from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from schemas.service import ServiceImportResult
from utils.excel_utils import parse_excel, generate_excel_template
from utils.crypto import encrypt
from services.audit_service import log_audit
from core.capabilities import ServiceType

async def import_services(file_content: bytes, db: Session, user_id: int, username: str):
    rows = parse_excel(file_content)
    
    added = 0
    updated = 0
    failed = 0
    failed_items = []
    
    for row in rows:
        try:
            service_code = row.get('service_code')
            if not service_code:
                failed += 1
                failed_items.append({"row": row, "reason": "service_code is required"})
                continue
            
            existing = db.query(Service).filter(Service.service_code == service_code).first()
            
            ip = row.get('ip')
            server = db.query(Server).filter(Server.ip == ip).first()
            if not server:
                failed += 1
                failed_items.append({"row": row, "reason": f"Server with ip {ip} not found"})
                continue
            
            service_type = row.get('service_type', 'OTHER').upper()
            if service_type not in [e.value for e in ServiceType]:
                service_type = 'OTHER'
            
            environment = row.get('environment', 'DEV').upper()
            if environment not in ['DEV', 'TEST', 'STAGING', 'PROD']:
                environment = 'DEV'
            
            if existing:
                for key, value in row.items():
                    if value and hasattr(existing, key):
                        if key in ['password', 'private_key']:
                            setattr(existing, key, encrypt(value))
                        else:
                            setattr(existing, key, value)
                existing.server_id = server.id
                db.commit()
                updated += 1
            else:
                new_service = Service(
                    service_name=row.get('service_name', ''),
                    service_code=service_code,
                    service_type=service_type,
                    module=row.get('module'),
                    environment=environment,
                    server_id=server.id,
                    ip=ip,
                    port=int(row.get('port')) if row.get('port') else None,
                    service_path=row.get('service_path'),
                    work_dir=row.get('work_dir'),
                    start_script=row.get('start_script'),
                    stop_script=row.get('stop_script'),
                    restart_script=row.get('restart_script'),
                    log_path=row.get('log_path'),
                    check_type=row.get('check_type'),
                    check_keyword=row.get('check_keyword'),
                    pid_file=row.get('pid_file'),
                    owner=row.get('owner'),
                    remark=row.get('remark')
                )
                db.add(new_service)
                db.commit()
                added += 1
        except Exception as e:
            failed += 1
            failed_items.append({"row": row, "reason": str(e)})
    
    log_audit(db, user_id, username, "IMPORT", result="success" if failed == 0 else "failed",
              output=f"Added: {added}, Updated: {updated}, Failed: {failed}")
    
    return ServiceImportResult(
        success=failed == 0,
        message=f"Import completed: {added} added, {updated} updated, {failed} failed",
        added=added,
        updated=updated,
        failed=failed,
        failed_items=failed_items
    )
