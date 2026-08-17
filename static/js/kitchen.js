// ==========================================================================
// KITCHEN PANEL (MUTFAK PANELİ) LOGIC (GÜNCELLENMİŞ)
// ==========================================================================

const escapeHtml = window.SecurityText.escapeHtml;

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

function getStaffToken() {
    if (window.StaffAuth && typeof window.StaffAuth.getToken === 'function') {
        const t = window.StaffAuth.getToken();
        if (t) return t;
    }
    if (window.StaffAuth && window.StaffAuth.getSession()) {
        return window.StaffAuth.getSession().accessToken;
    }
    try {
        const storedSession = JSON.parse(sessionStorage.getItem('qrStaffAuthSessionV1') || 'null');
        if (storedSession && storedSession.accessToken) return storedSession.accessToken;
        const storedLocal = JSON.parse(localStorage.getItem('qrStaffAuthSessionV1') || 'null');
        if (storedLocal && storedLocal.accessToken) return storedLocal.accessToken;
    } catch (e) {}
    return null;
}

async function authFetch(url, options = {}) {
    const token = getStaffToken();
    const headers = options.headers ? { ...options.headers } : {};
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    return fetch(url, { ...options, headers });
}

let kitchenSocket = null;

function initKitchenSocket() {
    const token = getStaffToken();
    if (kitchenSocket) {
        try {
            kitchenSocket.disconnect();
        } catch (e) {}
        kitchenSocket = null;
    }

    kitchenSocket = io({
        auth: { token: token },
        query: { token: token || '' },
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

    kitchenSocket.on('connect', () => {
        updateKitchenSocketBadge(true);
    });

    kitchenSocket.on('disconnect', () => {
        updateKitchenSocketBadge(false);
    });

    // 1. Ödemesi Yapılan Yeni Sipariş Mutfağa Düştü!
    kitchenSocket.on('yeni_siparis', (newOrder) => {
        playKitchenAlertSound();
        showKitchenToast(`🔔 YENİ SİPARİŞ! ${(newOrder && newOrder.masa_no) || 'Masa'} (${(newOrder && newOrder.siparis_kodu) || ''})`);
        loadKitchenOrders();
    });

    // 2. Durum Güncellemeleri
    kitchenSocket.on('durum_guncellendi', (data) => {
        loadKitchenOrders();
    });
}

window.addEventListener('staff-authenticated', () => {
    initKitchenSocket();
    loadKitchenOrders();
});

window.addEventListener('staff-auth-cleared', () => {
    if (kitchenSocket) {
        kitchenSocket.disconnect();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    loadKitchenOrders();
    if (getStaffToken()) {
        initKitchenSocket();
    }
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
        const res = await authFetch('/api/siparisler');
        if (!res.ok) {
            console.warn("Mutfak siparişleri yüklenemedi:", res.status);
            kitchenOrders = [];
            renderKitchenOrders();
            return;
        }
        const allOrders = await res.json();
        
        if (Array.isArray(allOrders)) {
            kitchenOrders = allOrders.filter(o => ['odendi_mutfakta', 'garson_onayladi_mutfakta', 'nakit_tahsil_edildi', 'hazirlaniyor'].includes(o.siparis_durumu));
        } else {
            kitchenOrders = [];
        }
        renderKitchenOrders();
    } catch (e) {
        console.error("Mutfak siparişleri yüklenemedi:", e);
    }
}

function renderKitchenOrders() {
    const grid = document.getElementById('kitchenOrdersGrid');
    if (!grid) return;

    const activeOrders = kitchenOrders.filter(o => ['odendi_mutfakta', 'garson_onayladi_mutfakta', 'nakit_tahsil_edildi', 'hazirlaniyor'].includes(o.siparis_durumu));

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
        const orderId = Number(order.id);
        if (!Number.isInteger(orderId) || orderId <= 0) return;
        const isNew = order.siparis_durumu === 'odendi_mutfakta' || order.siparis_durumu === 'garson_onayladi_mutfakta' || order.siparis_durumu === 'nakit_tahsil_edildi';
        const isPreparing = order.siparis_durumu === 'hazirlaniyor';

        html += `
            <div class="order-card status-${escapeHtml(order.siparis_durumu)}">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${escapeHtml(order.masa_no)}</div>
                        <div class="order-code">${escapeHtml(order.siparis_kodu)} • ${escapeHtml(order.olusturma_tarihi)}</div>
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
                        <span style="font-size: 1.1rem;">${escapeHtml(item.adet)}x ${escapeHtml(item.urun_adi)}</span>
                    </div>
                    ${item.urun_notu ? `
                        <div class="order-item-note">
                            ⚠️ MÜŞTERİ NOTU: ${escapeHtml(item.urun_notu)}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += `
                </div>

                <div class="status-btn-group">
                    ${isNew ? `
                        <button class="btn-status-action btn-warning" onclick="updateOrderStatus(${orderId}, 'hazirlaniyor')">
                            ▶ Hazırlanıyor
                        </button>
                    ` : ''}
                    
                    ${isPreparing ? `
                        <button class="btn-status-action btn-success" onclick="updateOrderStatus(${orderId}, 'hazir')">
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
        const res = await authFetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yeni_durum: yeniDurum })
        });
        
        if (res.ok) {
            loadKitchenOrders();
        } else {
            const data = await res.json().catch(() => ({}));
            appAlert("Durum güncellenirken hata oluştu: " + (data.detail || "Sunucu hatası"));
        }
    } catch (e) {
        appAlert("Sunucuya ulaşılamadı.");
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
