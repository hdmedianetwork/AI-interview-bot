# src/routers/__init__.py
from .users.main import router as users_router
from .qna.main import router as qna_router
from .feedback.main import router as feedback_router
from .dashboard.main import  router as dashboard_route

__all__ = [
    "users_router",
    "qna_router",
    "feedback_router",
    "dashboard_route"
           ]
