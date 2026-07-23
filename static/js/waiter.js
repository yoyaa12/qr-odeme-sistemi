// ==========================================================================
// WAITER PANEL (GARSON PANELİ) LOGIC (GÜNCELLENMİŞ)
// ==========================================================================

let waiterOrders = [];
let tables = [];

function playWaiterBellSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(1046.50, audioCtx.currentTime);
        osc.frequency.setValueAtTime(1318.51, audioCtx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.5);
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded', () => {
    loadWaiterData();

    // Socket.io Canlı Bağlantı
    const socket = io();

    socket.on('connect', () => {
        updateWaiterSocketBadge(true);
    });

    socket.on('disconnect', () => {
        updateWaiterSocketBadge(false);
    });

    // Mutfak "Hazır" Yaptığında
    socket.on('durum_guncellendi', (data) => {
        if (data.yeni_durum === 'hazir') {
            playWaiterBellSound();
            showWaiterToast(`🔔 TESLİMAT BEKLİYOR! ${data.masa_no} Yemeği Hazır!`);
        }
        loadWaiterData();
    });

    // Müşteri Nakit Ödeme Seçtiğinde
    socket.on('nakit_odeme_talebi', (data) => {
        playWaiterBellSound();
        showWaiterToast(`💵 NAKİT ÖDEME TALEBİ! ${data.masa_no} - Tutar: ${data.toplam_tutar.toFixed(2)} ₺`);
        loadWaiterData();
    });

    socket.on('yeni_siparis', () => loadWaiterData());
    socket.on('masa_durumu_degisti', () => loadWaiterData());
});

function updateWaiterSocketBadge(isConnected) {
    const badge = document.getElementById('socketStatusBadge');
    if (badge) {
        if (isConnected) {
            badge.innerHTML = `🟢 Canlı Bağlantı Aktif`;
            badge.style.color = `var(--success)`;
        } else {
            badge.innerHTML = `🔴 Bağlantı Kesildi`;
            badge.style.color = `var(--danger)`;
        }
    }
}

async function loadWaiterData() {
    try {
        const [ordersRes, tablesRes] = await Promise.all([
            fetch('/api/siparisler'),
            fetch('/api/masalar')
        ]);
        
        const allOrders = await ordersRes.json();
        tables = await tablesRes.json();

        waiterOrders = allOrders.filter(o => ['odendi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        renderWaiterDashboard();
    } catch (e) {
        console.error("Garson verileri yüklenemedi:", e);
    }
}

function renderWaiterDashboard() {
    const container = document.getElementById('waiterDashboardGrid');
    if (!container) return;

    const activeOrders = waiterOrders.filter(o => ['odendi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));

    if (activeOrders.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--text-muted);">
                <div style="font-size: 3rem; margin-bottom: 12px;">🛎️</div>
                <h2>Aktif Masa Siparişi Yok</h2>
                <p>Mutfaktan teslimat bekleyen ürün veya nakit talepleri burada görünecektir.</p>
            </div>
        `;
        return;
    }

    let html = '';
    activeOrders.forEach(order => {
        const isReady = order.siparis_durumu === 'hazir';
        const isPreparing = order.siparis_durumu === 'hazirlaniyor';
        const isCashPending = order.odeme_yontemi === 'nakit' && order.odeme_durumu !== 'odendi';

        let badgeText = "MUTFAKTA";
        let badgeColor = "var(--danger)";

        if (isPreparing) {
            badgeText = "HAZIRLANIYOR";
            badgeColor = "var(--primary)";
        } else if (isReady) {
            badgeText = "TESLİMAT BEKLİYOR! (HAZIR)";
            badgeColor = "var(--success)";
        }

        html += `
            <div class="order-card status-${order.siparis_durumu}">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${order.masa_no}</div>
                        <div class="order-code">Toplam: ${order.toplam_tutar.toFixed(2)} ₺</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="table-badge" style="background: ${badgeColor};">
                            ${badgeText}
                        </span>
                    </div>
                </div>

                ${isCashPending ? `
                    <div style="background: rgba(245, 158, 11, 0.2); border: 1px solid var(--primary); padding: 10px; border-radius: var(--radius-md); font-weight: 700; color: #fbbf24; font-size: 0.9rem;">
                        💵 MASADA NAKİT ÖDEME TALEBİ! (${order.toplam_tutar.toFixed(2)} ₺)
                    </div>
                ` : ''}

                <div style="display:flex; flex-direction:column; gap:6px; flex:1;">
        `;

        order.detaylar.forEach(item => {
            html += `
                <div class="order-item-row">
                    <div class="order-item-main">
                        <span>${item.adet}x ${item.urun_adi}</span>
                        <span>${item.ara_toplam.toFixed(2)} ₺</span>
                    </div>
                    ${item.urun_notu ? `<div class="order-item-note">Not / Opsiyon: ${item.urun_notu}</div>` : ''}
                </div>
            `;
        });

        html += `
                </div>

                <div style="display:flex; flex-direction:column; gap: 8px;">
                    ${isCashPending ? `
                        <button class="btn-status-action btn-warning" onclick="collectCash(${order.id})">
                            💵 Nakit Tahsil Edildi (Garson Mehmet)
                        </button>
                    ` : ''}

                    ${isReady ? `
                        <button class="btn-status-action btn-success" onclick="deliverOrder(${order.id})">
                            🚀 Masaya Teslim Et (Siparişi Kapat)
                        </button>
                    ` : `
                        <div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; width: 100%; padding: 4px;">
                            ⏳ Mutfakta Hazırlanıyor...
                        </div>
                    `}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

async function collectCash(siparisId) {
    try {
        const res = await fetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yeni_durum: 'nakit_tahsil_edildi', garson_adi: 'Garson Mehmet' })
        });

        if (res.ok) {
            loadWaiterData();
            showWaiterToast("Nakit tahsil edildi olarak kaydedildi. 👍");
        }
    } catch (e) {
        alert("İşlem başarısız.");
    }
}

async function deliverOrder(siparisId) {
    try {
        const res = await fetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yeni_durum: 'teslim_edildi' })
        });

        if (res.ok) {
            loadWaiterData();
            showWaiterToast("Sipariş masaya teslim edildi. 👍");
        }
    } catch (e) {
        alert("Sunucu ile iletişim kurulamadı.");
    }
}

function showWaiterToast(msg) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: linear-gradient(135deg, #10b981, #047857);
        color: #fff;
        padding: 16px 28px;
        border-radius: 16px;
        font-weight: 800;
        font-size: 1.1rem;
        box-shadow: 0 10px 30px rgba(16, 185, 129, 0.5);
        z-index: 9999;
    `;
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
