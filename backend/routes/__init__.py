from backend.routes.auth import router as auth_router
from backend.routes.profile import router as profile_router
from backend.routes.interviews import router as interviews_router
from backend.routes.evaluation import router as evaluation_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.performance import router as performance_router
from backend.routes.resume_analysis import router as resume_analysis_router
from backend.routes.coding_interviews import router as coding_router
from backend.routes.analytics import router as analytics_router
from backend.routes.ai import router as ai_router
from backend.routes.users import router as users_router
from backend.routes.recommendations import router as recommendations_router
from backend.routes.voice import router as voice_router
from backend.routes.roadmap import router as roadmap_router
from backend.routes.readiness import router as readiness_router
from backend.routes.intelligence import router as intelligence_router

__all__ = [
    "auth_router",
    "profile_router",
    "interviews_router",
    "evaluation_router",
    "dashboard_router",
    "performance_router",
    "resume_analysis_router",
    "coding_router",
    "analytics_router",
    "ai_router",
    "users_router",
    "recommendations_router",
    "voice_router",
    "roadmap_router",
    "readiness_router",
    "intelligence_router",
]
