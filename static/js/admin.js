// ==========================================================================
// ADMIN PANEL LOGIC (KATEGORİ & ÜRÜN STOK YÖNETİMİ & FİLTRELEME)
// ==========================================================================

let currentSelectedCategoryFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
    loadAdminCategories();
    loadAdminProducts();
});

async function loadAdminCategories() {
    try {
        const res = await fetch('/api/kategoriler');
        const categories = await res.json();

        const tbody = document.getElementById('adminCategoriesTbody');
        const select = document.getElementById('adminProdCategorySelect');
        const filterSelect = document.getElementById('adminFilterCategorySelect');

        if (tbody) {
            let html = '';
            categories.forEach(cat => {
                html += `
                    <tr>
                        <td>#${cat.id}</td>
                        <td><strong>${cat.kategori_adi}</strong></td>
                        <td><button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteCategory(${cat.id})">Sil</button></td>
                    </tr>
                `;
            });
            tbody.innerHTML = html || '<tr><td colspan="3">Kategori yok.</td></tr>';
        }

        if (select) {
            let optHtml = '';
            categories.forEach(cat => {
                optHtml += `<option value="${cat.id}">${cat.kategori_adi}</option>`;
            });
            select.innerHTML = optHtml;
        }

        if (filterSelect) {
            let filterHtml = '<option value="all">🔍 Tüm Kategoriler (Tüm Ürünler)</option>';
            categories.forEach(cat => {
                filterHtml += `<option value="${cat.id}" ${currentSelectedCategoryFilter == cat.id ? 'selected' : ''}>📂 ${cat.kategori_adi}</option>`;
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

        const tbody = document.getElementById('adminProductsTbody');
        if (tbody) {
            let html = '';
            products.forEach(p => {
                html += `
                    <tr>
                        <td>#${p.id}</td>
                        <td><strong>${p.urun_adi}</strong></td>
                        <td><span style="background:rgba(99,102,241,0.15); color:#818cf8; border:1px solid #6366f1; padding:4px 10px; border-radius:12px; font-weight:800; font-size:0.82rem;">${p.kategori_adi || ''}</span></td>
                        <td><strong>${formatAdminPrice(p.fiyat)}</strong></td>
                        <td><span style="font-weight:800; color:${getStockColor(p.stok_miktari)}; font-size:1.05rem;">${p.stok_miktari}</span></td>
                        <td>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <input type="number" id="stockInput_${p.id}" value="${p.stok_miktari}" min="0" style="width:85px; padding:6px 8px; font-weight:800; text-align:center; border:1px solid var(--primary);">
                                <button class="btn-status-action btn-success" style="padding:6px 12px; font-size:0.82rem; font-weight:800;" onclick="updateProductStock(${p.id}, '${p.urun_adi.replace(/'/g, "\\'")}')">
                                    💾 Kaydet
                                </button>
                            </div>
                        </td>
                        <td><button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteProduct(${p.id})">Sil</button></td>
                    </tr>
                `;
            });
            tbody.innerHTML = html || '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted); font-weight:700;">Bu kategoride henüz ürün bulunmuyor.</td></tr>';
        }
    } catch (e) {
        console.error("Ürünler yüklenemedi:", e);
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

async function updateProductStock(urunId, urunAdi = "") {
    const input = document.getElementById(`stockInput_${urunId}`);
    if (!input) return;

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

async function deleteCategory(id) {
    const onaylandi = await appConfirm("Kategoriyi silmek istediğinizden emin misiniz?", {
        title: '🗑️ Kategoriyi Sil',
        okText: 'Evet, sil'
    });
    if (!onaylandi) return;
    await fetch(`/api/admin/kategoriler/${id}`, { method: 'DELETE' });
    showAdminToast(`🗑️ Kategori #${id} silindi.`);
    await loadAdminCategories();
    loadAdminProducts();
}

async function deleteProduct(id) {
    const onaylandi = await appConfirm("Ürünü silmek istediğinizden emin misiniz?", {
        title: '🗑️ Ürünü Sil',
        okText: 'Evet, sil'
    });
    if (!onaylandi) return;
    await fetch(`/api/admin/urunler/${id}`, { method: 'DELETE' });
    showAdminToast(`🗑️ Ürün #${id} silindi.`);
    loadAdminProducts();
}
