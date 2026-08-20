from fastapi import Depends, HTTPException
from typing import Optional, List
from app.core.events import event_bus
from app.repositories.kategori_repo import KategoriRepository
from app.repositories.urun_repo import UrunRepository
from app.schemas.catalog import UrunEkleModel, UrunGuncelleModel, UrunResponse
from app.database import db_transaction

class UrunService:
    def __init__(
        self,
        repo: UrunRepository = Depends(),
        kategori_repo: KategoriRepository = Depends(),
    ):
        self.repo = repo
        self.kategori_repo = kategori_repo

    def _assert_kategori_kullanilabilir(self, kategori_id: int) -> None:
        """Hedef kategorinin var ve menüde olduğunu doğrular.

        Menü sorgusu `k.aktif_mi = 1` koşulunu da uyguluyor: ürün, menüden
        kaldırılmış bir kategoriye taşınırsa kendisi aktif olsa bile listelenmez.
        Sessizce kaybolmak yerine istek reddedilir.
        """
        kategori = self.kategori_repo.get_by_id(kategori_id)
        if kategori is None:
            raise HTTPException(status_code=404, detail="Hedef kategori bulunamadı.")
        if not kategori.get("aktif_mi"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"'{kategori['kategori_adi']}' kategorisi menüden kaldırılmış "
                    "durumda; ürün oraya taşınırsa menüde görünmez."
                ),
            )

    def get_urunler(self, kategori_id: Optional[int] = None) -> List[UrunResponse]:
        urunler = self.repo.get_all(kategori_id)
        return [UrunResponse(**u) for u in urunler] if urunler else []

    def add_urun(self, data: UrunEkleModel) -> Optional[int]:
        with db_transaction():
            inserted_id = self.repo.create(data.kategori_id, data.urun_adi, data.aciklama, data.fiyat, data.gorsel_url, data.stok_miktari)
        return inserted_id

    async def update_urun(self, urun_id: int, data: UrunGuncelleModel) -> None:
        """Ürünün adını, kategorisini, fiyatını, açıklamasını ve stoğunu günceller.

        Gönderilmeyen alanlara dokunulmaz, böylece stok kutusu yalnızca
        `stok_miktari` göndererek çalışmaya devam eder.
        """
        if data.kategori_id is not None:
            self._assert_kategori_kullanilabilir(data.kategori_id)

        updates = {
            "urun_adi": data.urun_adi,
            "kategori_id": data.kategori_id,
            "fiyat": data.fiyat,
            "aciklama": data.aciklama,
            "stok_miktari": data.stok_miktari,
        }

        with db_transaction():
            etkilenen = self.repo.update(urun_id, updates)

        if etkilenen == 0:
            # Ya ürün yok ya da gönderilen gövdede güncellenecek hiçbir alan
            # yoktu. İkincisi istemci hatasıdır; ikisini de sessizce "başarılı"
            # saymak, düzenlemenin kaydedildiği yanılsamasını yaratırdı.
            if self.repo.get_by_id(urun_id) is None:
                raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
            raise HTTPException(
                status_code=400, detail="Güncellenecek en az bir alan gönderilmelidir."
            )

        # Admin stoğu elle değiştirdiğinde açık menülerdeki "Son X Adet" rozeti
        # de anında güncellenmelidir; aksi halde müşteri bir sonraki tazelemeye
        # kadar eski adedi görür.
        if data.stok_miktari is not None:
            await event_bus.publish(
                "stok_guncellendi",
                {"stoklar": [{"urun_id": urun_id, "stok_miktari": int(data.stok_miktari)}]},
            )

    def delete_urun(self, urun_id: int) -> None:
        """Ürünü menüden kaldırır.

        Kaldırma yumuşaktır (`aktif_mi = 0`): satır dururken ürün menüden
        çıkar ve sipariş edilemez hale gelir. Gerekçe `UrunRepository.deactivate`
        içinde — özeti, satılmış bir ürünü gerçekten silmenin hem FK ihlali
        (HTTP 500) hem de geçmiş adisyonlarda kalem-ürün bağının kopması
        anlamına gelmesi.
        """
        with db_transaction():
            etkilenen = self.repo.deactivate(urun_id)

        if etkilenen == 0:
            raise HTTPException(
                status_code=404, detail="Ürün bulunamadı veya zaten menüden kaldırılmış."
            )

    def get_kaldirilan_urunler(self) -> List[UrunResponse]:
        """Menüden kaldırılmış ürünler."""
        urunler = self.repo.get_inactive()
        return [UrunResponse(**u) for u in urunler] if urunler else []

    def restore_urun(self, urun_id: int) -> None:
        """Kaldırılmış ürünü menüye geri getirir.

        Ürünün kategorisi hâlâ kaldırılmışsa işlem reddedilir. Aksi halde
        "geri getirildi" denip menüde hiç görünmeyen bir ürün ortaya çıkardı:
        menü sorgusu `k.aktif_mi = 1` koşulunu da uyguluyor, yani pasif
        kategorinin ürünü aktif olsa bile listelenmez.
        """
        urun = self.repo.get_by_id(urun_id)
        if not urun:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı.")

        kategori = self.kategori_repo.get_by_id(urun["kategori_id"])
        if kategori and not kategori.get("aktif_mi"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Önce '{kategori['kategori_adi']}' kategorisini geri getirin; "
                    "kaldırılmış bir kategorinin ürünü menüde görünmez."
                ),
            )

        with db_transaction():
            etkilenen = self.repo.activate(urun_id)

        if etkilenen == 0:
            raise HTTPException(status_code=409, detail="Ürün zaten menüde.")
