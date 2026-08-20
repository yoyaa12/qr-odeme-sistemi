"""Kimlik doğrulama uçlarının döndürdüğü yanıt nesneleri.

Entity'ler (`entity.py`) doğrudan döndürülmez. Aradaki fark önemli:
`KullaniciEntity` `sifre_hash` taşır, `KullaniciResponse` taşımaz. Yanıt
modelini ayrı tutmak, bir kolonun yanlışlıkla dışarı sızmasını tip düzeyinde
imkânsız hale getirir — FastAPI `response_model`'de tanımlı olmayan her alanı
serileştirmeden önce eler.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.enums import UserRole


class KullaniciResponse(BaseModel):
    """Oturum açmış personelin dışarı verilebilir kimliği.

    `kullanici_adi` ve `garson_adi` aynı kolonun iki adıdır: personel girişi
    ilkini, garson PIN akışı ikincisini doldurur. `sifre_hash` burada yoktur ve
    olmamalıdır.
    """

    id: int
    kullanici_adi: Optional[str] = None
    garson_adi: Optional[str] = None
    rol: Optional[UserRole] = None


class GarsonResponse(BaseModel):
    """Garson seçim listelerinde kullanılan sade gösterim."""

    id: int
    ad_soyad: str


class LoginResponse(BaseModel):
    """`POST /api/auth/login` yanıtı."""

    status: str
    user: KullaniciResponse
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=60, le=365 * 24 * 3600)


class GarsonPinResponse(BaseModel):
    """`POST /api/garson/verify-pin` yanıtı."""

    status: str
    garson: KullaniciResponse
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=60, le=365 * 24 * 3600)
