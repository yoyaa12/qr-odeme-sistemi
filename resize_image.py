import os
from PIL import Image

src = r"C:\Users\emre\.gemini\antigravity-ide\brain\5ab0b49b-c026-4d3d-97bf-2e9ab37e71e0\sezar_salata_1785747724320.png"
dest_dir = r"c:\Users\emre\Desktop\QR odeme\static\img\urunler\salatalar"
dest_file = os.path.join(dest_dir, "sezar_salata.jpg")

os.makedirs(dest_dir, exist_ok=True)

try:
    with Image.open(src) as img:
        # Resize to 500x500 for web performance
        img = img.resize((500, 500), Image.Resampling.LANCZOS)
        # Convert to RGB in case it's RGBA
        img = img.convert("RGB")
        # Save as JPG for better compression
        img.save(dest_file, "JPEG", quality=85)
    print(f"Başarıyla kaydedildi: {dest_file}")
except Exception as e:
    print(f"Hata: {e}")
