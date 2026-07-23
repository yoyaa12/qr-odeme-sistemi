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

    // Socket.io Canlı Bağlantı (Otomatik Reconnection Ayarları)
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

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

    socket.on('nakit_odendi', () => loadWaiterData());
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

        waiterOrders = allOrders.filter(o => ['nakit_bekliyor', 'odendi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        renderWaiterDashboard();
    } catch (e) {
        console.error("Garson verileri yüklenemedi:", e);
    }
}

function renderWaiterDashboard() {
    const container = document.getElementById('waiterDashboardGrid');
    if (!container) return;

    const activeOrders = waiterOrders.filter(o => ['nakit_bekliyor', 'odendi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));

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
        const isCashPending = order.siparis_durumu === 'nakit_bekliyor' || (order.odeme_yontemi === 'nakit' && order.odeme_durumu !== 'odendi');
        const isPreparing = order.siparis_durumu === 'hazirlaniyor';
        const isReady = order.siparis_durumu === 'hazir';

        let badgeText = "MUTFAKTA";
        let badgeColor = "var(--danger)";

        if (isCashPending) {
            badgeText = "💵 NAKİT ÖDEME BEKLİYOR";
            badgeColor = "#d97706";
        } else if (isPreparing) {
            badgeText = "HAZIRLANIYOR";
            badgeColor = "var(--primary)";
        } else if (isReady) {
            badgeText = "TESLİMAT BEKLİYOR! (HAZIR)";
            badgeColor = "var(--success)";
        }

        html += `
            <div class="order-card status-${order.siparis_durumu}" style="${isCashPending ? 'border-color: #f59e0b; box-shadow: 0 0 20px rgba(245,158,11,0.3);' : ''}">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${order.masa_no}</div>
                        <div class="order-code">Toplam: ${order.toplam_tutar.toFixed(2)} ₺ ${order.garson_adi ? `• Garson: ${order.garson_adi}` : ''}</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="table-badge" style="background: ${badgeColor}; font-weight:800;">
                            ${badgeText}
                        </span>
                    </div>
                </div>

                ${isCashPending ? `
                    <div style="background: rgba(245, 158, 11, 0.18); border: 1.5px solid var(--primary); padding: 12px; border-radius: var(--radius-md);">
                        <div style="font-weight: 800; color: #fbbf24; font-size: 0.95rem; margin-bottom: 4px;">
                            💵 MASADAN NAKİT TAHSİLAT YAPILACAK (${order.toplam_tutar.toFixed(2)} ₺)
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Garson masadan fiziki olarak ${order.toplam_tutar.toFixed(2)} ₺ tahsil ettikten sonra adını yazıp onay butonuna basmalıdır. Sipariş ancak o zaman mutfağa düşer.
                        </div>
                        <div style="display:flex; gap: 8px; flex-wrap: wrap;">
                            <input type="text" id="garsonInput_${order.id}" value="Garson Berat" placeholder="Ödemeyi Alan Garson Adı" style="font-size:0.85rem; padding: 8px 12px; flex:1; min-width: 130px;">
                            <button class="btn-status-action btn-warning" style="padding: 8px 14px; font-size: 0.88rem; white-space:nowrap;" onclick="collectCash(${order.id})">
                                💵 Nakit Tahsil Edildi
                            </button>
                        </div>
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
                    ${isReady ? `
                        <button class="btn-status-action btn-success" onclick="deliverOrder(${order.id})">
                            🚀 Masaya Teslim Et (Siparişi Kapat)
                        </button>
                    ` : (isCashPending ? '' : `
                        <div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; width: 100%; padding: 4px;">
                            ⏳ Mutfakta Hazırlanıyor...
                        </div>
                    `)}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

async function collectCash(siparisId) {
    const inputEl = document.getElementById(`garsonInput_${siparisId}`);
    const garsonName = inputEl ? inputEl.value.trim() || 'Garson Berat' : 'Garson Berat';

    try {
        const res = await fetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yeni_durum: 'nakit_tahsil_edildi', garson_adi: garsonName })
        });

        if (res.ok) {
            loadWaiterData();
            showWaiterToast(`Nakit ödeme ${garsonName} tarafından tahsil edildi. Sipariş mutfağa aktarıldı! 👍`);
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
