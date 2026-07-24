from fastapi import APIRouter, Depends
from app.services.auth_service import AuthService
from app.schemas.schemas import LoginModel

router = APIRouter()

@router.post("/auth/login")
async def login(data: LoginModel, service: AuthService = Depends()):
    user = service.login(data)
    return {"status": "success", "user": user}
