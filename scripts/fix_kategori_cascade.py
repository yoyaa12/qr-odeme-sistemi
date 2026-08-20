"""`Urunler -> Kategoriler` foreign key'inin `ON DELETE CASCADE` kuralını kaldırır.

Neden gerekli:

`FK_Urunler_Kategoriler` bugüne kadar `ON DELETE CASCADE` ile tanımlıydı. Yani
bir kategori satırı silindiğinde SQL Server, o kategoriye ait BÜTÜN ürünleri
hiçbir uyarı vermeden siliyordu. 2026-08-20'de canlı veritabanında doğrulandı:
"İçecekler" kategorisini silme denemesi (rollback edilerek) 14 ürünü sildi.

Kural aynı zamanda tutarsız bir hataya da yol açıyordu. Silinen ürünlerden biri
daha önce sipariş edilmişse cascade `FK_SiparisDetaylari_Urunler` kuralına
(NO_ACTION) çarpıyor ve işlem `IntegrityError` ile düşüyordu. Yani aynı silme
işlemi, verinin durumuna göre bazen sessizce veri siliyor bazen HTTP 500
veriyordu.

Uygulama katmanı 2026-08-20'de yumuşak silmeye geçirildi: `KategoriRepository`
artık `DELETE` değil `UPDATE ... SET aktif_mi = 0` çalıştırıyor, dolayısıyla
cascade uygulama üzerinden tetiklenemiyor. Ancak kural veritabanında durduğu
sürece SSMS'ten veya bir bakım betiğinden atılan elle bir `DELETE FROM
Kategoriler` yine ürünleri siler. Bu betik o son riski kapatır.

Değişiklik sonrası davranış: ürünü olan bir kategoriyi gerçekten silmeye
çalışmak FK hatası verir. Doğru olan budur — menüden çıkarmak isteyen zaten
`aktif_mi = 0` yolunu kullanmalı.

Betik idempotenttir: kural zaten NO_ACTION ise hiçbir şey yapmaz.
Hiçbir satır silinmez veya değiştirilmez; yalnızca kısıt tanımı değişir.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import get_db_connection


FK_ADI = "FK_Urunler_Kategoriler"

DURUM_SORGUSU = """
    SELECT fk.name, fk.delete_referential_action_desc AS kural
    FROM sys.foreign_keys fk
    WHERE fk.name = ?
"""

# Kısıt tek adımda değiştirilemez: SQL Server'da bir FK'nın DELETE kuralını
# ALTER ile güncellemek mümkün değil, düşürüp yeniden kurmak gerekir. İkisi tek
# transaction içinde yapılır ki arada kısıtsız bir an oluşmasın.
DDL = """
ALTER TABLE dbo.Urunler DROP CONSTRAINT FK_Urunler_Kategoriler;

ALTER TABLE dbo.Urunler
ADD CONSTRAINT FK_Urunler_Kategoriler
    FOREIGN KEY (kategori_id) REFERENCES dbo.Kategoriler (id)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION;
"""


def main() -> int:
    conn, driver = get_db_connection(autocommit=False)
    print(f"Baglanti: {driver}")
    cursor = conn.cursor()

    try:
        cursor.execute(DURUM_SORGUSU, (FK_ADI,))
        row = cursor.fetchone()

        if row is None:
            print(f"HATA: '{FK_ADI}' adinda bir foreign key bulunamadi.")
            print("Sema beklenenden farkli; hicbir degisiklik yapilmadi.")
            conn.rollback()
            return 1

        mevcut_kural = row[1]
        print(f"Mevcut DELETE kurali: {mevcut_kural}")

        if mevcut_kural != "CASCADE":
            print("Kural zaten CASCADE degil. Yapilacak bir sey yok.")
            conn.rollback()
            return 0

        # Degisiklik oncesi kac urunun risk altinda oldugunu goster.
        cursor.execute(
            """
            SELECT COUNT(*) FROM Urunler u
            WHERE EXISTS (SELECT 1 FROM Kategoriler k WHERE k.id = u.kategori_id)
            """
        )
        risk_altinda = cursor.fetchone()[0]
        print(f"Cascade ile silinebilecek urun sayisi: {risk_altinda}")

        cursor.execute(DDL)
        conn.commit()
        print("FK_Urunler_Kategoriler artik ON DELETE NO ACTION.")

        # Commit sonrasi dogrulama.
        cursor.execute(DURUM_SORGUSU, (FK_ADI,))
        print(f"Dogrulama - yeni DELETE kurali: {cursor.fetchone()[1]}")
        return 0

    except Exception as exc:
        conn.rollback()
        print(f"HATA: {exc}")
        print("Degisiklik geri alindi; sema oldugu gibi kaldi.")
        return 1
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
