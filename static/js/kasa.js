document.addEventListener('DOMContentLoaded', () => {
    loadKasaData();

    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000
    });

    socket.on('connect', () => updateKasaSocketBadge(true));
    socket.on('disconnect', () => updateKasaSocketBadge(false));

    socket.on('durum_guncellendi', () => loadKasaData());
    socket.on('yeni_siparis', () => loadKasaData());
    socket.on('masa_durumu_degisti', () => loadKasaData());
    socket.on('garson_onay_talebi', () => loadKasaData());
});

function updateKasaSocketBadge(isConnected) {
    const badge = document.getElementById('socketStatusBadge');
    if (badge) {
        badge.innerHTML = isConnected ? `🟢 Canlı Bağlantı Aktif` : `🔴 Bağlantı Kesildi`;
        badge.style.color = isConnected ? `var(--success)` : `var(--danger)`;
    }
}

async function loadKasaData() {
    try {
        const [tablesRes, ordersRes] = await Promise.all([
            fetch('/api/masalar'),
            fetch('/api/siparisler')
        ]);
        const tables = await tablesRes.json();
        const orders = await ordersRes.json();

        renderKasaGrid(tables, orders);
    } catch(e) {
        console.error("Kasa verileri yüklenemedi:", e);
    }
}

function renderKasaGrid(tables, orders) {
    const container = document.getElementById('kasaGrid');
    if (!container) return;

    let html = '';
    tables.forEach(t => {
        const masaOrders = orders.filter(o => o.masa_id === t.id && ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        const totalBill = masaOrders.reduce((sum, o) => sum + o.toplam_tutar, 0);
        const isDolu = t.durum === 'dolu' || masaOrders.length > 0;
        const isPaidOnline = masaOrders.length > 0 && masaOrders.every(o => o.odeme_durumu === 'odendi');

        html += `
            <div class="order-card" style="border-color: ${isDolu ? (isPaidOnline ? '#10b981' : '#f59e0b') : 'rgba(255,255,255,0.1)'};">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${t.masa_no}</div>
                        <div class="order-code">Aktif Sipariş: ${masaOrders.length} Kalem</div>
                    </div>
                    <span class="table-badge" style="background:${isDolu ? (isPaidOnline ? '#10b981' : '#f59e0b') : '#64748b'}; color:#fff; font-weight:800;">
                        ${isDolu ? (isPaidOnline ? '💳 ÖDENDİ (Masada Yiyor)' : '🟡 HESAP AÇIK (Kasada Ödeyecek)') : '🟢 BOŞ'}
                    </span>
                </div>

                <div style="margin: 12px 0; padding:12px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:var(--radius-md);">
                    <div style="font-size:0.85rem; color:var(--text-secondary);">Adisyon Detayı:</div>
                    ${masaOrders.map(o => `
                        <div style="display:flex; justify-content:space-between; font-size:0.88rem; margin-top:4px;">
                            <span>#${o.siparis_kodu} (${o.odeme_yontemi === 'pos' ? 'Online Ödendi' : 'Kasada Ödenecek'})</span>
                            <span style="font-weight:800; color:#fbbf24;">${o.toplam_tutar.toFixed(2)} ₺</span>
                        </div>
                    `).join('')}
                    <div style="display:flex; justify-content:space-between; border-top:1px dashed var(--border-color); margin-top:8px; padding-top:6px; font-weight:800; font-size:1.1rem; color:#fbbf24;">
                        <span>Toplam Adisyon:</span>
                        <span>${totalBill.toFixed(2)} ₺</span>
                    </div>
                </div>

                ${isDolu ? `
                    <button class="btn-status-action btn-success" style="width:100%; padding:12px; font-weight:800; font-size:0.95rem;" onclick="collectAndClearTable(${t.id})">
                        💵 Kasada Ödemeyi Tahsil Et & Masayı Kapat (CLEAR)
                    </button>
                ` : '<div style="font-size:0.85rem; color:var(--text-muted); text-align:center; padding:8px;">Masa boş ve hazır.</div>'}
            </div>
        `;
    });

    container.innerHTML = html || '<div style="color:var(--text-muted);">Masa bulunamadı.</div>';
}

async function collectAndClearTable(masaId) {
    if (!confirm("Masa ödemesi kasada tahsil edilecek ve masa sıfırlanacaktır. Onaylıyor musunuz?")) return;
    try {
        const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
        if (res.ok) {
            loadKasaData();
            showKasaToast("Ödeme tahsil edildi, masa temizlendi ve kapatıldı! 🧹");
        }
    } catch(e) {
        alert("İşlem gerçekleştirilemedi.");
    }
}

function showKasaToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification-waiter';
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
