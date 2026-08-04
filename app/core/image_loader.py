import os
import shutil
import glob
from app.database import execute_non_query

ARTIFACT_DIR = r"C:\Users\emre\.gemini\antigravity-ide\brain\7b239df4-d331-4933-a911-a3a17294a682"
TARGET_BASE = r"c:\Users\emre\Desktop\QR odeme\static\img\urunler"

IMAGE_MAP = [
    # BURGERLER
    ("klasik_gurme_burger", "burgerler", "klasik_gurme_burger.jpg", ["Klasik Gurme Burger", "Barbeque Bacon Burger", "Acılı Jalapeño Burger", "Vejetaryen Mantar Burger"]),
    ("cheeseburger", "burgerler", "cheeseburger.jpg", ["Cheeseburger"]),
    ("double_smash_burger", "burgerler", "double_smash_burger.jpg", ["Double Smash Burger"]),
    ("citir_tavuk_burger", "burgerler", "citir_tavuk_burger.jpg", ["Çıtır Tavuk Burger"]),
    
    # PIZZALAR
    ("karisik_pizza", "pizzalar", "karisik_pizza.jpg", ["Karışık Pizza", "Karisik Pizza", "Vejetaryen Pizza", "Meksika Acılı Pizza"]),
    ("margherita_pizza", "pizzalar", "margherita_pizza.jpg", ["Margherita Pizza", "Dört Peynirli Pizza"]),
    ("pepperoni_pizza", "pizzalar", "pepperoni_pizza.jpg", ["Pepperoni Pizza", "Tavuklu Barbekü Pizza"]),
    
    # SALATALAR
    ("sezar_salata", "salatalar", "sezar_salata.jpg", ["Çıtır Tavuklu Sezar Salata", "Akdeniz Salatası", "Ton Balıklı Salata", "Izgara Hellim Peynirli Salata", "Gavurdağı Salatası", "Kinoa & Avokadolu Yeşil Salata", "Roka Parmesan Salatası"]),
    
    # TATLILAR
    ("kunefe", "tatlilar", "kunefe.jpg", ["Künefe"]),
    ("san_sebastian_cheesecake", "tatlilar", "san_sebastian.jpg", ["San Sebastian Cheesecake", "Tiramisu"]),
    ("havuc_dilim_baklava", "tatlilar", "havuc_dilim_baklava.jpg", ["Havuç Dilim Baklava", "Antep Fıstıklı Katmer", "Fırın Sütlaç", "Souffle", "Sufle"]),
    
    # İÇECEKLER
    ("ev_yapimi_limonata", "icecekler", "limonata.jpg", ["Ev Yapımı Limonata", "Fuse Tea (330ml)", "Şalgam Suyu (330ml)"]),
    ("ayran", "icecekler", "ayran.jpg", ["Ayran", "Küçük Ayran (200ml)", "Büyük Ayran (330ml)"]),
]

def sync_product_images():
    """Üretilen yüksek kaliteli ürün görsellerini static kopyalar ve DB gorsel_url alanlarını günceller."""
    for prefix, cat_dir, target_fn, prod_names in IMAGE_MAP:
        matches = glob.glob(os.path.join(ARTIFACT_DIR, f"{prefix}_*.png")) + glob.glob(os.path.join(ARTIFACT_DIR, f"{prefix}_*.jpg"))
        if not matches:
            continue
            
        latest_src = max(matches, key=os.path.getmtime)
        cat_folder = os.path.join(TARGET_BASE, cat_dir)
        os.makedirs(cat_folder, exist_ok=True)
        
        target_path = os.path.join(cat_folder, target_fn)
        try:
            shutil.copy2(latest_src, target_path)
            web_url = f"/static/img/urunler/{cat_dir}/{target_fn}"
            
            for p_name in prod_names:
                execute_non_query(
                    "UPDATE Urunler SET gorsel_url = ? WHERE urun_adi LIKE ?",
                    (web_url, f"%{p_name}%")
                )
        except Exception as e:
            print(f"Error copying {prefix}: {e}")
