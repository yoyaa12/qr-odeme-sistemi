// ==========================================================================
// WAITER PANEL (GARSON PANELİ) LOGIC (GÜNCELLENMİŞ - 6 HANELİ PIN DESTEKLİ)
// ==========================================================================

let waiterOrders = [];
let allRawOrders = [];
let tables = [];
let currentPinDigits = [];
let activeGarson = null;
let pendingActionCallback = null;
let activeBrowsingTables = {}; // { masa_id: { masa_no: 'Masa 1', time: Date.now() } }

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
    restoreGarsonSession();

    // Socket.io Canlı Bağlantı
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

    // Müşteri QR Menüyü Açtığında (Masa Oturumu Başladı)
    socket.on('garson_musteri_geldi', (data) => {
        showWaiterToast(`👋 MÜŞTERİ GELDİ! ${data.masa_no} menüyü inceliyor.`);
        if (data && data.masa_id) {
            if (!activeBrowsingTables[data.masa_id]) {
                activeBrowsingTables[data.masa_id] = { masa_no: data.masa_no, time: Date.now(), item_count: 0, last_item: '' };
            }
            renderWaiterDashboard();
        }
    });

    // Müşteri Sepete Ürün Eklediğinde
    socket.on('garson_musteri_urun_secti', (data) => {
        if (data && data.masa_id) {
            if (data.item_count > 0 && (!activeBrowsingTables[data.masa_id] || activeBrowsingTables[data.masa_id].item_count === 0)) {
                showWaiterToast(`📖 MENÜ İNCELENİYOR! ${data.masa_no} sepete ürün ekledi (${data.last_item}).`);
            }
            activeBrowsingTables[data.masa_id] = {
                masa_no: data.masa_no,
                time: Date.now(),
                item_count: data.item_count,
                last_item: data.last_item
            };
            renderWaiterDashboard();
        }
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

    // Müşteri Yedikten Sonra Öde Seçtiğinde (Garson Onay Talebi)
    socket.on('garson_onay_talebi', (data) => {
        playWaiterBellSound();
        showWaiterToast(`🛎️ MASAYA GİDİN! ${data.masa_no} - Sipariş Onayı Bekliyor!`);
        loadWaiterData();
    });

    socket.on('nakit_odendi', () => loadWaiterData());
    socket.on('yeni_siparis', () => loadWaiterData());
    socket.on('masa_durumu_degisti', () => loadWaiterData());
    socket.on('masa_temizlendi', (data) => {
        if (data && data.masa_id) {
            delete activeBrowsingTables[data.masa_id];
        }
        loadWaiterData();
    });

    // Klavye ile PIN Girme Desteği
    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('garsonPinModal');
        if (!modal || !modal.classList.contains('active')) return;

        if (e.key >= '0' && e.key <= '9') {
            pressPinDigit(e.key);
        } else if (e.key === 'Backspace') {
            backspacePin();
        } else if (e.key === 'Escape') {
            closeGarsonPinModal();
        }
    });
});

// -------------------------------------------------------------
// 6 HANELİ GARSON PIN YÖNETİMİ & NUMPAD LOGIC
// -------------------------------------------------------------
// -------------------------------------------------------------
// 6 HANELİ GARSON PIN YÖNETİMİ & NUMPAD LOGIC (HER İŞLEMDE PIN SORULUR)
// -------------------------------------------------------------
function restoreGarsonSession() {
    // Statik kalıcı oturum tutulmaz, her işlemde PIN sorulur!
    localStorage.removeItem('activeGarsonSession');
    activeGarson = null;
    updateGarsonBadge();
}

function updateGarsonBadge() {
    const badge = document.getElementById('activeGarsonBadge');
    if (badge) {
        badge.innerHTML = `🔑 Her İşlemde Garson PIN Sorulur`;
        badge.style.borderColor = 'var(--primary)';
        badge.style.color = 'var(--primary)';
    }
}

window.openGarsonPinModal = function(callback = null) {
    pendingActionCallback = callback;
    currentPinDigits = [];
    updatePinDisplay();

    const errBox = document.getElementById('pinErrorMsg');
    if (errBox) errBox.style.display = 'none';

    const modal = document.getElementById('garsonPinModal');
    if (modal) modal.classList.add('active');
};

window.closeGarsonPinModal = function() {
    const modal = document.getElementById('garsonPinModal');
    if (modal) modal.classList.remove('active');
    currentPinDigits = [];
    pendingActionCallback = null;
};

window.pressPinDigit = function(digit) {
    if (currentPinDigits.length < 6) {
        currentPinDigits.push(digit);
        updatePinDisplay();

        if (currentPinDigits.length === 6) {
            submitGarsonPin();
        }
    }
};

window.clearPin = function() {
    currentPinDigits = [];
    updatePinDisplay();
};

window.backspacePin = function() {
    if (currentPinDigits.length > 0) {
        currentPinDigits.pop();
        updatePinDisplay();
    }
};

function updatePinDisplay() {
    for (let i = 1; i <= 6; i++) {
        const slot = document.getElementById(`pinSlot1`); // slot reference
        const currentSlot = document.getElementById(`pinSlot${i}`);
        if (currentSlot) {
            if (i <= currentPinDigits.length) {
                currentSlot.classList.add('filled');
                currentSlot.innerText = '•';
            } else {
                currentSlot.classList.remove('filled', 'success', 'error');
                currentSlot.innerText = '';
            }
        }
    }
}

async function submitGarsonPin() {
    const pin = currentPinDigits.join('');
    const errBox = document.getElementById('pinErrorMsg');
    if (errBox) errBox.style.display = 'none';

    try {
        const res = await fetch('/api/garson/verify-pin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin_code: pin })
        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {
            for (let i = 1; i <= 6; i++) {
                const slot = document.getElementById(`pinSlot${i}`);
                if (slot) slot.classList.add('success');
            }

            const person = data.garson; // { garson_adi: 'Yiğit' / 'Berat' / 'Ahmet', rol: 'garson' / 'admin' }
            activeGarson = person;
            updateActiveGarsonBadge();
            const actionToExecute = pendingActionCallback;

            setTimeout(() => {
                closeGarsonPinModal();
                showWaiterToast(`🔑 PIN Doğrulandı (${person.garson_adi}) - İşlem yapılıyor... 🚀`);
                if (typeof actionToExecute === 'function') {
                    actionToExecute(person);
                }
            }, 300);
        } else {
            for (let i = 1; i <= 6; i++) {
                const slot = document.getElementById(`pinSlot${i}`);
                if (slot) slot.classList.add('error');
            }

            if (errBox) {
                errBox.innerText = data.detail || 'Hatalı 6 Haneli Garson PIN Kodu!';
                errBox.style.display = 'block';
            }

            setTimeout(() => {
                clearPin();
            }, 800);
        }
    } catch(e) {
        if (errBox) {
            errBox.innerText = 'Sunucu bağlantı hatası!';
            errBox.style.display = 'block';
        }
        clearPin();
    }
}

function requireGarsonPin(actionCallback) {
    // Her masaya tıklandığında ve her işlemde her zaman PIN sorulur
    openGarsonPinModal(actionCallback);
}

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
        
        allRawOrders = await ordersRes.json();
        tables = await tablesRes.json();

        tables.forEach(t => {
            if (t.secim_durumu) {
                activeBrowsingTables[t.id] = t.secim_durumu;
            }
        });

        waiterOrders = allRawOrders.filter(o => ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        renderWaiterDashboard();
    } catch (e) {
        console.error("Garson verileri yüklenemedi:", e);
    }
}

function renderWaiterDashboard() {
    const container = document.getElementById('waiterDashboardGrid');
    if (!container) return;

    const activeOrders = waiterOrders.filter(o => ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));

    const occupiedTableIds = allRawOrders
        .filter(o => o.odeme_durumu !== 'odendi' && ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir', 'teslim_edildi'].includes(o.siparis_durumu))
        .map(o => o.masa_id);

    const browsingTableIds = Object.keys(activeBrowsingTables).filter(id => {
        const masaId = parseInt(id);
        return !occupiedTableIds.includes(masaId);
    });

    if (activeOrders.length === 0 && browsingTableIds.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--text-muted);">
                <div style="font-size: 3rem; margin-bottom: 12px;">🛎️</div>
                <h2>Aktif Masa Siparişi Yok</h2>
                <p>Mutfaktan teslimat bekleyen ürün veya onay talepleri burada görünecektir.</p>
            </div>
        `;
        return;
    }

    // MASALARA GÖRE BİRLEŞTİRME & GRUPLAMA (TABLE-BASED AGGREGATION)
    const groupedByMasa = {};

    activeOrders.forEach(order => {
        if (!groupedByMasa[order.masa_id]) {
            groupedByMasa[order.masa_id] = {
                masa_id: order.masa_id,
                masa_no: order.masa_no,
                orders: [],
                total_amount: 0,
                has_pending_approval: false,
                has_cash_pending: false,
                has_ready: false,
                combined_items: {}
            };
        }
        
        const group = groupedByMasa[order.masa_id];
        group.orders.push(order);
        group.total_amount += order.toplam_tutar;

        if (order.siparis_durumu === 'garson_onayi_bekliyor') group.has_pending_approval = true;
        if (order.siparis_durumu === 'nakit_bekliyor' || (order.odeme_yontemi === 'nakit' && order.odeme_durumu !== 'odendi')) group.has_cash_pending = true;
        if (order.siparis_durumu === 'hazir') group.has_ready = true;

        (order.detaylar || []).forEach(item => {
            const key = item.urun_adi + '_' + (item.urun_notu || '');
            if (!group.combined_items[key]) {
                group.combined_items[key] = {
                    urun_adi: item.urun_adi,
                    adet: 0,
                    birim_fiyat: item.birim_fiyat,
                    ara_toplam: 0,
                    urun_notu: item.urun_notu || ''
                };
            }
            group.combined_items[key].adet += item.adet;
            group.combined_items[key].ara_toplam += item.ara_toplam;
        });
    });

    let html = '';
    Object.values(groupedByMasa).forEach(group => {
        let badgeText = "MUTFAKTA";
        let badgeColor = "var(--danger)";

        if (group.has_pending_approval) {
            badgeText = "🛎️ MASA DOĞRULAMA BEKLİYOR";
            badgeColor = "#3b82f6";
        } else if (group.has_cash_pending) {
            badgeText = "💵 NAKİT ÖDEME BEKLİYOR";
            badgeColor = "#d97706";
        } else if (group.has_ready) {
            badgeText = "TESLİMAT BEKLİYOR! (HAZIR)";
            badgeColor = "var(--success)";
        } else {
            badgeText = "HAZIRLANIYOR";
            badgeColor = "var(--primary)";
        }

        const borderStyle = group.has_pending_approval ? 'border-color: #3b82f6; box-shadow: 0 0 20px rgba(59,130,246,0.35);' : (group.has_cash_pending ? 'border-color: #f59e0b; box-shadow: 0 0 20px rgba(245,158,11,0.3);' : '');

        html += `
            <div class="order-card" style="${borderStyle}">
                <div class="order-header">
                    <div class="order-title-wrapper">
                        <div class="order-table-title">🪑 ${group.masa_no}</div>
                        <span class="table-badge" style="background: ${badgeColor}; font-weight:800;">
                            ${badgeText}
                        </span>
                    </div>
                    <div class="order-total-bar">
                        <span>Toplam Masa Hesabı:</span>
                        <strong>${group.total_amount.toFixed(2)} ₺</strong>
                    </div>
                </div>

                ${group.has_pending_approval ? `
                    <div style="background: rgba(59, 130, 246, 0.18); border: 1.5px solid #3b82f6; padding: 12px; border-radius: var(--radius-md); margin-bottom: 10px;">
                        <div style="font-weight: 800; color: #60a5fa; font-size: 0.95rem; margin-bottom: 4px;">
                            🛎️ MASADAN SİPARİŞ ONAY TALEBİ (${group.total_amount.toFixed(2)} ₺)
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Masadan yeni sipariş verildi. Garson olarak siparişi kontrol edip onaylayınız veya düzenleyiniz.
                        </div>
                        <div style="display:flex; gap: 8px; flex-wrap: wrap;">
                            <button class="btn-status-action btn-success" style="padding: 8px 14px; font-size: 0.88rem; flex:1;" onclick="approveTableOrdersWithPin(${group.masa_id})">
                                ✅ Onayla & Mutfağa Gönder
                            </button>
                            <button class="btn-status-action btn-warning" style="padding: 8px 14px; font-size: 0.88rem;" onclick="openEditOrderModalForTable(${group.masa_id})">
                                ✏️ Siparişi Düzenle
                            </button>
                        </div>
                    </div>
                ` : ''}

                ${group.has_cash_pending ? `
                    <div style="background: rgba(245, 158, 11, 0.18); border: 1.5px solid var(--primary); padding: 12px; border-radius: var(--radius-md); margin-bottom: 10px;">
                        <div style="font-weight: 800; color: #fbbf24; font-size: 0.95rem; margin-bottom: 4px;">
                            💵 MASADAN NAKİT TAHSİLAT YAPILACAK (${group.total_amount.toFixed(2)} ₺)
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Garson masadan ${group.total_amount.toFixed(2)} ₺ tahsil ettikten sonra PIN ile onaylamalıdır.
                        </div>
                        <div style="display:flex; gap: 8px; flex-wrap: wrap;">
                            <button class="btn-status-action btn-warning" style="padding: 8px 14px; font-size: 0.88rem; flex:1;" onclick="collectCashTableWithPin(${group.masa_id})">
                                💵 Nakit Tahsil Et & Onayla
                            </button>
                        </div>
                    </div>
                ` : ''}

                <div style="display:flex; flex-direction:column; gap:6px; flex:1;">
        `;

        Object.values(group.combined_items).forEach(item => {
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

                <div style="display:flex; flex-direction:column; gap: 8px; margin-top: 12px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 10px;">
                    ${group.has_ready ? `
                        <button class="btn-status-action btn-success" style="padding: 12px; font-weight: 800; font-size: 0.95rem;" onclick="deliverTableOrdersDirect(${group.masa_id})">
                            🚀 Masaya Teslim Et
                        </button>
                    ` : (group.has_cash_pending || group.has_pending_approval ? '' : `
                        <div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; width: 100%; padding: 4px;">
                            ⏳ Mutfakta Hazırlanıyor...
                        </div>
                    `)}
                    <div style="text-align: center; margin-top: 4px;">
                        <button type="button" style="background: none; border: none; color: #f87171; font-size: 0.78rem; font-weight: 700; cursor: pointer; text-decoration: underline; opacity: 0.8;" onclick="clearMasaWithPin(${group.masa_id})">
                            Oturumu Sonlandır
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    browsingTableIds.forEach(id => {
        const b = activeBrowsingTables[id];
        const hasCart = b.item_count && b.item_count > 0;
        html += `
            <div class="order-card" style="border-color: ${hasCart ? '#f59e0b' : '#3b82f6'}; box-shadow: 0 0 15px ${hasCart ? 'rgba(245,158,11,0.3)' : 'rgba(59,130,246,0.3)'};">
                <div class="order-header">
                    <div class="order-title-wrapper">
                        <div class="order-table-title">🪑 ${b.masa_no}</div>
                        <span class="table-badge" style="background:${hasCart ? '#f59e0b' : '#3b82f6'}; color:#fff; font-weight:800;">
                            ${hasCart ? `📖 MENÜ İNCELENİYOR (${b.item_count} Ürün Sepette)` : '📖 MENÜ İNCELENİYOR'}
                        </span>
                    </div>
                </div>
                <div style="background:${hasCart ? 'rgba(245,158,11,0.12)' : 'rgba(59,130,246,0.12)'}; border:1px solid ${hasCart ? '#f59e0b' : '#3b82f6'}; padding:12px; border-radius:var(--radius-md); font-size:0.85rem; color:${hasCart ? '#fbbf24' : '#60a5fa'}; margin-top:8px;">
                    ${hasCart 
                        ? `📖 Müşteri menüyü inceliyor ve sepete ürün ekledi: <strong>${b.last_item}</strong> (Toplam ${b.item_count} Ürün). Sipariş verdiğinde anında uyarılacaksınız!`
                        : `👋 Müşteri masaya oturdu, QR kod ile menüyü inceliyor. Sipariş verdiğinde anında uyarılacaksınız!`}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

window.approveTableOrdersWithPin = function(masaId) {
    requireGarsonPin(async (garson) => {
        const pendingOrders = waiterOrders.filter(o => o.masa_id === masaId && o.siparis_durumu === 'garson_onayi_bekliyor');
        try {
            await Promise.all(pendingOrders.map(o => 
                fetch(`/api/siparisler/${o.id}/durum`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ yeni_durum: 'garson_onayladi_mutfakta', garson_adi: garson.garson_adi })
                })
            ));
            loadWaiterData();
            showWaiterToast(`Masa ${garson.garson_adi} tarafından doğrulandı! Siparişler mutfağa aktarıldı. 🚀`);
        } catch (e) {
            alert("İşlem başarısız.");
        }
    });
};

window.collectCashTableWithPin = function(masaId) {
    requireGarsonPin(async (garson) => {
        const cashOrders = waiterOrders.filter(o => o.masa_id === masaId && (o.siparis_durumu === 'nakit_bekliyor' || (o.odeme_yontemi === 'nakit' && o.odeme_durumu !== 'odendi')));
        try {
            await Promise.all(cashOrders.map(o => 
                fetch(`/api/siparisler/${o.id}/durum`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ yeni_durum: 'nakit_tahsil_edildi', garson_adi: garson.garson_adi })
                })
            ));
            loadWaiterData();
            showWaiterToast(`Nakit ödeme ${garson.garson_adi} tarafından tahsil edildi. Siparişler mutfağa aktarıldı! 👍`);
        } catch (e) {
            alert("İşlem başarısız.");
        }
    });
};

window.deliverTableOrdersDirect = async function(masaId) {
    const readyOrders = waiterOrders.filter(o => o.masa_id === masaId && o.siparis_durumu === 'hazir');
    try {
        const garsonName = activeGarson ? activeGarson.garson_adi : 'Garson';
        await Promise.all(readyOrders.map(o => 
            fetch(`/api/siparisler/${o.id}/durum`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ yeni_durum: 'teslim_edildi', garson_adi: garsonName })
            })
        ));
        loadWaiterData();
        showWaiterToast(`🚀 Masa siparişi masaya teslim edildi.`);
    } catch (e) {
        alert("İşlem başarısız.");
    }
};

window.deliverTableOrdersWithPin = function(masaId) {
    requireGarsonPin(async (garson) => {
        const readyOrders = waiterOrders.filter(o => o.masa_id === masaId && o.siparis_durumu === 'hazir');
        try {
            await Promise.all(readyOrders.map(o => 
                fetch(`/api/siparisler/${o.id}/durum`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ yeni_durum: 'teslim_edildi', garson_adi: garson.garson_adi })
                })
            ));
            loadWaiterData();
            showWaiterToast(`Siparişler ${garson.garson_adi} tarafından teslim edildi. 👍`);
        } catch (e) {
            alert("İşlem başarısız.");
        }
    });
};

window.clearMasaWithPin = function(masaId) {
    requireGarsonPin(async (garson) => {
        if (!confirm(`Masa oturumu ${garson.garson_adi} yetkisiyle sonlandırılacaktır. Onaylıyor musunuz?`)) return;
        try {
            const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
            if (res.ok) {
                loadWaiterData();
                showWaiterToast(`Masa oturumu ${garson.garson_adi} tarafından sonlandırıldı.`);
            }
        } catch(e) {
            alert("İşlem başarısız.");
        }
    });
};

function showWaiterToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification-waiter';
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ==========================================================================
// GARSON SİPARİŞ DÜZENLEME MANTIĞI (TIK TIK ÜRÜN EKLE/ÇIKAR/ADET GÜNCELLE)
// ==========================================================================
let currentEditOrder = null;
let currentEditItems = [];
let allMenuProducts = [];

async function loadAllMenuProducts() {
    if (allMenuProducts.length === 0) {
        try {
            const res = await fetch('/api/urunler');
            allMenuProducts = await res.json();
        } catch(e) {
            console.error("Ürünler yüklenemedi:", e);
        }
    }
}

window.openEditOrderModalForTable = async function(masaId) {
    const pendingOrders = waiterOrders.filter(o => o.masa_id === masaId && o.siparis_durumu === 'garson_onayi_bekliyor');
    if (pendingOrders.length === 0) {
        alert("Düzenlenecek onay bekleyen sipariş bulunamadı.");
        return;
    }

    currentEditOrder = pendingOrders[0];
    currentEditItems = JSON.parse(JSON.stringify(currentEditOrder.detaylar || []));

    await loadAllMenuProducts();
    populateEditProductSelect();

    const titleEl = document.getElementById('editModalTitle');
    if (titleEl) titleEl.innerText = `✏️ Masa ${currentEditOrder.masa_no} Siparişini Düzenle`;

    renderEditOrderItems();
    document.getElementById('editOrderModal').classList.add('active');
};

function populateEditProductSelect() {
    const select = document.getElementById('editAddProductSelect');
    if (!select) return;
    let html = '<option value="">-- Menüden Ürün Seçiniz --</option>';
    allMenuProducts.forEach(p => {
        html += `<option value="${p.id}">${p.urun_adi} (${p.fiyat.toFixed(2)} ₺)</option>`;
    });
    select.innerHTML = html;
}

function renderEditOrderItems() {
    const container = document.getElementById('editOrderItemsContainer');
    const totalEl = document.getElementById('editModalTotalAmount');
    if (!container) return;

    let total = 0;
    if (currentEditItems.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-secondary);">Siparişte ürün kalmadı.</div>`;
    } else {
        let html = '';
        currentEditItems.forEach((item, index) => {
            const araToplam = item.adet * item.birim_fiyat;
            total += araToplam;
            html += `
                <div class="order-item-row" style="padding: 10px 0; border-bottom: 1px dashed rgba(255,255,255,0.08);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700;">${item.urun_adi}</span>
                        <span style="font-weight:800; color:#fbbf24;">${araToplam.toFixed(2)} ₺</span>
                    </div>
                    ${item.urun_notu ? `<div style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px;">${item.urun_notu}</div>` : ''}
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <button type="button" onclick="changeEditItemQty(${index}, -1)" style="width:32px; height:32px; font-weight:800; border-radius:var(--radius-sm); background:rgba(255,255,255,0.12); border:1px solid var(--border-color); color:#fff; cursor:pointer;">-</button>
                            <span style="font-weight:800; font-size:1.1rem; min-width:24px; text-align:center;">${item.adet}</span>
                            <button type="button" onclick="changeEditItemQty(${index}, 1)" style="width:32px; height:32px; font-weight:800; border-radius:var(--radius-sm); background:rgba(255,255,255,0.12); border:1px solid var(--border-color); color:#fff; cursor:pointer;">+</button>
                        </div>
                        <button type="button" style="background:none; border:none; color:var(--danger); font-size:0.85rem; font-weight:700; cursor:pointer;" onclick="removeEditItem(${index})">🗑️ Sil</button>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    if (totalEl) totalEl.innerText = `${total.toFixed(2)} ₺`;
}

window.changeEditItemQty = function(index, delta) {
    if (!currentEditItems[index]) return;
    currentEditItems[index].adet += delta;
    if (currentEditItems[index].adet <= 0) {
        currentEditItems.splice(index, 1);
    }
    renderEditOrderItems();
};

window.removeEditItem = function(index) {
    currentEditItems.splice(index, 1);
    renderEditOrderItems();
};

window.addSelectedProductToEditOrder = function() {
    const select = document.getElementById('editAddProductSelect');
    if (!select || !select.value) return;
    const prodId = parseInt(select.value);
    const prod = allMenuProducts.find(p => p.id === prodId);
    if (!prod) return;

    const existing = currentEditItems.find(i => i.urun_id === prodId);
    if (existing) {
        existing.adet += 1;
    } else {
        currentEditItems.push({
            urun_id: prod.id,
            urun_adi: prod.urun_adi,
            adet: 1,
            birim_fiyat: prod.fiyat,
            urun_notu: '',
            ara_toplam: prod.fiyat
        });
    }

    select.value = '';
    renderEditOrderItems();
};

window.closeEditOrderModal = function() {
    currentEditOrder = null;
    currentEditItems = [];
    const modal = document.getElementById('editOrderModal');
    if (modal) modal.classList.remove('active');
};

window.saveEditedOrder = function() {
    if (!currentEditOrder) return;
    
    if (currentEditItems.length === 0) {
        alert("Siparişte en az 1 ürün bulunmalıdır.");
        return;
    }

    requireGarsonPin(async (garson) => {
        const totalAmount = currentEditItems.reduce((acc, item) => acc + (item.adet * item.birim_fiyat), 0);
        const payload = {
            toplam_tutar: totalAmount,
            garson_adi: garson.garson_adi,
            urunler: currentEditItems.map(i => ({
                urun_id: i.urun_id,
                adet: i.adet,
                birim_fiyat: i.birim_fiyat,
                urun_notu: i.urun_notu || ''
            }))
        };

        try {
            const res = await fetch(`/api/siparisler/${currentEditOrder.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeEditOrderModal();
                loadWaiterData();
                showWaiterToast(`✏️ Sipariş ${garson.garson_adi} tarafından güncellendi!`);
            } else {
                const errData = await res.json().catch(() => ({}));
                alert(errData.detail || "Sipariş güncelleme başarısız.");
            }
        } catch(e) {
            alert("Sunucu bağlantı hatası. Lütfen ağınızı kontrol edin.");
        }
    });
};

function updateActiveGarsonBadge() {
    const badge = document.getElementById('activeGarsonBadge');
    if (!badge) return;
    if (activeGarson) {
        badge.innerHTML = `
            <span>👤 Garson: ${activeGarson.garson_adi}</span>
            <button onclick="logoutGarson()" style="background:none; border:none; color:var(--danger); cursor:pointer; font-size:0.75rem; font-weight:700; padding:0; margin-left:4px;">🔒 Çıkış</button>
        `;
        badge.style.display = 'inline-flex';
    } else {
        badge.style.display = 'none';
    }
}

window.logoutGarson = function() {
    activeGarson = null;
    updateActiveGarsonBadge();
    showWaiterToast("Garson oturumu kapatıldı.");
};

