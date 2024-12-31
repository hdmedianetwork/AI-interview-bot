# src/routers/__init__.py
from .users.main import router as users_router
from .qna.main import router as qna_router

__all__ = [
    "users_router",
    "qna_router"
           ]
