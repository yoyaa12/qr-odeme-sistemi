from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_staff
from app.auth.models import StaffPrincipal
from app.services.auth_service import AuthService
from app.schemas.auth import KullaniciResponse, LoginModel, LoginResponse

router = APIRouter()

@router.post("/auth/login", response_model=LoginResponse)
def login(data: LoginModel, request: Request, service: AuthService = Depends()):
    client_host = request.client.host if request.client else "unknown"
    result = service.login(data, client_host)
    user = KullaniciResponse(
        id=result.principal.user_id,
        kullanici_adi=result.principal.username,
        rol=result.principal.role,
    )
    return LoginResponse(
        status="success",
        user=user,
        access_token=result.access_token,
        expires_in=result.expires_in,
    )


@router.get("/auth/me", response_model=KullaniciResponse)
def get_authenticated_staff(
    principal: StaffPrincipal = Depends(get_current_staff),
):
    return KullaniciResponse(
        id=principal.user_id,
        kullanici_adi=principal.username,
        rol=principal.role,
    )
