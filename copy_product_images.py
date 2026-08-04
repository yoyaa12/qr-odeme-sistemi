import os
import shutil
from app.database import execute_non_query, db_transaction

artifact_dir = r"C:\Users\emre\.gemini\antigravity-ide\brain\4bef9a3d-27a2-454a-b1d4-0a4cf0282dc5"
base_target_dir = r"c:\Users\emre\Desktop\QR odeme\static\img\urunler"

mapping = {
    "Mercimek Çorbası": ("prod_mercimek_1785493503851.png", "corbalar", "mercimek_corbasi.png"),
    "Ezogelin Çorbası": ("prod_ezogelin_1785493521480.png", "corbalar", "ezogelin_corbasi.png"),
    "Karışık Pizza": ("prod_karisik_pizza_1785493539122.png", "pizzalar", "karisik_pizza.png"),
    "Margherita Pizza": ("prod_margherita_pizza_1785493557089.png", "pizzalar", "margherita_pizza.png")
}

with db_transaction():
    for prod_name, (src_file, sub_folder, dst_file) in mapping.items():
        src_path = os.path.join(artifact_dir, src_file)
        target_folder = os.path.join(base_target_dir, sub_folder)
        os.makedirs(target_folder, exist_ok=True)
        dst_path = os.path.join(target_folder, dst_file)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            gorsel_url = f"/static/img/urunler/{sub_folder}/{dst_file}"
            execute_non_query("UPDATE Urunler SET gorsel_url = ? WHERE urun_adi = ?", (gorsel_url, prod_name))
            print(f"Ürün '{prod_name}' görseli kopyalandı ve güncellendi: {gorsel_url}")
        else:
            print(f"Kaynak görsel bulunamadı: {src_path}")

print("=== ÜRÜN GÖRSELLERİ AKTARIMI TAMAMLANDI ===")
