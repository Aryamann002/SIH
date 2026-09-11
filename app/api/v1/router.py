from fastapi import APIRouter
from app.api.v1 import stream, actions, sessions

api_router = APIRouter()

api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(actions.router, prefix="/actions", tags=["actions"])
api_router.include_router(sessions.router, tags=["sessions"])
