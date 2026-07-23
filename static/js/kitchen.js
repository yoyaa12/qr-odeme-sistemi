// ==========================================================================
// KITCHEN PANEL (MUTFAK PANELİ) LOGIC (GÜNCELLENMİŞ)
// ==========================================================================

let kitchenOrders = [];

function playKitchenAlertSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        const osc1 = audioCtx.createOscillator();
        const osc2 = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc1.type = 'sine';
        osc2.type = 'triangle';

        osc1.frequency.setValueAtTime(880, audioCtx.currentTime);
        osc1.frequency.setValueAtTime(1174.66, audioCtx.currentTime + 0.2);

        osc2.frequency.setValueAtTime(440, audioCtx.currentTime);
        osc2.frequency.setValueAtTime(587.33, audioCtx.currentTime + 0.2);

        gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.6);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(audioCtx.destination);

        osc1.start();
        osc2.start();
        osc1.stop(audioCtx.currentTime + 0.6);
        osc2.stop(audioCtx.currentTime + 0.6);
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded', () => {
    loadKitchenOrders();

    // Socket.io Canlı Bağlantı & Gerçek Bağlantı Kontrolü
    const socket = io();

    socket.on('connect', () => {
        updateKitchenSocketBadge(true);
    });

    socket.on('disconnect', () => {
        updateKitchenSocketBadge(false);
    });

    // 1. Ödemesi Yapılan Yeni Sipariş Mutfağa Düştü!
    socket.on('yeni_siparis', (newOrder) => {
        playKitchenAlertSound();
        showKitchenToast(`🔔 YENİ SİPARİŞ! ${newOrder.masa_no} (${newOrder.siparis_kodu})`);
        loadKitchenOrders();
    });

    // 2. Durum Güncellemeleri
    socket.on('durum_guncellendi', (data) => {
        loadKitchenOrders();
    });
});

function updateKitchenSocketBadge(isConnected) {
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

async function loadKitchenOrders() {
    try {
        const res = await fetch('/api/siparisler');
        const allOrders = await res.json();
        
        kitchenOrders = allOrders.filter(o => ['odendi_mutfakta', 'hazirlaniyor'].includes(o.siparis_durumu));
        renderKitchenOrders();
    } catch (e) {
        console.error("Mutfak siparişleri yüklenemedi:", e);
    }
}

function renderKitchenOrders() {
    const grid = document.getElementById('kitchenOrdersGrid');
    if (!grid) return;

    const activeOrders = kitchenOrders.filter(o => ['odendi_mutfakta', 'hazirlaniyor'].includes(o.siparis_durumu));

    if (activeOrders.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--text-muted);">
                <div style="font-size: 3rem; margin-bottom: 12px;">👨‍🍳</div>
                <h2>Bekleyen Sipariş Yok</h2>
                <p>Yeni bir müşteri sipariş verip ödemeyi tamamladığında anında buraya düşecektir.</p>
            </div>
        `;
        return;
    }

    let html = '';
    activeOrders.forEach(order => {
        const isNew = order.siparis_durumu === 'odendi_mutfakta';
        const isPreparing = order.siparis_durumu === 'hazirlaniyor';

        html += `
            <div class="order-card status-${order.siparis_durumu}">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${order.masa_no}</div>
                        <div class="order-code">${order.siparis_kodu} • ${order.olusturma_tarihi || ''}</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="table-badge" style="background: ${isNew ? 'var(--danger)' : 'var(--accent)'}">
                            ${isNew ? 'YENİ SİPARİŞ' : 'HAZIRLANIYOR'}
                        </span>
                    </div>
                </div>

                <div style="display:flex; flex-direction:column; gap:6px; flex:1;">
        `;

        order.detaylar.forEach(item => {
            html += `
                <div class="order-item-row">
                    <div class="order-item-main">
                        <span style="font-size: 1.1rem;">${item.adet}x ${item.urun_adi}</span>
                    </div>
                    ${item.urun_notu ? `
                        <div class="order-item-note">
                            ⚠️ MÜŞTERİ NOTU: ${item.urun_notu}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += `
                </div>

                <div class="status-btn-group">
                    ${isNew ? `
                        <button class="btn-status-action btn-warning" onclick="updateOrderStatus(${order.id}, 'hazirlaniyor')">
                            ▶ Hazırlanıyor
                        </button>
                    ` : ''}
                    
                    ${isPreparing ? `
                        <button class="btn-status-action btn-success" onclick="updateOrderStatus(${order.id}, 'hazir')">
                            ✔ Hazır! (Garsona Bildir)
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });

    grid.innerHTML = html;
}

async function updateOrderStatus(siparisId, yeniDurum) {
    try {
        const res = await fetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yeni_durum: yeniDurum })
        });
        
        if (res.ok) {
            loadKitchenOrders();
        } else {
            alert("Durum güncellenirken hata oluştu.");
        }
    } catch (e) {
        alert("Sunucuya ulaşılamadı.");
    }
}

function showKitchenToast(msg) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 24px;
        background: linear-gradient(135deg, #ef4444, #b91c1c);
        color: #fff;
        padding: 16px 28px;
        border-radius: 16px;
        font-weight: 800;
        font-size: 1.1rem;
        box-shadow: 0 10px 30px rgba(239, 68, 68, 0.5);
        z-index: 9999;
    `;
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
