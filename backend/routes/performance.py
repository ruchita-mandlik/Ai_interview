from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.models import User
from backend.utils.security import get_current_user
from backend.services.dashboard_service import DashboardService

router = APIRouter(tags=["Performance Analytics"])

@router.get("/api/performance")
def get_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return DashboardService.get_performance_analytics(db, current_user)

@router.get("/api/history")
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.routes.interviews import list_interviews
    return list_interviews(current_user=current_user, db=db)
