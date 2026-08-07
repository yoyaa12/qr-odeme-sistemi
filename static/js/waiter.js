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
let activeDetailMasaId = null;

function getFormattedMasaNo(masa_no) {
    if (!masa_no) return '';
    if (masa_no.startsWith('Masa ')) {
        return 'S-' + masa_no.substring(5);
    } else if (masa_no.startsWith('Salon ')) {
        return 'S-' + masa_no.substring(6);
    } else if (masa_no.startsWith('Bahçe ')) {
        return 'B-' + masa_no.substring(6);
    } else if (masa_no.startsWith('S-') || masa_no.startsWith('B-')) {
        return masa_no;
    }
    return masa_no;
}

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
    } catch (e) { }
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
    socket.on('masa_tasindi', (data) => {
        if (data && activeDetailMasaId && parseInt(activeDetailMasaId) === parseInt(data.from_masa_id)) {
            activeDetailMasaId = parseInt(data.to_masa_id);
        }
        loadWaiterData();
    });
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
function touchGarsonActivity() {
    if (activeGarson) {
        try {
            localStorage.setItem('activeGarsonSession', JSON.stringify({
                garson: activeGarson,
                lastActivity: Date.now()
            }));
        } catch (e) { }
    }
}

function restoreGarsonSession() {
    try {
        const stored = localStorage.getItem('activeGarsonSession');
        if (stored) {
            const data = JSON.parse(stored);
            const ONE_HOUR = 60 * 60 * 1000;
            if (data && data.garson && data.lastActivity && (Date.now() - data.lastActivity < ONE_HOUR)) {
                activeGarson = data.garson;
                touchGarsonActivity();
                updateActiveGarsonBadge();
                return true;
            }
        }
    } catch (e) { }
    localStorage.removeItem('activeGarsonSession');
    activeGarson = null;
    updateActiveGarsonBadge();
    return false;
}

window.openGarsonPinModal = function (callback = null) {
    pendingActionCallback = callback;
    currentPinDigits = [];
    updatePinDisplay();

    const errBox = document.getElementById('pinErrorMsg');
    if (errBox) errBox.style.display = 'none';

    const modal = document.getElementById('garsonPinModal');
    if (modal) modal.classList.add('active');
};

window.closeGarsonPinModal = function () {
    const modal = document.getElementById('garsonPinModal');
    if (modal) modal.classList.remove('active');
    currentPinDigits = [];
    pendingActionCallback = null;
};

window.pressPinDigit = function (digit) {
    if (currentPinDigits.length < 6) {
        currentPinDigits.push(digit);
        updatePinDisplay();

        if (currentPinDigits.length === 6) {
            submitGarsonPin();
        }
    }
};

window.clearPin = function () {
    currentPinDigits = [];
    updatePinDisplay();
};

window.backspacePin = function () {
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
            touchGarsonActivity();
            updateActiveGarsonBadge();
            const actionToExecute = pendingActionCallback;

            setTimeout(() => {
                closeGarsonPinModal();
                showWaiterToast(`🔑 PIN Doğrulandı (${person.garson_adi}) - Oturum Açıldı 🚀`);
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
    } catch (e) {
        if (errBox) {
            errBox.innerText = 'Sunucu bağlantı hatası!';
            errBox.style.display = 'block';
        }
        clearPin();
    }
}

function requireGarsonPin(actionCallback) {
    if (restoreGarsonSession()) {
        touchGarsonActivity();
        if (typeof actionCallback === 'function') {
            actionCallback(activeGarson);
        }
    } else {
        openGarsonPinModal(actionCallback);
    }
}

function updateWaiterSocketBadge(isConnected) {
    const badge = document.getElementById('socketStatusBadge');
    if (badge) {
        if (isConnected) {
            badge.innerHTML = `🟢`;
            badge.setAttribute('title', 'Canlı Bağlantı Aktif');
        } else {
            badge.innerHTML = `🔴`;
            badge.setAttribute('title', 'Bağlantı Kesildi');
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

        if (activeDetailMasaId) {
            const modal = document.getElementById('masaDetailModal');
            if (modal && modal.classList.contains('active')) {
                openMasaDetail(activeDetailMasaId);
            }
        }
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
                device_ids: new Set(),
                total_amount: 0,
                has_pending_approval: false,
                has_cash_pending: false,
                has_ready: false,
                combined_items: {}
            };
        }

        const group = groupedByMasa[order.masa_id];
        group.orders.push(order);
        if (order.device_id) group.device_ids.add(order.device_id);
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
        let borderStyle = 'border-color: #a855f7; box-shadow: 0 0 15px rgba(168,85,247,0.2);'; // Mutfakta (Purple)
        let statusIcon = '🔥';
        let statusText = 'Mutfakta';

        if (group.has_ready) {
            borderStyle = 'border-color: #10b981; box-shadow: 0 0 15px rgba(16,185,129,0.2);'; // Hazır (Green)
            statusIcon = '✅';
            statusText = 'Hazır';
        } else if (group.has_cash_pending) {
            borderStyle = 'border-color: #f59e0b; box-shadow: 0 0 15px rgba(245,158,11,0.3);'; // Ödeme (Orange)
            statusIcon = '💵';
            statusText = 'Ödeme';
        } else if (group.has_pending_approval) {
            borderStyle = 'border-color: #fbbf24; box-shadow: 0 0 15px rgba(251,191,36,0.35);'; // Onay Bekliyor (Yellow - fbbf24)
            statusIcon = '⏳';
            statusText = 'Onay Bekliyor';
        }

        html += `
            <div class="order-card" style="background: #1e293b; border: 2px solid; ${borderStyle} cursor: pointer; padding: 12px 8px; border-radius: 10px; margin-bottom: 8px; min-height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;" onclick="openMasaDetailWithPin(${group.masa_id})">
                <div class="order-table-title" style="font-size: 1.3rem; font-weight: 800; margin-bottom: 4px;">${getFormattedMasaNo(group.masa_no)}</div>
            </div>
        `;
    });

    browsingTableIds.forEach(id => {
        const b = activeBrowsingTables[id];
        const hasCart = b.item_count && b.item_count > 0;
        const formattedMasaNo = getFormattedMasaNo(b.masa_no);
        const color = '#3b82f6';
        const icon = hasCart ? '🛒' : '👀';
        const text = hasCart ? 'Sepette Ürün' : 'Menü İnceliyor';

        html += `
            <div class="order-card" style="background: #1e293b; border: 2px solid ${color}; box-shadow: 0 0 15px rgba(59,130,246,0.2); cursor: pointer; padding: 12px 8px; border-radius: 10px; margin-bottom: 8px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; gap: 6px; min-height: 80px;" onclick="openMasaDetailWithPin(${id})">
                <div style="font-weight: 800; font-size: 1.3rem; color: #fff;">${formattedMasaNo}</div>
            </div>
        `;
    });

    activeBrowsingTables = {}; // Reset browsing tables after rendering to prevent stale tables
    container.innerHTML = html;
}

window.openMasaDetailWithPin = function (masaId) {
    requireGarsonPin((garson) => {
        openMasaDetail(masaId);
    });
};

window.closeMasaDetailModal = function () {
    document.getElementById('masaDetailModal').classList.remove('active');
    activeGarson = null;
    activeDetailMasaId = null;
};

function openMasaDetail(masaId) {
    activeDetailMasaId = masaId;
    const activeOrders = allRawOrders.filter(o => o.masa_id == masaId && o.siparis_durumu !== 'iptal' && o.siparis_durumu !== 'odendi_kapatildi');
    const hasBrowsing = activeBrowsingTables[masaId] !== undefined;

    let masaNo = 'Bilinmeyen Masa';
    if (activeOrders.length > 0) masaNo = activeOrders[0].masa_no;
    else if (hasBrowsing) masaNo = activeBrowsingTables[masaId].masa_no;

    document.getElementById('masaDetailTitle').innerText = getFormattedMasaNo(masaNo) + " Detayı";
    const content = document.getElementById('masaDetailContent');

    if (activeOrders.length === 0 && !hasBrowsing) {
        content.innerHTML = `<p style="text-align:center; color:#9ca3af;">Masada aktif işlem yok.</p>`;
        document.getElementById('masaDetailModal').classList.add('active');
        return;
    }

    let totalAmount = 0;
    let hasPendingApproval = false;
    let hasCashPending = false;
    let hasReady = false;
    const combinedItems = {};
    const deviceIds = new Set();

    activeOrders.forEach(order => {
        totalAmount += order.toplam_tutar;
        if (order.device_id) deviceIds.add(order.device_id);
        if (order.siparis_durumu === 'garson_onayi_bekliyor') hasPendingApproval = true;
        if (order.siparis_durumu === 'nakit_bekliyor' || (order.odeme_yontemi === 'nakit' && order.odeme_durumu !== 'odendi')) hasCashPending = true;
        if (order.siparis_durumu === 'hazir') hasReady = true;

        (order.detaylar || []).forEach(item => {
            const key = item.urun_adi + '_' + (item.urun_notu || '');
            if (!combinedItems[key]) {
                combinedItems[key] = { urun_adi: item.urun_adi, adet: 0, birim_fiyat: item.birim_fiyat, ara_toplam: 0, urun_notu: item.urun_notu || '' };
            }
            combinedItems[key].adet += item.adet;
            combinedItems[key].ara_toplam += item.ara_toplam;
        });
    });

    let html = '';
    if (!hasPendingApproval) {
        html += `
            <div style="font-size: 1.2rem; font-weight: 800; margin-bottom: 15px; text-align: center; color: #fff;">
                Masa Toplamı: <span style="color: #10b981;">${totalAmount.toFixed(2)} ₺</span>
            </div>
        `;
    }

    // Order items
    if (Object.keys(combinedItems).length > 0) {
        html += `<div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 10px; margin-bottom: 15px; max-height: 200px; overflow-y: auto;">`;
        Object.values(combinedItems).forEach(item => {
            html += `
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px;">
                    <div>
                        <div style="font-weight: 700; color:#e5e7eb;">${item.adet}x ${item.urun_adi}</div>
                        ${item.urun_notu ? `<div style="font-size: 0.75rem; color:#9ca3af;">Not: ${item.urun_notu}</div>` : ''}
                    </div>
                    ${!hasPendingApproval ? `<div style="font-weight: bold; color: #fbbf24;">${item.ara_toplam.toFixed(2)} ₺</div>` : ''}
                </div>
            `;
        });
        html += `</div>`;
    }

    // Devices / Ban logic
    if (deviceIds.size > 0) {
        html += `<div style="margin-bottom: 15px;">
            <div style="font-size:0.85rem; color:#9ca3af; margin-bottom: 4px;">Bağlı Cihazlar:</div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
        `;
        Array.from(deviceIds).forEach(did => {
            const shortDid = did.includes('-') ? did.split('-')[1].substring(0, 4).toUpperCase() : did.substring(0, 4).toUpperCase();
            html += `
                <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 8px; border-radius: 6px; display:flex; align-items:center; gap: 8px;">
                    <span style="font-size:0.8rem; color:#fca5a5;">Cihaz: ${shortDid}</span>
                    <button onclick="banDeviceDirect('${did}', ${masaId})" style="background: #ef4444; border:none; color:#fff; padding: 4px 8px; font-size:0.7rem; border-radius:4px; font-weight:bold; cursor:pointer;">BANLA</button>
                </div>
            `;
        });
        html += `</div></div>`;
    }

    // Action Buttons
    html += `<div style="display: flex; flex-direction: column; gap: 10px;">`;

    if (hasPendingApproval) {
        html += `
            <div style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); padding: 12px; border-radius: 8px;">
                <div style="color: #60a5fa; font-weight: bold; margin-bottom: 8px; text-align: center;">Sipariş Onay Talebi Var</div>
                <div style="display:flex; gap:10px;">
                    <button class="btn-status-action btn-success" style="flex:1; padding: 12px; font-size: 1rem;" onclick="approveTableOrdersDirect(${masaId}); closeMasaDetailModal();">✅ Onayla</button>
                    <button class="btn-status-action btn-warning" style="flex:1; padding: 12px; font-size: 1rem;" onclick="closeMasaDetailModal(); openEditOrderModalForTable(${masaId});">✏️ Düzenle</button>
                </div>
            </div>
        `;
    }

    if (hasCashPending) {
        html += `
            <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); padding: 12px; border-radius: 8px;">
                <div style="color: #fbbf24; font-weight: bold; margin-bottom: 8px; text-align: center;">Nakit Ödeme Bekliyor</div>
                <button class="btn-status-action btn-warning" style="width:100%; padding: 12px; font-size: 1rem;" onclick="collectCashTableDirect(${masaId}); closeMasaDetailModal();">💵 Nakit Tahsil Et</button>
            </div>
        `;
    }

    if (hasReady) {
        html += `
            <button class="btn-status-action btn-success" style="width:100%; padding: 12px; font-size: 1rem;" onclick="deliverTableOrdersDirect(${masaId}); closeMasaDetailModal();">🚀 Masaya Teslim Et</button>
        `;
    }

    if (!hasReady && !hasCashPending && !hasPendingApproval) {
        html += `
            <button style="background: transparent; border: 1px solid rgba(239, 68, 68, 0.5); color: #fca5a5; padding: 10px; border-radius: 8px; font-weight: bold; cursor: pointer;" onclick="clearMasaDirect(${masaId}); closeMasaDetailModal();">Oturumu Sonlandır</button>
        `;
    }

    html += `</div>`;

    content.innerHTML = html;
    document.getElementById('masaDetailModal').classList.add('active');
}

window.approveTableOrdersWithPin = function (masaId) {
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

window.approveTableOrdersDirect = async function (masaId) {
    if (!activeGarson) return;
    const pendingOrders = waiterOrders.filter(o => o.masa_id === masaId && o.siparis_durumu === 'garson_onayi_bekliyor');
    try {
        await Promise.all(pendingOrders.map(o =>
            fetch(`/api/siparisler/${o.id}/durum`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ yeni_durum: 'garson_onayladi_mutfakta', garson_adi: activeGarson.garson_adi })
            })
        ));
        loadWaiterData();
        showWaiterToast(`Masa ${activeGarson.garson_adi} tarafından doğrulandı! 🚀`);
    } catch (e) {
        alert("İşlem başarısız.");
    }
};

window.collectCashTableWithPin = function (masaId) {
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

window.collectCashTableDirect = async function (masaId) {
    if (!activeGarson) return;
    const cashOrders = waiterOrders.filter(o => o.masa_id === masaId && (o.siparis_durumu === 'nakit_bekliyor' || (o.odeme_yontemi === 'nakit' && o.odeme_durumu !== 'odendi')));
    try {
        await Promise.all(cashOrders.map(o =>
            fetch(`/api/siparisler/${o.id}/durum`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ yeni_durum: 'nakit_tahsil_edildi', garson_adi: activeGarson.garson_adi })
            })
        ));
        loadWaiterData();
        showWaiterToast(`Nakit ödeme ${activeGarson.garson_adi} tarafından tahsil edildi.`);
    } catch (e) {
        alert("İşlem başarısız.");
    }
};

window.deliverTableOrdersDirect = async function (masaId) {
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

window.deliverTableOrdersWithPin = function (masaId) {
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

window.clearMasaWithPin = function (masaId) {
    requireGarsonPin(async (garson) => {
        if (!confirm(`Masa oturumu ${garson.garson_adi} yetkisiyle sonlandırılacaktır. Onaylıyor musunuz?`)) return;
        try {
            const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
            if (res.ok) {
                loadWaiterData();
                showWaiterToast(`Masa oturumu ${garson.garson_adi} tarafından sonlandırıldı.`);
            }
        } catch (e) {
            alert("İşlem başarısız.");
        }
    });
};

window.clearMasaDirect = async function (masaId) {
    if (!activeGarson) return;
    if (!confirm(`Masa oturumu ${activeGarson.garson_adi} yetkisiyle sonlandırılacaktır. Onaylıyor musunuz?`)) return;
    try {
        const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
        if (res.ok) {
            loadWaiterData();
            showWaiterToast(`Masa oturumu ${activeGarson.garson_adi} tarafından sonlandırıldı.`);
        }
    } catch (e) {
        alert("İşlem başarısız.");
    }
};

window.banDeviceWithPin = function (deviceId, masaId) {
    requireGarsonPin(async (garson) => {
        if (!confirm(`Bu cihazı kalıcı olarak yasaklamak istediğinize emin misiniz? (${garson.garson_adi})`)) return;
        try {
            const res = await fetch(`/api/garson/ban-device`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId })
            });
            const data = await res.json();
            if (res.ok) {
                await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
                loadWaiterData();
                showWaiterToast(`Cihaz ${garson.garson_adi} tarafından banlandı.`);
            } else {
                alert(data.message || "İşlem başarısız.");
            }
        } catch (e) {
            alert("İşlem başarısız.");
        }
    });
};

window.banDeviceDirect = async function (deviceId, masaId) {
    if (!activeGarson) return;
    if (!confirm(`Bu cihazı kalıcı olarak yasaklamak istediğinize emin misiniz? (${activeGarson.garson_adi})`)) return;
    try {
        const res = await fetch(`/api/garson/ban-device`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId })
        });
        const data = await res.json();
        if (res.ok) {
            await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
            loadWaiterData();
            showWaiterToast(`Cihaz ${activeGarson.garson_adi} tarafından banlandı.`);
            closeMasaDetailModal();
        } else {
            alert(data.message || "İşlem başarısız.");
        }
    } catch (e) {
        alert("İşlem başarısız.");
    }
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
        } catch (e) {
            console.error("Ürünler yüklenemedi:", e);
        }
    }
}

window.openEditOrderModalForTable = async function (masaId) {
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
    if (titleEl) titleEl.innerText = `✏️ Masa ${getFormattedMasaNo(currentEditOrder.masa_no)} Siparişini Düzenle`;

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

window.changeEditItemQty = function (index, delta) {
    if (!currentEditItems[index]) return;
    currentEditItems[index].adet += delta;
    if (currentEditItems[index].adet <= 0) {
        currentEditItems.splice(index, 1);
    }
    renderEditOrderItems();
};

window.removeEditItem = function (index) {
    currentEditItems.splice(index, 1);
    renderEditOrderItems();
};

window.addSelectedProductToEditOrder = function () {
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

window.closeEditOrderModal = function () {
    const masaId = currentEditOrder ? currentEditOrder.masa_id : null;
    currentEditOrder = null;
    currentEditItems = [];
    const modal = document.getElementById('editOrderModal');
    if (modal) modal.classList.remove('active');
    if (masaId) {
        openMasaDetail(masaId);
    }
};

window.saveEditedOrder = async function () {
    if (!currentEditOrder) return;

    if (currentEditItems.length === 0) {
        alert("Siparişte en az 1 ürün bulunmalıdır.");
        return;
    }

    if (!activeGarson) return;

    const totalAmount = currentEditItems.reduce((acc, item) => acc + (item.adet * item.birim_fiyat), 0);
    const payload = {
        toplam_tutar: totalAmount,
        garson_adi: activeGarson.garson_adi,
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
            showWaiterToast(`✏️ Sipariş ${activeGarson.garson_adi} tarafından güncellendi!`);
        } else {
            const errData = await res.json().catch(() => ({}));
            alert(errData.detail || "Sipariş güncelleme başarısız.");
        }
    } catch (e) {
        alert("Sunucu bağlantı hatası. Lütfen ağınızı kontrol edin.");
    }
};

function updateActiveGarsonBadge() {
    const badge = document.getElementById('activeGarsonBadge');
    const logoutBtn = document.getElementById('garsonLogoutBtn');
    if (activeGarson) {
        if (badge) {
            badge.innerHTML = `👤 ${activeGarson.garson_adi}`;
            badge.style.background = 'rgba(16, 185, 129, 0.15)';
            badge.style.color = '#34d399';
            badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        }
        if (logoutBtn) logoutBtn.style.display = 'block';
    } else {
        if (badge) {
            badge.innerHTML = `🔑 Giriş Yapılmadı`;
            badge.style.background = 'rgba(99, 102, 241, 0.15)';
            badge.style.color = '#a5b4fc';
            badge.style.borderColor = 'rgba(99, 102, 241, 0.4)';
        }
        if (logoutBtn) logoutBtn.style.display = 'none';
    }
}

window.logoutGarson = function () {
    localStorage.removeItem('activeGarsonSession');
    activeGarson = null;
    updateActiveGarsonBadge();
    showWaiterToast("Garson oturumu kapatıldı.");
};

