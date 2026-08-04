import os
import shutil
from app.database import execute_non_query, db_transaction

artifact_dir = r"C:\Users\emre\.gemini\antigravity-ide\brain\4bef9a3d-27a2-454a-b1d4-0a4cf0282dc5"
dst_path = r"c:\Users\emre\Desktop\QR odeme\static\img\urunler\corbalar\domates_corbasi.png"
src_path = os.path.join(artifact_dir, "prod_domates_1785498355342.png")

with db_transaction():
    if os.path.exists(src_path):
        shutil.copy2(src_path, dst_path)
        gorsel_url = "/static/img/urunler/corbalar/domates_corbasi.png"
        execute_non_query("UPDATE Urunler SET gorsel_url = ? WHERE urun_adi = 'Domates Çorbası'", (gorsel_url,))
        print(f"Domates Çorbası görseli güncellendi: {gorsel_url}")
    else:
        print(f"Bulunamadı: {src_path}")
