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

from app.core.image_loader import sync_product_images

@app.on_event("startup")
async def startup_db_updates():
    try:
        execute_non_query("IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Kategoriler' AND COLUMN_NAME = 'gorsel_url') ALTER TABLE Kategoriler ADD gorsel_url NVARCHAR(255) NULL;")
        execute_non_query("IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Masalar' AND COLUMN_NAME = 'totp_secret') ALTER TABLE Masalar ADD totp_secret VARCHAR(64) NULL;")
        execute_non_query("IF NOT EXISTS (SELECT * FROM Masalar WHERE id=99) BEGIN SET IDENTITY_INSERT Masalar ON; INSERT INTO Masalar (id, masa_no, masa_durumu) VALUES (99, 'Developer Masası', 'musait'); SET IDENTITY_INSERT Masalar OFF; END")
        sync_product_images()
    except Exception as e:
        print("Startup migration notice:", e)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Socket.io ASGI uygulamasını FastAPI'ye bağlama
app_asgi = socketio.ASGIApp(sio, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"], # Geliştirme ortamı için. Canlıda gerçek domainler eklenmeli.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyaları sunma
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/img/kategoriler", exist_ok=True)
os.makedirs("static/img/urunler", exist_ok=True)
for sub in ["corbalar", "pizzalar", "burgerler", "salatalar", "tatlilar", "icecekler", "aperatifler", "soslar"]:
    os.makedirs(f"static/img/urunler/{sub}", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Sayfa rotaları
app.include_router(views_router)

# REST API rotaları
app.include_router(api_router, prefix="/api")
