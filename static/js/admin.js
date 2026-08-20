// ==========================================================================
// ADMIN PANEL LOGIC (KATEGORİ & ÜRÜN STOK YÖNETİMİ & FİLTRELEME)
// ==========================================================================

// Diğer panellerle aynı kaynak: `static/js/security.js`. Kategori ve ürün
// adları yöneticinin serbest metin girdisidir; `innerHTML` ile basıldıkları için
// kaçış yapılmadan yazmak, adın içine konan bir etiketin panelde çalışması
// anlamına gelirdi.
const escapeHtml = window.SecurityText.escapeHtml;

let currentSelectedCategoryFilter = 'all';

// Son yüklenen liste. Düzenleme moduna girip çıkmak sunucuya gitmeden yeniden
// çizim yapabilsin diye tutuluyor.
let adminProducts = [];
// Kategori seçim kutusunu düzenleme satırında da kurabilmek için önbellek.
let adminCategories = [];
// Aynı anda yalnızca bir satır düzenlenir; `null` ise hiçbiri.
let editingProductId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadAdminCategories();
    loadAdminProducts();
    loadRemovedMenuItems();
});

async function loadAdminCategories() {
    try {
        const res = await fetch('/api/kategoriler');
        const categories = await res.json();
        adminCategories = Array.isArray(categories) ? categories : [];

        const tbody = document.getElementById('adminCategoriesTbody');
        const select = document.getElementById('adminProdCategorySelect');
        const filterSelect = document.getElementById('adminFilterCategorySelect');

        if (tbody) {
            let html = '';
            categories.forEach(cat => {
                html += `
                    <tr>
                        <td>#${cat.id}</td>
                        <td><strong>${escapeHtml(cat.kategori_adi)}</strong></td>
                        <td><button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteCategory(${cat.id})">Sil</button></td>
                    </tr>
                `;
            });
            tbody.innerHTML = html || '<tr><td colspan="3">Kategori yok.</td></tr>';
        }

        if (select) {
            let optHtml = '';
            categories.forEach(cat => {
                optHtml += `<option value="${cat.id}">${escapeHtml(cat.kategori_adi)}</option>`;
            });
            select.innerHTML = optHtml;
        }

        if (filterSelect) {
            let filterHtml = '<option value="all">🔍 Tüm Kategoriler (Tüm Ürünler)</option>';
            categories.forEach(cat => {
                filterHtml += `<option value="${cat.id}" ${currentSelectedCategoryFilter == cat.id ? 'selected' : ''}>📂 ${escapeHtml(cat.kategori_adi)}</option>`;
            });
            filterSelect.innerHTML = filterHtml;
        }
    } catch (e) {
        console.error("Kategoriler yüklenemedi:", e);
    }
}

let currentSortField = null; // 'fiyat' or 'stok_miktari'
let currentSortOrder = 'asc'; // 'asc' (küçükten büyüğe) or 'desc' (büyükten küçüğe)

function toggleAdminSort(field) {
    if (currentSortField === field) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortField = field;
        currentSortOrder = 'asc';
    }
    updateSortHeaderIcons();
    loadAdminProducts();
}

function updateSortHeaderIcons() {
    const fiyatIcon = document.getElementById('sortFiyatIcon');
    const stokIcon = document.getElementById('sortStokIcon');

    if (fiyatIcon) {
        if (currentSortField === 'fiyat') {
            fiyatIcon.innerHTML = currentSortOrder === 'asc' ? ' ▲' : ' ▼';
            fiyatIcon.style.opacity = '1';
        } else {
            fiyatIcon.innerHTML = ' ↕';
            fiyatIcon.style.opacity = '0.5';
        }
    }
    if (stokIcon) {
        if (currentSortField === 'stok_miktari') {
            stokIcon.innerHTML = currentSortOrder === 'asc' ? ' ▲' : ' ▼';
            stokIcon.style.opacity = '1';
        } else {
            stokIcon.innerHTML = ' ↕';
            stokIcon.style.opacity = '0.5';
        }
    }
}

function formatAdminPrice(price) {
    if (price === null || price === undefined) return '0 ₺';
    const num = Number(price);
    if (isNaN(num)) return '0 ₺';
    return (num % 1 === 0) ? `${num.toFixed(0)} ₺` : `${num.toFixed(2)} ₺`;
}

function getStockColor(stock) {
    const s = Number(stock) || 0;
    if (s < 20) {
        return '#ef4444'; // 20'den az -> Kırmızı
    } else if (s <= 50) {
        return '#f59e0b'; // 20 - 50 arası -> Sarı
    } else {
        return '#10b981'; // 50 - 100 arası (ve üzeri) -> Yeşil
    }
}

async function loadAdminProducts(kategoriId = null) {
    // Tam yenileme her zaman düzenleme modundan çıkar. Aksi halde açık bir form,
    // altındaki veri değiştikten sonra hâlâ eski değerleri gösterirdi.
    editingProductId = null;

    if (kategoriId !== null) {
        currentSelectedCategoryFilter = kategoriId;
    } else {
        const filterSelect = document.getElementById('adminFilterCategorySelect');
        if (filterSelect && filterSelect.value) {
            currentSelectedCategoryFilter = filterSelect.value;
        }
    }

    try {
        let url = '/api/urunler';
        if (currentSelectedCategoryFilter && currentSelectedCategoryFilter !== 'all') {
            url += `?kategori_id=${currentSelectedCategoryFilter}`;
        }
        const res = await fetch(url);
        let products = await res.json();

        // Fiyat veya Stok Miktarına Göre Sıralama (Küçükten Büyüğe / Büyükten Küçüğe)
        if (currentSortField) {
            products.sort((a, b) => {
                let valA = Number(a[currentSortField]) || 0;
                let valB = Number(b[currentSortField]) || 0;
                return currentSortOrder === 'asc' ? valA - valB : valB - valA;
            });
        }

        // Satırlar önbellekten çizilir. Düzenleme moduna girip çıkmak yalnızca
        // yeniden çizim gerektirir; her seferinde sunucuya gitmek, kullanıcının
        // yazdıklarını kaybettirecek bir gecikme yaratırdı.
        adminProducts = products;
        renderAdminProductsTable();
    } catch (e) {
        console.error("Ürünler yüklenemedi:", e);
    }
}

function renderAdminProductsTable() {
    const tbody = document.getElementById('adminProductsTbody');
    if (!tbody) return;

    const html = adminProducts
        .map(p => (p.id === editingProductId ? renderProductEditRow(p) : renderProductRow(p)))
        .join('');

    tbody.innerHTML = html || '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted); font-weight:700;">Bu kategoride henüz ürün bulunmuyor.</td></tr>';
}

function renderProductRow(p) {
    return `
        <tr>
            <td>#${p.id}</td>
            <td><strong>${escapeHtml(p.urun_adi)}</strong></td>
            <td><span style="background:rgba(99,102,241,0.15); color:#818cf8; border:1px solid #6366f1; padding:4px 10px; border-radius:12px; font-weight:800; font-size:0.82rem;">${escapeHtml(p.kategori_adi || '')}</span></td>
            <td><strong>${formatAdminPrice(p.fiyat)}</strong></td>
            <td><span style="font-weight:800; color:${getStockColor(p.stok_miktari)}; font-size:1.05rem;">${p.stok_miktari}</span></td>
            <td>
                <div style="display:flex; gap:6px; align-items:center;">
                    <input type="number" id="stockInput_${p.id}" data-urun-adi="${escapeHtml(p.urun_adi)}" value="${p.stok_miktari}" min="0" style="width:85px; padding:6px 8px; font-weight:800; text-align:center; border:1px solid var(--primary);">
                    <button class="btn-status-action btn-success" style="padding:6px 12px; font-size:0.82rem; font-weight:800;" onclick="updateProductStock(${p.id})">
                        💾 Kaydet
                    </button>
                </div>
            </td>
            <td>
                <div style="display:flex; gap:6px;">
                    <button class="btn-status-action" style="padding:6px 12px;" onclick="startEditProduct(${p.id})">Düzenle</button>
                    <button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteProduct(${p.id})">Sil</button>
                </div>
            </td>
        </tr>
    `;
}

function renderProductEditRow(p) {
    // Kategori seçenekleri `loadAdminCategories`'in önbelleğinden gelir; listede
    // yalnızca menüde duran kategoriler vardır. Ürünün mevcut kategorisi
    // kaldırılmışsa listede olmayacağı için ilk seçenek işaretli görünür —
    // sunucu da o durumda taşımayı zaten 409 ile reddeder.
    const kategoriSecenekleri = adminCategories
        .map(cat => `<option value="${cat.id}" ${cat.id === p.kategori_id ? 'selected' : ''}>${escapeHtml(cat.kategori_adi)}</option>`)
        .join('');

    const kutuStili = 'width:100%; padding:6px 8px; font-weight:700; border:1px solid var(--primary);';

    return `
        <tr style="background: rgba(99,102,241,0.08);">
            <td>#${p.id}</td>
            <td><input type="text" id="editName_${p.id}" value="${escapeHtml(p.urun_adi)}" maxlength="100" style="${kutuStili} min-width:160px;"></td>
            <td><select id="editCategory_${p.id}" style="${kutuStili} min-width:130px;">${kategoriSecenekleri}</select></td>
            <td><input type="number" id="editPrice_${p.id}" value="${Number(p.fiyat)}" min="0" step="0.5" style="${kutuStili} width:100px;"></td>
            <td><input type="number" id="editStock_${p.id}" value="${Number(p.stok_miktari)}" min="0" step="1" style="${kutuStili} width:100px;"></td>
            <td style="text-align:center; color:var(--text-muted);">—</td>
            <td>
                <div style="display:flex; gap:6px;">
                    <button class="btn-status-action btn-success" style="padding:6px 12px;" onclick="saveEditProduct(${p.id})">💾 Kaydet</button>
                    <button class="btn-status-action" style="padding:6px 12px;" onclick="cancelEditProduct()">İptal</button>
                </div>
            </td>
        </tr>
        <tr style="background: rgba(99,102,241,0.08);">
            <td colspan="7" style="padding-top:0;">
                <label for="editDesc_${p.id}" style="display:block; font-size:0.78rem; color:#94a3b8; font-weight:700; margin-bottom:4px;">
                    Açıklama <span style="opacity:0.7;">(boş bırakılabilir)</span>
                </label>
                <input type="text" id="editDesc_${p.id}" value="${escapeHtml(p.aciklama || '')}" maxlength="500"
                       placeholder="Müşteri menüsünde ürünün altında görünür"
                       style="${kutuStili} width:100%;">
            </td>
        </tr>
    `;
}

function startEditProduct(urunId) {
    // Aynı anda tek satır düzenlenir: birden çok açık form, hangisinin
    // kaydedilmediğini takip etmeyi zorlaştırırdı.
    editingProductId = urunId;
    renderAdminProductsTable();
    const nameInput = document.getElementById(`editName_${urunId}`);
    if (nameInput) nameInput.focus();
}

function cancelEditProduct() {
    editingProductId = null;
    renderAdminProductsTable();
}

async function saveEditProduct(urunId) {
    const nameInput = document.getElementById(`editName_${urunId}`);
    const categorySelect = document.getElementById(`editCategory_${urunId}`);
    const priceInput = document.getElementById(`editPrice_${urunId}`);
    const stockInput = document.getElementById(`editStock_${urunId}`);
    const descInput = document.getElementById(`editDesc_${urunId}`);
    if (!nameInput || !categorySelect || !priceInput || !stockInput || !descInput) return;

    const urunAdi = nameInput.value.trim();
    // Boş açıklama `null` değil boş metin olarak gönderilir: `null` "dokunma",
    // `""` ise "bilerek boşalt" anlamına geliyor.
    const aciklama = descInput.value.trim();
    const fiyat = Number(priceInput.value);
    const stok = parseInt(stockInput.value, 10);
    const kategoriId = parseInt(categorySelect.value, 10);

    // Sunucu bu kuralların hepsini yeniden uygular (`UrunGuncelleModel`); buradaki
    // kontroller yalnızca kullanıcıyı bir gidiş-dönüş beklemekten kurtarır.
    if (!urunAdi) {
        showAdminToast("⚠️ Ürün adı boş olamaz.", true);
        return;
    }
    if (isNaN(fiyat) || fiyat < 0) {
        showAdminToast("⚠️ Fiyat geçerli ve negatif olmayan bir sayı olmalıdır.", true);
        return;
    }
    if (isNaN(stok) || stok < 0) {
        showAdminToast("⚠️ Stok geçerli ve negatif olmayan bir tam sayı olmalıdır.", true);
        return;
    }

    try {
        const res = await fetch(`/api/admin/urunler/${urunId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                urun_adi: urunAdi,
                kategori_id: kategoriId,
                fiyat: fiyat,
                stok_miktari: stok,
                aciklama: aciklama
            })
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            // 409: hedef kategori menüden kaldırılmış. Sunucunun mesajı ne
            // yapılması gerektiğini söylüyor, olduğu gibi gösteriliyor.
            showAdminToast("❌ " + (data.detail || "Ürün güncellenemedi."), true);
            return;
        }

        editingProductId = null;
        showAdminToast(`✅ "${urunAdi}" güncellendi.`);
        loadAdminProducts();
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}

function filterAdminProducts() {
    const select = document.getElementById('adminFilterCategorySelect');
    if (!select) return;
    loadAdminProducts(select.value);
}

function showAdminToast(msg, isError = false) {
    let container = document.getElementById('adminToastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'adminToastContainer';
        container.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            z-index: 99999;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.style.cssText = `
        background: #18181b;
        color: #ffffff;
        padding: 16px 28px;
        border-radius: 14px;
        font-weight: 700;
        font-size: 1.05rem;
        border: 2px solid ${isError ? '#ef4444' : '#3f3f46'};
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85);
        pointer-events: auto;
        opacity: 0;
        transform: scale(0.85);
        transition: opacity 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        white-space: nowrap;
    `;
    toast.innerText = msg;
    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'scale(1)';
    });

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'scale(0.85)';
        setTimeout(() => toast.remove(), 250);
    }, 2200);
}

async function updateProductStock(urunId) {
    const input = document.getElementById(`stockInput_${urunId}`);
    if (!input) return;

    // Ürün adı eskiden `onclick` özniteliğinin içine JS string literali olarak
    // gömülüyordu: çift tırnaklı bir HTML özniteliğinin içinde tek tırnaklı bir
    // JS string. Adın içindeki bir çift tırnak özniteliği kapatabiliyordu ve
    // oradaki kaçış yalnızca tek tırnağı ele alıyordu. `data-` özniteliği bu iç
    // içe geçmeyi tamamen ortadan kaldırır.
    const urunAdi = input.dataset.urunAdi || "";

    const newStock = parseInt(input.value);
    if (isNaN(newStock) || newStock < 0) {
        showAdminToast("⚠️ Lütfen geçerli ve pozitif bir stok miktarı giriniz.", true);
        return;
    }

    try {
        const res = await fetch(`/api/admin/urunler/${urunId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stok_miktari: newStock })
        });

        if (res.ok) {
            const displayName = urunAdi ? `"${urunAdi}"` : `Ürün #${urunId}`;
            showAdminToast(`✅ ${displayName} stok miktarı ${newStock} olarak güncellendi!`);
            loadAdminProducts();
        } else {
            const data = await res.json().catch(() => ({}));
            showAdminToast("❌ Stok güncellenirken hata oluştu: " + (data.detail || "Sunucu hatası"), true);
        }
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}

async function handleAddCategory(e) {
    e.preventDefault();
    const name = document.getElementById('newCategoryName').value.trim();
    if (!name) return;

    await fetch('/api/admin/kategoriler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kategori_adi: name })
    });

    document.getElementById('newCategoryName').value = '';
    showAdminToast(`✅ "${name}" kategorisi başarıyla eklendi!`);
    await loadAdminCategories();
}

async function handleAddProduct(e) {
    e.preventDefault();
    const catId = parseInt(document.getElementById('adminProdCategorySelect').value);
    const name = document.getElementById('newProdName').value.trim();
    const desc = document.getElementById('newProdDesc').value.trim();
    const price = parseFloat(document.getElementById('newProdPrice').value);
    const stock = parseInt(document.getElementById('newProdStock').value) || 100;

    if (!name || isNaN(price)) return;

    await fetch('/api/admin/urunler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            kategori_id: catId,
            urun_adi: name,
            aciklama: desc,
            fiyat: price,
            stok_miktari: stock
        })
    });

    document.getElementById('newProdName').value = '';
    document.getElementById('newProdDesc').value = '';
    document.getElementById('newProdPrice').value = '';
    showAdminToast(`✅ "${name}" ürünü başarıyla eklendi!`);
    loadAdminProducts();
}

// Kaldırma işlemleri sunucuda "yumuşak" yapılır: satır sipariş geçmişi için
// durmaya devam eder, kayıt yalnızca menüden çıkar. Bu yüzden mesajlarda
// "silindi" yerine "menüden kaldırıldı" deniyor.
//
// Her iki fonksiyon da eskiden yanıtı hiç okumuyordu ve koşulsuz "silindi"
// yazıyordu. Sunucu FK ihlali yüzünden HTTP 500 döndüğünde bile yönetici
// başarı mesajı görüyor, ürün ise yerinde duruyordu.
async function deleteCategory(id) {
    const onaylandi = await appConfirm(
        "Kategori ve içindeki tüm ürünler menüden kaldırılacak. Devam edilsin mi?",
        {
            title: '🗑️ Kategoriyi Kaldır',
            okText: 'Evet, kaldır'
        }
    );
    if (!onaylandi) return;

    try {
        const res = await fetch(`/api/admin/kategoriler/${id}`, { method: 'DELETE' });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            showAdminToast("❌ Kategori kaldırılamadı: " + (data.detail || "Sunucu hatası"), true);
            return;
        }

        showAdminToast("🗑️ " + (data.message || `Kategori #${id} menüden kaldırıldı.`));
        await loadAdminCategories();
        loadAdminProducts();
        loadRemovedMenuItems();
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}

async function deleteProduct(id) {
    const onaylandi = await appConfirm("Ürün menüden kaldırılacak. Devam edilsin mi?", {
        title: '🗑️ Ürünü Kaldır',
        okText: 'Evet, kaldır'
    });
    if (!onaylandi) return;

    try {
        const res = await fetch(`/api/admin/urunler/${id}`, { method: 'DELETE' });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            showAdminToast("❌ Ürün kaldırılamadı: " + (data.detail || "Sunucu hatası"), true);
            return;
        }

        showAdminToast("🗑️ " + (data.message || `Ürün #${id} menüden kaldırıldı.`));
        loadAdminProducts();
        loadRemovedMenuItems();
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}


// --- Menüden kaldırılanlar ---------------------------------------------------
//
// Kaldırma sunucuda yumuşak yapılır (aktif_mi = 0), yani kayıt veritabanında
// durur. Bu bölüm olmadan geri getirmenin tek yolu veritabanına elle
// müdahale etmekti.

async function loadRemovedMenuItems() {
    const section = document.getElementById('removedSection');
    if (!section) return;

    try {
        const res = await fetch('/api/admin/menu/kaldirilanlar');
        if (!res.ok) {
            section.style.display = 'none';
            return;
        }
        const data = await res.json();
        const kategoriler = data.kategoriler || [];
        const urunler = data.urunler || [];

        // Kaldırılmış hiçbir kayıt yoksa bölüm tamamen gizlenir; boş bir tablo
        // göstermek paneli gereksiz kalabalıklaştırırdı.
        section.style.display = (kategoriler.length || urunler.length) ? 'block' : 'none';

        const catWrap = document.getElementById('removedCategoriesWrap');
        const catTbody = document.getElementById('removedCategoriesTbody');
        if (catWrap && catTbody) {
            catWrap.style.display = kategoriler.length ? 'block' : 'none';
            catTbody.innerHTML = kategoriler.map(cat => `
                <tr>
                    <td>#${cat.id}</td>
                    <td><strong>${escapeHtml(cat.kategori_adi)}</strong></td>
                    <td><button class="btn-status-action" style="padding:6px 12px;" onclick="restoreCategory(${cat.id})">Geri Getir</button></td>
                </tr>
            `).join('');
        }

        const prodWrap = document.getElementById('removedProductsWrap');
        const prodTbody = document.getElementById('removedProductsTbody');
        if (prodWrap && prodTbody) {
            prodWrap.style.display = urunler.length ? 'block' : 'none';
            prodTbody.innerHTML = urunler.map(u => `
                <tr>
                    <td>#${u.id}</td>
                    <td><strong>${escapeHtml(u.urun_adi)}</strong></td>
                    <td>${escapeHtml(u.kategori_adi || '-')}</td>
                    <td>${Number(u.fiyat).toFixed(2)} ₺</td>
                    <td><button class="btn-status-action" style="padding:6px 12px;" onclick="restoreProduct(${u.id})">Geri Getir</button></td>
                </tr>
            `).join('');
        }
    } catch (e) {
        section.style.display = 'none';
    }
}

async function restoreCategory(id) {
    try {
        const res = await fetch(`/api/admin/kategoriler/${id}/geri-yukle`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            showAdminToast("❌ Kategori geri getirilemedi: " + (data.detail || "Sunucu hatası"), true);
            return;
        }

        showAdminToast("♻️ " + (data.message || `Kategori #${id} menüye geri getirildi.`));
        await loadAdminCategories();
        loadAdminProducts();
        loadRemovedMenuItems();
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}

async function restoreProduct(id) {
    try {
        const res = await fetch(`/api/admin/urunler/${id}/geri-yukle`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            // 409: kategorisi hâlâ kaldırılmış. Sunucunun mesajı ne yapılması
            // gerektiğini söylüyor, olduğu gibi gösteriliyor.
            showAdminToast("❌ " + (data.detail || "Ürün geri getirilemedi."), true);
            return;
        }

        showAdminToast("♻️ " + (data.message || `Ürün #${id} menüye geri getirildi.`));
        loadAdminProducts();
        loadRemovedMenuItems();
    } catch (e) {
        showAdminToast("❌ Sunucuya ulaşılamadı.", true);
    }
}
