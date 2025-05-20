from fastapi import APIRouter
from app.api.v1.endpoints import chat
 
api_router_v1 = APIRouter()
api_router_v1.include_router(chat.router, prefix="/chat", tags=["Chat Agent"]) 