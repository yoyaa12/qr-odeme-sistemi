UPDATE dbo.Kullanicilar
SET sifre_hash = ?
WHERE id = ?
  AND kullanici_adi = ?
  AND sifre_hash = ?;
