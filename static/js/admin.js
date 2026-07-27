// ==========================================================================
// ADMIN PANEL LOGIC (KATEGORİ, ÜRÜN, MASA YÖNETİMİ)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadAdminCategories();
    loadAdminProducts();
    loadAdminTables();
    loadKasaTables();
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
    loadKasaTables();
}

async function loadKasaTables() {
    try {
        const [tablesRes, ordersRes] = await Promise.all([
            fetch('/api/masalar'),
            fetch('/api/siparisler')
        ]);
        const tables = await tablesRes.json();
        const orders = await ordersRes.json();
        
        const container = document.getElementById('kasaTablesGrid');
        if (!container) return;

        let html = '';
        tables.forEach(t => {
            const masaOrders = orders.filter(o => o.masa_id === t.id && ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
            const totalBill = masaOrders.reduce((sum, o) => sum + o.toplam_tutar, 0);
            const isDolu = t.durum === 'dolu' || masaOrders.length > 0;

            html += `
                <div class="order-card" style="border-color: ${isDolu ? '#f59e0b' : 'rgba(255,255,255,0.1)'};">
                    <div class="order-header">
                        <div class="order-table-title">🪑 ${t.masa_no}</div>
                        <span class="table-badge" style="background:${isDolu ? '#f59e0b' : '#10b981'}; color:#fff; font-weight:800;">
                            ${isDolu ? '🔴 DOLU (Aktif Masa)' : '🟢 BOŞ'}
                        </span>
                    </div>
                    <div style="margin: 10px 0; font-size:1.1rem; font-weight:800; color:#fbbf24;">
                        Toplam Adisyon Tutarı: ${totalBill.toFixed(2)} ₺
                    </div>
                    <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:12px;">
                        Aktif Sipariş Sayısı: ${masaOrders.length} Adet
                    </div>
                    ${isDolu ? `
                        <button class="btn-status-action btn-danger" style="width:100%; padding:10px; font-weight:800;" onclick="clearTableFromAdmin(${t.id})">
                            Oturumu Sonlandır
                        </button>
                    ` : ''}
                </div>
            `;
        });
        container.innerHTML = html || '<div style="color:var(--text-muted);">Masa yok.</div>';
    } catch(e) {
        console.error("Kasa masaları yüklenemedi:", e);
    }
}

async function clearTableFromAdmin(masaId) {
    if (!confirm("Masa oturumu sonlandırılacaktır. Onaylıyor musunuz?")) return;
    try {
        const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
        if (res.ok) {
            loadKasaTables();
            loadAdminTables();
            alert("Masa oturumu sonlandırıldı!");
        }
    } catch(e) {
        alert("Masa sıfırlanamadı.");
    }
}
