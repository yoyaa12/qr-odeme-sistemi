import hmac
import hashlib
import logging
import time
import secrets
from typing import Set

logger = logging.getLogger(__name__)

# Her zaman penceresi 30 saniyedir.
TOTP_WINDOW_SECONDS = 30

# Kaç pencere sapmaya izin verildiği. Bu değer doğrudan "fiziksel varlık kanıtı
# en fazla ne kadar eski olabilir" sorusunun cevabıdır.
#
# QR'daki kod istemci tarafında saklanıp ilk siparişte otomatik gönderiliyor
# (static/js/app.js). Yani tolerans, "QR'ı okutmakla siparişi vermek arasında
# geçebilecek süre" demek:
#   ±2 -> 60-89 saniye  (eski değer)
#   ±1 -> 30-59 saniye  (mevcut, ölçülmüş değerler)
# Aralığın alt ve üst ucu, QR'ın 30 saniyelik pencerenin neresinde okutulduğuna
# göre değişir: pencerenin başında okutulan kod 59, sonunda okutulan 30 saniye
# yaşar.
TOTP_WINDOW_TOLERANCE = 1

# Replay Attack Prevention: Güvenli şekilde doğrulanmış token'ları saklama
# Key: f"{masa_id}:{token}:{time_window}"
_used_tokens: Set[str] = set()
_last_cleanup_time: float = time.time()

def _cleanup_old_tokens():
    """Periyodik olarak 60 saniyeden eski kullanılmış token kayıtlarını temizler."""
    global _last_cleanup_time, _used_tokens
    now = time.time()
    if now - _last_cleanup_time > 60:
        current_window = int(now // TOTP_WINDOW_SECONDS)
        new_set = set()
        for token_entry in _used_tokens:
            try:
                parts = token_entry.split(":")
                if len(parts) >= 3:
                    w = int(parts[2])
                    # Kabul edilen aralıktan bir pencere fazlası tutulur; replay
                    # kaydı, token hâlâ kabul edilebilirken silinmemelidir.
                    if current_window - w <= TOTP_WINDOW_TOLERANCE + 1:
                        new_set.add(token_entry)
            except Exception:
                pass
        _used_tokens = new_set
        _last_cleanup_time = now

def generate_secret_key() -> str:
    """Her masa için 32 karakterlik rastgele gizli anahtar (totp_secret) üretir."""
    return secrets.token_hex(16)

def generate_dynamic_token(secret: str, timestamp: float = None) -> str:
    """
    30 saniyelik zaman penceresi için HMAC-SHA256 tabanlı 6 haneli dinamik token üretir.
    """
    if not secret:
        return "000000"
        
    if timestamp is None:
        timestamp = time.time()
        
    time_window = int(timestamp // TOTP_WINDOW_SECONDS)
    msg = str(time_window).encode('utf-8')
    key = secret.encode('utf-8')
    
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    
    # Dynamic Truncation & 6 Haneli sayıya dönüştürme
    offset = digest[-1] & 0x0F
    code = ((digest[offset] & 0x7F) << 24 |
            (digest[offset + 1] & 0xFF) << 16 |
            (digest[offset + 2] & 0xFF) << 8 |
            (digest[offset + 3] & 0xFF)) % 1000000
            
    return f"{code:06d}"

def get_seconds_remaining(timestamp: float = None) -> int:
    """Mevcut 30 saniyelik periyottan kaç saniye kaldığını döndürür."""
    if timestamp is None:
        timestamp = time.time()
    return TOTP_WINDOW_SECONDS - int(timestamp % TOTP_WINDOW_SECONDS)

def verify_dynamic_token(masa_id: int, secret: str, token: str, timestamp: float = None, mark_as_used: bool = True) -> bool:
    """
    Dinamik QR token'ını doğrular.
    - Replay Attack Koruması: Aynı token (mark_as_used=True ise) 2. kez kullanılamaz.
    - Zaman penceresi kontrolü: mevcut pencere ve ±TOTP_WINDOW_TOLERANCE pencere.
      Varsayılan ±1 ile bir kod, okutulduktan sonra 30-59 saniye geçerli kalır.
    """
    if not secret or not token:
        return False

    _cleanup_old_tokens()

    if timestamp is None:
        timestamp = time.time()

    current_window = int(timestamp // TOTP_WINDOW_SECONDS)

    # Mevcut pencere önce denenir, sonra simetrik olarak genişletilir.
    windows_to_check = [current_window]
    for offset in range(1, TOTP_WINDOW_TOLERANCE + 1):
        windows_to_check.append(current_window - offset)
        windows_to_check.append(current_window + offset)
    
    valid = False
    used_window = current_window
    
    for w in windows_to_check:
        token_entry = f"{masa_id}:{token}:{w}"
        if token_entry in _used_tokens:
            logger.warning(
                "Replay attack engellendi: masa %s, pencere %s", masa_id, w
            )
            continue

        ts = w * TOTP_WINDOW_SECONDS
        expected = generate_dynamic_token(secret, ts)
        if hmac.compare_digest(expected, str(token).strip()):
            valid = True
            used_window = w
            break
            
    if valid:
        if mark_as_used:
            # Doğrulanan token'ı kullanıldı olarak işaretle
            actual_entry = f"{masa_id}:{token}:{used_window}"
            _used_tokens.add(actual_entry)
        return True
        
    return False

