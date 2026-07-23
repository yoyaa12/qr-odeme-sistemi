import sys
import os
import uvicorn

# Windows konsol UTF-8 kodlama ayarı
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"\n=======================================================")
    print(f" RESTORAN QR KODLU SIPARIS & OPERASYON SISTEMI BASLATILIYOR")
    print(f"=======================================================")
    print(f" - Ana Ekran (Giris) : http://localhost:{port}/")
    print(f" - Musteri QR Menusu : http://localhost:{port}/menu?masa=1")
    print(f" - Mutfak Paneli     : http://localhost:{port}/mutfak")
    print(f" - Garson Paneli     : http://localhost:{port}/garson")
    print(f" - Yönetici Paneli   : http://localhost:{port}/admin")
    print(f"=======================================================\n")
    
    uvicorn.run("app.main:app_asgi", host="0.0.0.0", port=port, reload=True)
