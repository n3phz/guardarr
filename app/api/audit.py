from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.base import get_db
from app.db.models import AuditLogModel
from pydantic import BaseModel


router = APIRouter(prefix="/api", tags=["audit"])


class AuditEntryResponse(BaseModel):
    id: int
    reservation_id: str
    event_type: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/audit", response_model=List[AuditEntryResponse])
def list_audit_entries(
    reservation_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLogModel).order_by(desc(AuditLogModel.created_at))

    if reservation_id:
        query = query.filter(AuditLogModel.reservation_id == reservation_id)
    if event_type:
        query = query.filter(AuditLogModel.event_type == event_type)

    return query.offset(offset).limit(limit).all()