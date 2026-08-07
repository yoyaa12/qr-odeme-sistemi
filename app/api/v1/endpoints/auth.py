from fastapi import APIRouter, Depends
from app.services.auth_service import AuthService
from app.schemas.schemas import LoginModel, LoginResponse

router = APIRouter()

@router.post("/auth/login", response_model=LoginResponse)
async def login(data: LoginModel, service: AuthService = Depends()):
    user = service.login(data)
    return LoginResponse(status="success", user=user)
