from typing import Optional

from pydantic import BaseModel


class AdminIslemResponse(BaseModel):
    status: str
    message: Optional[str] = None
    id: Optional[int] = None


class GenelBasariliResponse(BaseModel):
    status: str
    message: str
