// ==========================================================================
// ADMIN PANEL LOGIC (KATEGORİ, ÜRÜN, MASA YÖNETİMİ)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadAdminCategories();
    loadAdminProducts();
    loadAdminTables();
});

async function loadAdminCategories() {
    try {
        const res = await fetch('/api/kategoriler');
        const categories = await res.json();
        
        const tbody = document.getElementById('adminCategoriesTbody');
        const select = document.getElementById('adminProdCategorySelect');
        
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
    } catch (e) {
        console.error("Kategoriler yüklenemedi:", e);
    }
}

async function loadAdminProducts() {
    try {
        const res = await fetch('/api/urunler');
        const products = await res.json();
        
        const tbody = document.getElementById('adminProductsTbody');
        if (tbody) {
            let html = '';
            products.forEach(p => {
                html += `
                    <tr>
                        <td>#${p.id}</td>
                        <td><strong>${p.urun_adi}</strong></td>
                        <td>${p.kategori_adi || ''}</td>
                        <td>${p.fiyat.toFixed(2)} ₺</td>
                        <td>${p.stok_miktari}</td>
                        <td><button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteProduct(${p.id})">Sil</button></td>
                    </tr>
                `;
            });
            tbody.innerHTML = html || '<tr><td colspan="6">Ürün yok.</td></tr>';
        }
    } catch (e) {
        console.error("Ürünler yüklenemedi:", e);
    }
}

async function loadAdminTables() {
    try {
        const res = await fetch('/api/masalar');
        const tables = await res.json();
        
        const tbody = document.getElementById('adminTablesTbody');
        if (tbody) {
            let html = '';
            tables.forEach(t => {
                html += `
                    <tr>
                        <td>#${t.id}</td>
                        <td><strong>${t.masa_no}</strong></td>
                        <td><code>${t.qr_kodu}</code></td>
                        <td><a href="/menu?masa=${t.id}" target="_blank" style="color:var(--primary); font-weight:700;">🔗 QR Menüyü Aç</a></td>
                        <td><button class="btn-status-action btn-warning" style="padding:6px 12px;" onclick="deleteTable(${t.id})">Sil</button></td>
                    </tr>
                `;
            });
            tbody.innerHTML = html || '<tr><td colspan="5">Masa yok.</td></tr>';
        }
    } catch (e) {
        console.error("Masalar yüklenemedi:", e);
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
    loadAdminCategories();
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
    loadAdminProducts();
}

async function handleAddTable(e) {
    e.preventDefault();
    const name = document.getElementById('newTableName').value.trim();
    if (!name) return;

    await fetch('/api/admin/masalar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ masa_no: name })
    });

    document.getElementById('newTableName').value = '';
    loadAdminTables();
}

async function deleteCategory(id) {
    if (!confirm("Kategoriyi silmek istediğinizden emin misiniz?")) return;
    await fetch(`/api/admin/kategoriler/${id}`, { method: 'DELETE' });
    loadAdminCategories();
}

async function deleteProduct(id) {
    if (!confirm("Ürünü silmek istediğinizden emin misiniz?")) return;
    await fetch(`/api/admin/urunler/${id}`, { method: 'DELETE' });
    loadAdminProducts();
}

async function deleteTable(id) {
    if (!confirm("Masayı silmek istediğinizden emin misiniz?")) return;
    await fetch(`/api/admin/masalar/${id}`, { method: 'DELETE' });
    loadAdminTables();
}
