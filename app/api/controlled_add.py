from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.controlled_add import ControlledAddRequest, ControlledAddResponse
from app.services.controlled_admission import ControlledAdmissionService

router = APIRouter(prefix="/api/qbittorrent", tags=["controlled-admission"])


@router.post("/reservations/{reservation_id}/add", response_model=ControlledAddResponse, status_code=status.HTTP_201_CREATED)
def controlled_add_torrent(reservation_id: str, req: ControlledAddRequest, db: Session = Depends(get_db)):
    try:
        return ControlledAdmissionService.controlled_add(db, reservation_id, req)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
