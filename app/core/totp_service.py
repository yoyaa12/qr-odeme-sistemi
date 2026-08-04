import hmac
import hashlib
import time
import secrets
from typing import Dict, Set

# Replay Attack Prevention: Güvenli şekilde doğrulanmış token'ları saklama
# Key: f"{masa_id}:{token}:{time_window}"
_used_tokens: Set[str] = set()
_last_cleanup_time: float = time.time()

def _cleanup_old_tokens():
    """Periyodik olarak 60 saniyeden eski kullanılmış token kayıtlarını temizler."""
    global _last_cleanup_time, _used_tokens
    now = time.time()
    if now - _last_cleanup_time > 60:
        current_window = int(now // 30)
        new_set = set()
        for token_entry in _used_tokens:
            try:
                parts = token_entry.split(":")
                if len(parts) >= 3:
                    w = int(parts[2])
                    if current_window - w <= 2:
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
        
    time_window = int(timestamp // 30)
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
    return 30 - int(timestamp % 30)

def verify_dynamic_token(masa_id: int, secret: str, token: str, timestamp: float = None) -> bool:
    """
    Dinamik QR token'ını doğrular.
    - Replay Attack Koruması: Aynı token 30s içinde 2. kez kullanılamaz.
    - 30 Saniyelik Zaman Penceresi kontrolü.
    """
    if not secret or not token:
        return False
        
    _cleanup_old_tokens()
    
    if timestamp is None:
        timestamp = time.time()
        
    current_window = int(timestamp // 30)
    
    # 1. Replay Attack Kontrolü
    token_entry = f"{masa_id}:{token}:{current_window}"
    if token_entry in _used_tokens:
        print(f"[SECURITY GUARD] Replay attack detected for Table {masa_id} with token {token}")
        return False

    # 2. Zaman Penceresi Kontrolü (Mevcut window ve ±1 window toleransı)
    windows_to_check = [current_window, current_window - 1, current_window + 1]
    
    valid = False
    used_window = current_window
    
    for w in windows_to_check:
        ts = w * 30
        expected = generate_dynamic_token(secret, ts)
        if hmac.compare_digest(expected, token):
            valid = True
            used_window = w
            break
            
    if valid:
        # Doğrulanan token'ı kullanıldı olarak işaretle
        actual_entry = f"{masa_id}:{token}:{used_window}"
        _used_tokens.add(actual_entry)
        return True
        
    return False
