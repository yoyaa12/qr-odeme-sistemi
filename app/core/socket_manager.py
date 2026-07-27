import socketio
from app.core.events import event_bus

# Socket.io Async Sunucusu Oluşturma
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# Masada menüyü inceleyen / sepete ürün ekleyen masaların sunucu tarafında takibi
BROWSING_TABLES = {}

@sio.event
async def connect(sid, environ):
    print(f"[Socket.io] İstemci bağlandı: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[Socket.io] İstemci ayrıldı: {sid}")

@sio.event
async def musteri_oturdu(sid, data):
    print(f"[Socket.io] Müşteri menüyü açtı: {data}")
    if data and isinstance(data, dict) and "masa_id" in data:
        masa_id = int(data["masa_id"])
        if masa_id not in BROWSING_TABLES:
            BROWSING_TABLES[masa_id] = {
                "masa_id": masa_id,
                "masa_no": data.get("masa_no", f"Masa {masa_id}"),
                "item_count": 0,
                "last_item": ""
            }
    await sio.emit("garson_musteri_geldi", data)

@sio.event
async def musteri_urun_secti(sid, data):
    print(f"[Socket.io] Müşteri sepete ürün ekledi: {data}")
    if data and isinstance(data, dict) and "masa_id" in data:
        masa_id = int(data["masa_id"])
        item_count = data.get("item_count", 0)
        BROWSING_TABLES[masa_id] = {
            "masa_id": masa_id,
            "masa_no": data.get("masa_no", f"Masa {masa_id}"),
            "item_count": item_count,
            "last_item": data.get("last_item", "")
        }
    await sio.emit("garson_musteri_urun_secti", data)

def get_browsing_tables():
    return BROWSING_TABLES

def clear_browsing_table(masa_id: int):
    if masa_id in BROWSING_TABLES:
        del BROWSING_TABLES[masa_id]

# --- EventBus Subscriptions ---
@event_bus.subscribe("yeni_siparis")
async def on_yeni_siparis(payload):
    await sio.emit("yeni_siparis", payload)

@event_bus.subscribe("masa_durumu_degisti")
async def on_masa_durumu_degisti(payload):
    await sio.emit("masa_durumu_degisti", payload)

@event_bus.subscribe("garson_onay_talebi")
async def on_garson_onay_talebi(payload):
    await sio.emit("garson_onay_talebi", payload)

@event_bus.subscribe("nakit_odeme_talebi")
async def on_nakit_odeme_talebi(payload):
    await sio.emit("nakit_odeme_talebi", payload)

@event_bus.subscribe("nakit_odendi")
async def on_nakit_odendi(payload):
    await sio.emit("nakit_odendi", payload)

@event_bus.subscribe("durum_guncellendi")
async def on_durum_guncellendi(payload):
    await sio.emit("durum_guncellendi", payload)

@event_bus.subscribe("masa_temizlendi")
async def on_masa_temizlendi(payload):
    await sio.emit("masa_temizlendi", payload)

