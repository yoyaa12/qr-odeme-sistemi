from fastapi import APIRouter
from app.api.v1.endpoints import (
    kategoriler, urunler, masalar, siparisler, garson, auth, admin
)

api_router = APIRouter()

api_router.include_router(kategoriler.router, tags=["kategoriler"])
api_router.include_router(urunler.router, tags=["urunler"])
api_router.include_router(masalar.router, tags=["masalar"])
api_router.include_router(siparisler.router, tags=["siparisler"])
api_router.include_router(garson.router, tags=["garson"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(admin.router, tags=["admin"])
