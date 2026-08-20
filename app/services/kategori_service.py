from fastapi import Depends, HTTPException
from typing import List, Optional
from app.repositories.kategori_repo import KategoriRepository
from app.repositories.urun_repo import UrunRepository
from app.schemas.catalog import KategoriResponse
from app.database import db_transaction

class KategoriService:
    def __init__(
        self,
        repo: KategoriRepository = Depends(),
        urun_repo: UrunRepository = Depends(),
    ):
        self.repo = repo
        self.urun_repo = urun_repo

    def get_kategoriler(self) -> List[KategoriResponse]:
        kategoriler = self.repo.get_all_active()
        return [KategoriResponse(**k) for k in kategoriler] if kategoriler else []

    def add_kategori(self, kategori_adi: str) -> Optional[int]:
        with db_transaction():
            inserted_id = self.repo.create(kategori_adi)
        return inserted_id

    def delete_kategori(self, kategori_id: int) -> int:
        """Kategoriyi ve altındaki ürünleri menüden kaldırır.

        Kaldırılan ürün sayısını döner.

        İki adım tek transaction içinde: kategori kapanır, altındaki aktif
        ürünler de kapanır. İkincisi olmazsa kategori listesinde karşılığı
        olmayan ürünler menüde asılı kalırdı.

        Bu, veritabanındaki `ON DELETE CASCADE` kuralının güvenli karşılığıdır.
        Fark, cascade'in satırları gerçekten silmesi ve bunu sessizce
        yapmasıydı: sipariş geçmişi olan bir ürün varsa işlem HTTP 500 ile
        düşüyor, yoksa ürünler geri dönüşsüz siliniyordu. Artık hiçbir satır
        silinmiyor ve kaç ürünün etkilendiği çağırana bildiriliyor.
        """
        with db_transaction():
            etkilenen_kategori = self.repo.deactivate(kategori_id)
            if etkilenen_kategori == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Kategori bulunamadı veya zaten menüden kaldırılmış.",
                )
            return self.urun_repo.deactivate_by_kategori(kategori_id)

    def get_kaldirilan_kategoriler(self) -> List[KategoriResponse]:
        """Menüden kaldırılmış kategoriler."""
        kategoriler = self.repo.get_inactive()
        return [KategoriResponse(**k) for k in kategoriler] if kategoriler else []

    def restore_kategori(self, kategori_id: int) -> int:
        """Kaldırılmış kategoriyi menüye geri getirir.

        Hâlâ kaldırılmış durumda kalan ürün sayısını döner.

        Kategoriyle birlikte ürünleri OTOMATİK geri getirilmez. Kaldırma
        sırasında kategorinin ürünleri kapatılmıştı, ama o kategoride daha önce
        tek tek kaldırılmış ürünler de olabilir; hepsini toplu açmak,
        yöneticinin bilerek menüden çıkardığı ürünleri geri diriltirdi. Hangi
        ürünün geri geleceğine yönetici tek tek karar verir.
        """
        with db_transaction():
            etkilenen = self.repo.activate(kategori_id)

        if etkilenen == 0:
            raise HTTPException(
                status_code=404, detail="Kategori bulunamadı veya zaten menüde."
            )

        return self.urun_repo.count_inactive_by_kategori(kategori_id)
