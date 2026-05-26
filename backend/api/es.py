from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.service import Service
from schemas.common import ResponseModel
import requests
import json
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

def get_es_client(service):
    config = json.loads(service.extra_config) if service.extra_config else {}
    username = config.get('username', '')
    password = config.get('password', '')
    
    url = f"http://{service.ip}:{service.port}"
    
    if username and password:
        return requests.Session(), url, (username, password)
    return requests.Session(), url, None

@router.get("/es/cluster/{service_id}", response_model=ResponseModel)
async def get_cluster_health(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.get(f"{url}/_cluster/health", auth=auth)
        response.raise_for_status()
        return ResponseModel(data=response.json())
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.get("/es/nodes/{service_id}", response_model=ResponseModel)
async def get_nodes(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.get(f"{url}/_cat/nodes?v", auth=auth)
        response.raise_for_status()
        return ResponseModel(data={"raw": response.text})
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.get("/es/indices/{service_id}", response_model=ResponseModel)
async def get_indices(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.get(f"{url}/_cat/indices?v", auth=auth)
        response.raise_for_status()
        return ResponseModel(data={"raw": response.text})
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.get("/es/index/{service_id}/{index_name}", response_model=ResponseModel)
async def get_index_info(service_id: int, index_name: str, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.get(f"{url}/{index_name}/_mapping", auth=auth)
        response.raise_for_status()
        return ResponseModel(data=response.json())
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.delete("/es/index/{service_id}/{index_name}", response_model=ResponseModel)
async def delete_index(service_id: int, index_name: str, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.delete(f"{url}/{index_name}", auth=auth)
        response.raise_for_status()
        return ResponseModel(data=response.json())
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.post("/es/search/{service_id}", response_model=ResponseModel)
async def execute_dsl(service_id: int, query: dict, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.post(f"{url}/_search", json=query, auth=auth)
        response.raise_for_status()
        return ResponseModel(data=response.json())
    except Exception as e:
        return ResponseModel(code=1, message=str(e))

@router.get("/es/snapshots/{service_id}", response_model=ResponseModel)
async def get_snapshots(service_id: int, repository: str = "_all", db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    session, url, auth = get_es_client(service)
    
    try:
        response = session.get(f"{url}/_snapshot/{repository}/_all", auth=auth)
        response.raise_for_status()
        return ResponseModel(data=response.json())
    except Exception as e:
        return ResponseModel(code=1, message=str(e))
