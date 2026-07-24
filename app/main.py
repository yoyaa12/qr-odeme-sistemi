import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.database import execute_non_query
from app.core.socket_manager import sio
from app.api.views import router as views_router
from app.api.v1.api import api_router

app = FastAPI(title="QR Restoran Sipariş Otomasyonu API")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Socket.io ASGI uygulamasını FastAPI'ye bağlama
app_asgi = socketio.ASGIApp(sio, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyaları sunma
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Sayfa rotaları
app.include_router(views_router)

# REST API rotaları
app.include_router(api_router, prefix="/api")
