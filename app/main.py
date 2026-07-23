import os
import uuid
import datetime
import decimal
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import socketio
from pydantic import BaseModel
from typing import List, Optional

from app.database import execute_query, execute_non_query

def sanitize_for_json(data):
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime.datetime, datetime.date, datetime.time)):
        return data.strftime("%H:%M:%S") if isinstance(data, (datetime.datetime, datetime.time)) else str(data)
    elif isinstance(data, decimal.Decimal):
        return float(data)
    return data

# Socket.io Async Sunucusu Oluşturma
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
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


# -------------------------------------------------------------
# PYDANTIC MODELLERİ
# -------------------------------------------------------------
class SiparisItemModel(BaseModel):
    urun_id: int
    adet: int
    birim_fiyat: float
    urun_notu: Optional[str] = ""

class SiparisOlusturModel(BaseModel):
    masa_id: int
    toplam_tutar: float
    odeme_yontemi: Optional[str] = "pos" # "pos" veya "nakit"
    urunler: List[SiparisItemModel]

class DurumGuncelleModel(BaseModel):
    yeni_durum: str
    garson_adi: Optional[str] = None

class LoginModel(BaseModel):
    kullanici_adi: str
    sifre: str

class UrunEkleModel(BaseModel):
    kategori_id: int
    urun_adi: str
    aciklama: Optional[str] = ""
    fiyat: float
    gorsel_url: Optional[str] = ""
    stok_miktari: Optional[int] = 100

class KategoriEkleModel(BaseModel):
    kategori_adi: str

class MasaEkleModel(BaseModel):
    masa_no: str


# -------------------------------------------------------------
# SOCKET.IO EVENT HANDLERS
# -------------------------------------------------------------
@sio.event
async def connect(sid, environ):
    print(f"[Socket.io] İstemci bağlandı: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[Socket.io] İstemci ayrıldı: {sid}")


# -------------------------------------------------------------
# HTML SAYFA YÖNLENDİRMELERİ
# -------------------------------------------------------------
def get_html_content(filename: str):
    path = os.path.join("templates", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>Sayfa Bulunamadı: {filename}</h1>"

@app.get("/", response_class=HTMLResponse)
async def home_page():
    return get_html_content("index.html")

@app.get("/menu", response_class=HTMLResponse)
async def customer_menu_page():
    return get_html_content("menu.html")

@app.get("/mutfak", response_class=HTMLResponse)
async def kitchen_panel_page():
    return get_html_content("mutfak.html")

@app.get("/garson", response_class=HTMLResponse)
async def waiter_panel_page():
    return get_html_content("garson.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel_page():
    return get_html_content("admin.html")


# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------

# 1. KATEGORİLER
@app.get("/api/kategoriler")
async def get_kategoriler():
    query = "SELECT id, kategori_adi, aktif_mi FROM Kategoriler WHERE aktif_mi = 1 ORDER BY id ASC"
    res = execute_query(query)
    return res or []

# 2. ÜRÜNLER
@app.get("/api/urunler")
async def get_urunler(kategori_id: Optional[int] = None):
    if kategori_id:
        query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.kategori_id = ? AND u.aktif_mi = 1"
        res = execute_query(query, (kategori_id,))
    else:
        query = "SELECT u.*, k.kategori_adi FROM Urunler u JOIN Kategoriler k ON u.kategori_id = k.id WHERE u.aktif_mi = 1"
        res = execute_query(query)
    return res or []

# 3. MASALAR
@app.get("/api/masalar")
async def get_masalar():
    query = "SELECT id, masa_no, qr_kodu, durum FROM Masalar ORDER BY id ASC"
    res = execute_query(query)
    return res or []

# 4. SİPARİŞ OLUŞTURMA (POS VEYA NAKİT SEÇENEKLİ)
@app.post("/api/siparisler")
async def create_siparis(data: SiparisOlusturModel):
    siparis_kodu = f"SIP-{uuid.uuid4().hex[:6].upper()}"
    
    masa = execute_query("SELECT * FROM Masalar WHERE id = ?", (data.masa_id,), fetch_one=True)
    if not masa:
        raise HTTPException(status_code=404, detail="Geçersiz masa ID!")

    odeme_durumu = "odendi" if data.odeme_yontemi == "pos" else "nakit_bekliyor"
    siparis_durumu = "odendi_mutfakta" if data.odeme_yontemi == "pos" else "nakit_bekliyor"

    insert_order_query = """
        INSERT INTO Siparisler (masa_id, siparis_kodu, toplam_tutar, odeme_durumu, siparis_durumu)
        VALUES (?, ?, ?, ?, ?)
    """
    siparis_id = execute_non_query(insert_order_query, (data.masa_id, siparis_kodu, data.toplam_tutar, odeme_durumu, siparis_durumu))

    if not siparis_id:
        s_row = execute_query("SELECT id FROM Siparisler WHERE siparis_kodu = ?", (siparis_kodu,), fetch_one=True)
        if s_row:
            siparis_id = s_row['id']
        else:
            raise HTTPException(status_code=500, detail="Sipariş veritabanına eklenirken hata oluştu.")

    execute_non_query("UPDATE Masalar SET durum = 'dolu' WHERE id = ?", (data.masa_id,))

    detaylar = []
    for item in data.urunler:
        ara_toplam = item.adet * item.birim_fiyat
        insert_detail_query = """
            INSERT INTO SiparisDetaylari (siparis_id, urun_id, adet, birim_fiyat, urun_notu, ara_toplam)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_non_query(insert_detail_query, (siparis_id, item.urun_id, item.adet, item.birim_fiyat, item.urun_notu, ara_toplam))

        u_info = execute_query("SELECT urun_adi FROM Urunler WHERE id = ?", (item.urun_id,), fetch_one=True)
        urun_adi = u_info['urun_adi'] if u_info else f"Ürün #{item.urun_id}"

        execute_non_query("UPDATE Urunler SET stok_miktari = CASE WHEN stok_miktari >= ? THEN stok_miktari - ? ELSE 0 END WHERE id = ?", (item.adet, item.adet, item.urun_id))

        detaylar.append({
            "urun_id": item.urun_id,
            "urun_adi": urun_adi,
            "adet": item.adet,
            "birim_fiyat": item.birim_fiyat,
            "urun_notu": item.urun_notu,
            "ara_toplam": ara_toplam
        })

    full_order = {
        "id": siparis_id,
        "masa_id": data.masa_id,
        "masa_no": masa['masa_no'],
        "siparis_kodu": siparis_kodu,
        "toplam_tutar": data.toplam_tutar,
        "odeme_yontemi": data.odeme_yontemi,
        "odeme_durumu": odeme_durumu,
        "siparis_durumu": siparis_durumu,
        "olusturma_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
        "detaylar": detaylar
    }

    # SOCKET.IO BİLDİRİMLERİ (Sadece POS ile ödendi ise mutfağa anında düşer)
    if data.odeme_yontemi == "pos":
        await sio.emit("yeni_siparis", full_order)

    await sio.emit("masa_durumu_degisti", {"masa_id": data.masa_id, "durum": "dolu"})
    
    if data.odeme_yontemi == "nakit":
        await sio.emit("nakit_odeme_talebi", {
            "siparis_id": siparis_id,
            "masa_id": data.masa_id,
            "masa_no": masa['masa_no'],
            "toplam_tutar": data.toplam_tutar,
            "siparis": full_order
        })

    return {"status": "success", "message": "Sipariş oluşturuldu.", "siparis": full_order}


# 5. SİPARİŞLERİ LİSTELEME
@app.get("/api/siparisler")
async def get_siparisler(durum: Optional[str] = None, masa_id: Optional[int] = None):
    if masa_id:
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.masa_id = ? ORDER BY s.id DESC"
        siparisler = execute_query(query, (masa_id,)) or []
    elif durum:
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.siparis_durumu = ? ORDER BY s.id DESC"
        siparisler = execute_query(query, (durum,)) or []
    else:
        query = "SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id ORDER BY s.id DESC"
        siparisler = execute_query(query) or []

    for s in siparisler:
        d_query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        s['detaylar'] = execute_query(d_query, (s['id'],)) or []

    return sanitize_for_json(siparisler)


# 5.5 MASANIN AKTİF SİPARİŞİNİ ALMA (F5 KORUMASI İÇİN)
@app.get("/api/masalar/{masa_id}/aktif-siparis")
async def get_masa_aktif_siparis(masa_id: int):
    query = """
        SELECT TOP 1 s.*, m.masa_no 
        FROM Siparisler s 
        JOIN Masalar m ON s.masa_id = m.id 
        WHERE s.masa_id = ? AND s.siparis_durumu != 'teslim_edildi' 
        ORDER BY s.id DESC
    """
    siparis = execute_query(query, (masa_id,), fetch_one=True)
    if siparis:
        d_query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        siparis['detaylar'] = execute_query(d_query, (siparis['id'],)) or []
        if isinstance(siparis.get('olusturma_tarihi'), datetime.datetime):
            siparis['olusturma_tarihi'] = siparis['olusturma_tarihi'].strftime("%H:%M:%S")
        return {"has_active": True, "siparis": siparis}
    return {"has_active": False, "siparis": None}


# 6. SİPARİŞ DURUMU GÜNCELLEME
@app.patch("/api/siparisler/{siparis_id}/durum")
async def update_siparis_durumu(siparis_id: int, data: DurumGuncelleModel):
    try:
        yeni_durum = data.yeni_durum.lower()
        
        s_info = execute_query("SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.id = ?", (siparis_id,), fetch_one=True)
        if not s_info:
            raise HTTPException(status_code=404, detail="Sipariş bulunamadı!")

        garson_adi = data.garson_adi or "Garson Berat"

        if yeni_durum == "nakit_tahsil_edildi":
            try:
                execute_non_query(
                    "UPDATE Siparisler SET odeme_durumu = 'odendi', siparis_durumu = 'odendi_mutfakta', garson_adi = ? WHERE id = ?",
                    (garson_adi, siparis_id)
                )
            except Exception:
                execute_non_query(
                    "UPDATE Siparisler SET odeme_durumu = 'odendi', siparis_durumu = 'odendi_mutfakta' WHERE id = ?",
                    (siparis_id,)
                )
            yeni_durum = "odendi_mutfakta"
        else:
            execute_non_query("UPDATE Siparisler SET siparis_durumu = ? WHERE id = ?", (yeni_durum, siparis_id))

        if yeni_durum in ["teslim_edildi", "iptal"]:
            aktif_siparisler = execute_query(
                "SELECT COUNT(*) as cnt FROM Siparisler WHERE masa_id = ? AND siparis_durumu IN ('nakit_bekliyor', 'odendi_mutfakta', 'hazirlaniyor', 'hazir')",
                (s_info['masa_id'],),
                fetch_one=True
            )
            if not aktif_siparisler or aktif_siparisler['cnt'] == 0:
                execute_non_query("UPDATE Masalar SET durum = 'bos' WHERE id = ?", (s_info['masa_id'],))
                await sio.emit("masa_durumu_degisti", {"masa_id": s_info['masa_id'], "durum": "bos"})

        # Güncellenmiş siparişi detaylarıyla çek
        updated_order = execute_query("SELECT s.*, m.masa_no FROM Siparisler s JOIN Masalar m ON s.masa_id = m.id WHERE s.id = ?", (siparis_id,), fetch_one=True)
        if not updated_order:
            updated_order = dict(s_info)
            updated_order['siparis_durumu'] = yeni_durum
        
        d_query = "SELECT sd.*, u.urun_adi FROM SiparisDetaylari sd JOIN Urunler u ON sd.urun_id = u.id WHERE sd.siparis_id = ?"
        updated_order['detaylar'] = execute_query(d_query, (siparis_id,)) or []
        
        updated_order = sanitize_for_json(updated_order)

        event_payload = sanitize_for_json({
            "siparis_id": siparis_id,
            "masa_id": s_info['masa_id'],
            "masa_no": s_info['masa_no'],
            "yeni_durum": yeni_durum,
            "odeme_durumu": updated_order.get("odeme_durumu", "odendi"),
            "garson_adi": garson_adi,
            "guncelleme_tarihi": datetime.datetime.now().strftime("%H:%M:%S"),
            "siparis": updated_order
        })

        if data.yeni_durum == "nakit_tahsil_edildi":
            # Nakit tahsil edilince mutfağa yeni sipariş uyarısı at
            await sio.emit("yeni_siparis", updated_order)
            await sio.emit("nakit_odendi", event_payload)

        await sio.emit("durum_guncellendi", event_payload)

        return {"status": "success", "message": f"Sipariş güncellendi.", "data": event_payload}
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Veritabanı/Sunucu hatası: {str(e)}")


# 7. AUTH & ADMIN ENDPOINTS
@app.post("/api/auth/login")
async def login(data: LoginModel):
    user = execute_query("SELECT id, kullanici_adi, rol FROM Kullanicilar WHERE kullanici_adi = ? AND sifre_hash = ?", (data.kullanici_adi, data.sifre), fetch_one=True)
    if not user:
        raise HTTPException(status_code=401, detail="Hatalı giriş!")
    return {"status": "success", "user": user}

@app.post("/api/admin/urunler")
async def add_urun(data: UrunEkleModel):
    uid = execute_non_query("INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)", (data.kategori_id, data.urun_adi, data.aciklama, data.fiyat, data.gorsel_url, data.stok_miktari))
    return {"status": "success", "id": uid}

@app.delete("/api/admin/urunler/{urun_id}")
async def delete_urun(urun_id: int):
    execute_non_query("DELETE FROM Urunler WHERE id = ?", (urun_id,))
    return {"status": "success"}

@app.post("/api/admin/kategoriler")
async def add_kategori(data: KategoriEkleModel):
    kid = execute_non_query("INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)", (data.kategori_adi,))
    return {"status": "success", "id": kid}

@app.delete("/api/admin/kategoriler/{kategori_id}")
async def delete_kategori(kategori_id: int):
    execute_non_query("DELETE FROM Kategoriler WHERE id = ?", (kategori_id,))
    return {"status": "success"}

@app.post("/api/admin/masalar")
async def add_masa(data: MasaEkleModel):
    qr_code = f"MASA_{data.masa_no.upper().replace(' ', '_')}"
    mid = execute_non_query("INSERT INTO Masalar (masa_no, qr_kodu, durum) VALUES (?, ?, 'bos')", (data.masa_no, qr_code))
    return {"status": "success", "id": mid}

@app.delete("/api/admin/masalar/{masa_id}")
async def delete_masa(masa_id: int):
    execute_non_query("DELETE FROM Masalar WHERE id = ?", (masa_id,))
    return {"status": "success"}
