import asyncio
import logging
import socketio
from urllib.parse import parse_qs
from app.core.events import event_bus
from app.auth.tokens import decode_access_token, TokenValidationError, AuthConfigurationError
from app.enums import TokenType, UserRole
from app.database import DatabaseSession
from app.repositories.auth_repo import AuthRepository
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Socket.io Async Sunucusu Oluşturma.
# cors_allowed_origins bilinçli olarak verilmiyor: python-engineio varsayılanı
# "yalnızca same-origin". Önceki '*' değeri, main.py'deki kısıtlı CORS
# yapılandırmasını WebSocket yolunda etkisiz bırakıyordu. Same-origin varsayılanı
# telefonların LAN üzerinden bağlanmasını engellemez, çünkü sayfa ve soket aynı
# origin'den servis edilir.
sio = socketio.AsyncServer(async_mode='asgi')

# Masada menüyü inceleyen / sepete ürün ekleyen masaların sunucu tarafında takibi
BROWSING_TABLES = {}
SID_TO_MASA = {}
MASA_SESSIONS = {}

# Yayın hedefleri. Her personel soketi hem "staff" hem de kendi "role_*" odasındadır;
# bu yüzden tek bir emit çağrısında oda listesi verilir (socket.io alıcıları tekilleştirir).
# Aynı yayını hem role_* hem staff odasına ayrı ayrı göndermek olayın iki kez düşmesine yol açar.
ROOM_ALL_STAFF = "staff"
ROOM_SERVICE_STAFF = ["role_garson", "role_kasa", "role_admin"]  # mutfak hariç


def _extract_token_and_params(auth, environ):
    token = None
    masa_id_param = None

    if auth and isinstance(auth, dict):
        token = auth.get("token") or auth.get("Authorization") or auth.get("token_hash") or auth.get("access_token")
        if "masa_id" in auth:
            try:
                masa_id_param = int(auth["masa_id"])
            except (ValueError, TypeError):
                pass

    if "QUERY_STRING" in environ and environ["QUERY_STRING"]:
        qs = parse_qs(environ["QUERY_STRING"])
        if not token:
            for k in ("token", "access_token", "session_token", "auth_token"):
                if k in qs and qs[k]:
                    token = qs[k][0]
                    break
        if not masa_id_param and "masa_id" in qs and qs["masa_id"]:
            try:
                masa_id_param = int(qs["masa_id"][0])
            except (ValueError, TypeError):
                pass

    if token and isinstance(token, str) and token.startswith("Bearer "):
        token = token[7:].strip()

    return token, masa_id_param


def _coerce_masa_id(value) -> int | None:
    """Normalise a table id that arrived from an untrusted client payload."""
    try:
        masa_id = int(value)
    except (ValueError, TypeError):
        return None
    return masa_id if masa_id > 0 else None


@sio.event
async def connect(sid, environ, auth=None):
    # 1. Transport Upgrade (polling -> websocket) veya Reconnect: Var olan oturum yetkilerini anında koru
    existing = None
    try:
        existing = await sio.get_session(sid)
        if existing and isinstance(existing, dict) and existing.get("user_type") != "ANONYMOUS":
            if existing.get("user_type") == "STAFF":
                role_val = existing.get("role")
                if role_val:
                    await sio.enter_room(sid, f"role_{role_val}")
                    await sio.enter_room(sid, "staff")
                    logger.info(
                        "Personel oturumu korundu (Transport Upgrade/Reconnect): sid: %s, rol: %s",
                        sid,
                        role_val,
                    )
                    return
            elif existing.get("user_type") == "CUSTOMER":
                masa_id = existing.get("masa_id")
                if masa_id:
                    await sio.enter_room(sid, f"table_{masa_id}")
                    return
    except Exception:
        pass

    token, masa_id_param = _extract_token_and_params(auth, environ)
    masa_id_param = _coerce_masa_id(masa_id_param)
    auth_data = {"user_type": "ANONYMOUS", "masa_id": None, "claimed_masa_id": masa_id_param}

    if token:
        # 2. Staff JWT Token Kontrolü (Tamamen In-Memory HMAC Doğrulaması - Event Loop Bloklamaz)
        if len(token.split(".")) == 3:
            try:
                claims = decode_access_token(token, expected_type=TokenType.STAFF)
                role_val = claims.role.value
                await sio.enter_room(sid, f"role_{role_val}")
                await sio.enter_room(sid, "staff")
                auth_data = {
                    "user_type": "STAFF",
                    "role": role_val,
                    "user_id": claims.subject,
                    "username": f"User_{claims.subject}"
                }
                logger.info(
                    "Personel baglandi: ID %s (Rol: %s, sid: %s)", claims.subject, role_val, sid
                )
            except (TokenValidationError, AuthConfigurationError) as exc:
                logger.warning("Personel token dogrulama hatasi (sid: %s): %s", sid, exc)
            except Exception:
                logger.exception("Personel handshake beklenmeyen hata (sid: %s)", sid)

        # 3. Müşteri Session Token Kontrolü (Thread Executor ile DB Sorgusu - Event Loop Bloklamaz)
        else:
            try:
                db = DatabaseSession()
                repo = AuthRepository(db)
                service = AuthService(repo)
                customer_session = await asyncio.to_thread(service.verify_customer_session, token)
                if customer_session:
                    masa_id = int(customer_session["masa_id"])
                    await sio.enter_room(sid, f"table_{masa_id}")
                    SID_TO_MASA[sid] = masa_id
                    auth_data = {
                        "user_type": "CUSTOMER",
                        "masa_id": masa_id,
                        "session_token": token
                    }
                    logger.info("Musteri baglandi: Masa %s (sid: %s)", masa_id, sid)
            except Exception:
                logger.exception("Musteri session dogrulama hatasi (sid: %s)", sid)

    # 4. Anonim/Public İstemci.
    # Doğrulanmamış bir istemci ASLA table_* odasına alınmaz: o odalar sipariş
    # kalemleri, tutar ve ödeme durumu taşıyan olayları dağıtır. İstemcinin
    # gönderdiği masa_id yalnızca "bu masada biri menüye bakıyor" ipucu olarak
    # saklanır ve personele bildirim dışında hiçbir yetki vermez.
    if auth_data["user_type"] == "ANONYMOUS" and masa_id_param:
        logger.info(
            "Anonim istemci baglandi (masa odasina alinmadi): iddia edilen masa %s, sid: %s",
            masa_id_param,
            sid,
        )

    await sio.save_session(sid, auth_data)


@sio.event
async def disconnect(sid):
    logger.info("Istemci ayrildi: %s", sid)
    if sid in SID_TO_MASA:
        masa_id = SID_TO_MASA[sid]
        del SID_TO_MASA[sid]
        if masa_id in MASA_SESSIONS and sid in MASA_SESSIONS[masa_id]:
            MASA_SESSIONS[masa_id].remove(sid)
            if not MASA_SESSIONS[masa_id]:
                clear_browsing_table(masa_id)
                await sio.emit("masa_temizlendi", {"masa_id": masa_id}, room="staff")


async def _resolve_presence_masa_id(sid, data) -> int | None:
    """Resolve the table id for a presence hint.

    A verified customer session is authoritative. Otherwise the client-supplied
    value is used *only* to tell staff that somebody is browsing at that table;
    it never grants room membership, so a spoofed id can create a stray waiter
    notification but cannot expose another table's order data.
    """
    session = await sio.get_session(sid) or {}
    masa_id = session.get("masa_id")
    if masa_id:
        return _coerce_masa_id(masa_id)

    if isinstance(data, dict) and "masa_id" in data:
        return _coerce_masa_id(data["masa_id"])
    return _coerce_masa_id(session.get("claimed_masa_id"))


@sio.event
async def musteri_oturdu(sid, data):
    masa_id = await _resolve_presence_masa_id(sid, data)

    if masa_id:
        SID_TO_MASA[sid] = masa_id
        if masa_id not in MASA_SESSIONS:
            MASA_SESSIONS[masa_id] = set()
        MASA_SESSIONS[masa_id].add(sid)

        if masa_id not in BROWSING_TABLES:
            BROWSING_TABLES[masa_id] = {
                "masa_id": masa_id,
                "masa_no": (data and data.get("masa_no")) or f"Masa {masa_id}",
                "item_count": 0,
                "last_item": ""
            }

    event_payload = {
        "masa_id": masa_id,
        "masa_no": (data and data.get("masa_no")) or f"Masa {masa_id}"
    }
    await sio.emit("garson_musteri_geldi", event_payload, room=["role_garson", "role_admin"])


@sio.event
async def musteri_urun_secti(sid, data):
    masa_id = await _resolve_presence_masa_id(sid, data)

    if masa_id and data and isinstance(data, dict):
        item_count = data.get("item_count", 0)
        BROWSING_TABLES[masa_id] = {
            "masa_id": masa_id,
            "masa_no": data.get("masa_no", f"Masa {masa_id}"),
            "item_count": item_count,
            "last_item": data.get("last_item", "")
        }

    event_payload = {
        "masa_id": masa_id,
        "masa_no": (data and data.get("masa_no")) or f"Masa {masa_id}",
        "item_count": (data and data.get("item_count")) or 0,
        "last_item": (data and data.get("last_item")) or ""
    }
    await sio.emit("garson_musteri_urun_secti", event_payload, room=["role_garson", "role_admin"])


def get_browsing_tables():
    return BROWSING_TABLES


def clear_browsing_table(masa_id: int):
    if masa_id in BROWSING_TABLES:
        del BROWSING_TABLES[masa_id]


# --- EventBus Subscriptions (Oda İzoleli Yayınlar) ---

@event_bus.subscribe("yeni_siparis")
async def on_yeni_siparis(payload):
    # Mutfak dahil tüm personel rolleri hedefte olduğu için tek "staff" odası yeterli
    await sio.emit("yeni_siparis", payload, room=ROOM_ALL_STAFF)


@event_bus.subscribe("masa_durumu_degisti")
async def on_masa_durumu_degisti(payload):
    await sio.emit("masa_durumu_degisti", payload, room="staff")
    if isinstance(payload, dict) and "masa_id" in payload:
        try:
            masa_id = int(payload["masa_id"])
            await sio.emit("masa_durumu_degisti", payload, room=f"table_{masa_id}")
        except (ValueError, TypeError):
            pass


@event_bus.subscribe("garson_onay_talebi")
async def on_garson_onay_talebi(payload):
    await sio.emit("garson_onay_talebi", payload, room=ROOM_SERVICE_STAFF)


@event_bus.subscribe("nakit_odeme_talebi")
async def on_nakit_odeme_talebi(payload):
    await sio.emit("nakit_odeme_talebi", payload, room=ROOM_SERVICE_STAFF)


@event_bus.subscribe("nakit_odendi")
async def on_nakit_odendi(payload):
    await sio.emit("nakit_odendi", payload, room=ROOM_SERVICE_STAFF)


@event_bus.subscribe("durum_guncellendi")
async def on_durum_guncellendi(payload):
    await sio.emit("durum_guncellendi", payload, room="staff")

    masa_id = None
    if isinstance(payload, dict):
        if "masa_id" in payload:
            masa_id = payload["masa_id"]
        elif "siparis" in payload and isinstance(payload["siparis"], dict):
            masa_id = payload["siparis"].get("masa_id")

    if masa_id:
        try:
            m_id = int(masa_id)
            await sio.emit("durum_guncellendi", payload, room=f"table_{m_id}")
        except (ValueError, TypeError):
            pass


@event_bus.subscribe("stok_guncellendi")
async def on_stok_guncellendi(payload):
    """Stok adedini bağlı tüm istemcilere duyurur (oda ayrımı yok).

    Menüdeki "Son X Adet" / "Tükendi" rozetleri yalnızca sayfa açılışında ve
    dakikalık tazelemede güncelleniyordu, bu yüzden başka bir masanın verdiği
    sipariş komşu masanın ekranına bir dakikaya kadar yansımıyordu.

    Payload yalnızca `urun_id` ve `stok_miktari` taşır; ikisi de kimlik
    gerektirmeyen `GET /api/urunler` üzerinden zaten herkese açıktır. Bu yüzden
    müşteri masa odalarına ayrı ayrı yayın yapmak yerine tek genel yayın
    yeterlidir: masa odasında olmayan (henüz QR okutmamış) müşterinin menüsü de
    canlı kalmalıdır.
    """
    await sio.emit("stok_guncellendi", payload)


@event_bus.subscribe("masa_temizlendi")
async def on_masa_temizlendi(payload):
    await sio.emit("masa_temizlendi", payload, room="staff")
    if isinstance(payload, dict) and "masa_id" in payload:
        try:
            m_id = int(payload["masa_id"])
            await sio.emit("masa_temizlendi", payload, room=f"table_{m_id}")
        except (ValueError, TypeError):
            pass


@event_bus.subscribe("masa_tasindi")
async def on_masa_tasindi(payload):
    if isinstance(payload, dict) and "from_masa_id" in payload and "to_masa_id" in payload:
        try:
            from_id = int(payload["from_masa_id"])
            to_id = int(payload["to_masa_id"])

            if from_id in MASA_SESSIONS:
                sids = MASA_SESSIONS[from_id]
                if to_id not in MASA_SESSIONS:
                    MASA_SESSIONS[to_id] = set()
                MASA_SESSIONS[to_id].update(sids)
                del MASA_SESSIONS[from_id]

                for sid in sids:
                    SID_TO_MASA[sid] = to_id
                    await sio.leave_room(sid, f"table_{from_id}")
                    # Presence takibi anonim istemcileri de içerir; masa taşıma
                    # onları hedef masanın odasına sokmamalı. Aksi halde
                    # handshake'te kapatılan yetkisiz erişim buradan geri gelirdi.
                    session = await sio.get_session(sid) or {}
                    if session.get("user_type") == "CUSTOMER" and session.get("masa_id"):
                        await sio.enter_room(sid, f"table_{to_id}")

            if from_id in BROWSING_TABLES:
                data = BROWSING_TABLES.pop(from_id)
                data["masa_id"] = to_id
                data["masa_no"] = payload.get("to_masa_no", f"Masa {to_id}")
                BROWSING_TABLES[to_id] = data
        except Exception as e:
            logger.exception("Masa tasima sirasinda oturum guncellenemedi")

    await sio.emit("masa_tasindi", payload, room="staff")
    if isinstance(payload, dict) and "from_masa_id" in payload:
        try:
            f_id = int(payload["from_masa_id"])
            t_id = int(payload.get("to_masa_id", f_id))
            # Soketler yukarıda zaten yeni masaya taşındı; iki odayı tek çağrıda
            # hedeflemek taşınan müşteriye olayın iki kez düşmesini engeller.
            await sio.emit("masa_tasindi", payload, room=[f"table_{f_id}", f"table_{t_id}"])
        except (ValueError, TypeError):
            pass
