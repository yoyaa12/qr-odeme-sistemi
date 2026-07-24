// ==========================================================================
// WAITER PANEL (GARSON PANELİ) LOGIC (GÜNCELLENMİŞ - 6 HANELİ PIN DESTEKLİ)
// ==========================================================================

let waiterOrders = [];
let tables = [];
let currentPinDigits = [];
let activeGarson = null;
let pendingActionCallback = null;

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
function restoreGarsonSession() {
    try {
        const saved = localStorage.getItem('activeGarsonSession');
        if (saved) {
            activeGarson = JSON.parse(saved);
            updateGarsonBadge();
        }
    } catch(e) {}
}

function updateGarsonBadge() {
    const badge = document.getElementById('activeGarsonBadge');
    if (badge) {
        if (activeGarson) {
            badge.innerHTML = `👤 Garson: <strong>${activeGarson.garson_adi}</strong> (Oturum Açık)`;
            badge.style.borderColor = 'var(--success)';
            badge.style.color = '#34d399';
        } else {
            badge.innerHTML = `🔑 Garson Giriş Yap / Şifre Değiştir`;
            badge.style.borderColor = 'var(--primary)';
            badge.style.color = 'var(--primary)';
        }
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
        const slot = document.getElementById(`pinSlot${i}`);
        if (slot) {
            if (i <= currentPinDigits.length) {
                slot.classList.add('filled');
                slot.innerText = '•'; // Şifre noktası
            } else {
                slot.classList.remove('filled', 'success', 'error');
                slot.innerText = '';
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

            activeGarson = data.garson;
            localStorage.setItem('activeGarsonSession', JSON.stringify(activeGarson));
            updateGarsonBadge();

            // ÖNEMLİ: Callback fonksiyonunu modal kapatılmadan ÖNCE yerel değişkene alıyoruz!
            const actionToExecute = pendingActionCallback;

            setTimeout(() => {
                closeGarsonPinModal();
                showWaiterToast(`Hoş geldin ${activeGarson.garson_adi}! İşlem yapılıyor... 🚀`);
                if (typeof actionToExecute === 'function') {
                    actionToExecute(activeGarson);
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
        
        const allOrders = await ordersRes.json();
        tables = await tablesRes.json();

        waiterOrders = allOrders.filter(o => ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        renderWaiterDashboard();
        renderFloorMap();
    } catch (e) {
        console.error("Garson verileri yüklenemedi:", e);
    }
}

window.toggleFloorMapModal = function() {
    const modal = document.getElementById('floorMapModal');
    if (modal) {
        modal.classList.toggle('active');
        if (modal.classList.contains('active')) {
            renderFloorMap();
        }
    }
};

window.renderFloorMap = async function() {
    const terraceContainer = document.getElementById('zoneTerraceTables');
    const indoorContainer = document.getElementById('zoneIndoorTables');
    const vipContainer = document.getElementById('zoneVipTables');

    if (!terraceContainer || !indoorContainer || !vipContainer) return;

    if (!tables || tables.length === 0) {
        try {
            const res = await fetch('/api/masalar');
            tables = await res.json();
        } catch(e) {}
    }

    let terraceHTML = '';
    let indoorHTML = '';
    let vipHTML = '';

    tables.forEach((table, index) => {
        const activeOrder = waiterOrders.find(o => o.masa_id === table.id && ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));
        
        let statusClass = 'status-bos';
        let statusText = '🟢 Boş';
        
        if (activeOrder) {
            if (activeOrder.siparis_durumu === 'garson_onayi_bekliyor') {
                statusClass = 'status-nakit_bekliyor';
                statusText = '🛎️ Onay Bekliyor';
            } else if (activeOrder.siparis_durumu === 'nakit_bekliyor' || (activeOrder.odeme_yontemi === 'nakit' && activeOrder.odeme_durumu !== 'odendi')) {
                statusClass = 'status-nakit_bekliyor';
                statusText = '🟡 Nakit Bekliyor';
            } else if (activeOrder.siparis_durumu === 'hazir') {
                statusClass = 'status-hazir';
                statusText = '🔵 Mutfakta Hazır';
            } else {
                statusClass = 'status-dolu';
                statusText = '🔴 Sipariş Var';
            }
        }

        const tableCardHTML = `
            <div class="table-node-card ${statusClass}" onclick="focusOrderCard(${activeOrder ? activeOrder.id : null})">
                <div class="table-node-number">🪑 ${table.masa_no}</div>
                <div class="table-node-badge">${statusText}</div>
            </div>
        `;

        if (index % 3 === 0) {
            terraceHTML += tableCardHTML;
        } else if (index % 3 === 1) {
            indoorHTML += tableCardHTML;
        } else {
            vipHTML += tableCardHTML;
        }
    });

    terraceContainer.innerHTML = terraceHTML || '<div style="font-size:0.75rem; color:var(--text-muted);">Masa yok</div>';
    indoorContainer.innerHTML = indoorHTML || '<div style="font-size:0.75rem; color:var(--text-muted);">Masa yok</div>';
    vipContainer.innerHTML = vipHTML || '<div style="font-size:0.75rem; color:var(--text-muted);">Masa yok</div>';
};

window.focusOrderCard = function(orderId) {
    requireGarsonPin((garson) => {
        toggleFloorMapModal();
    });
};

function renderWaiterDashboard() {
    const container = document.getElementById('waiterDashboardGrid');
    if (!container) return;

    const activeOrders = waiterOrders.filter(o => ['garson_onayi_bekliyor', 'nakit_bekliyor', 'odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir'].includes(o.siparis_durumu));

    if (activeOrders.length === 0) {
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
                    <div>
                        <div class="order-table-title">🪑 ${group.masa_no}</div>
                        <div class="order-code">Toplam Masa Hesabı: ${group.total_amount.toFixed(2)} ₺</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="table-badge" style="background: ${badgeColor}; font-weight:800;">
                            ${badgeText}
                        </span>
                    </div>
                </div>

                ${group.has_pending_approval ? `
                    <div style="background: rgba(59, 130, 246, 0.18); border: 1.5px solid #3b82f6; padding: 12px; border-radius: var(--radius-md); margin-bottom: 10px;">
                        <div style="font-weight: 800; color: #60a5fa; font-size: 0.95rem; margin-bottom: 4px;">
                            🛎️ MASADAN SİPARİŞ ONAY TALEBİ (${group.total_amount.toFixed(2)} ₺)
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Masadan yeni sipariş verildi. Masaya gidip PIN doğrulama ile tek tıkla mutfağa aktarınız.
                        </div>
                        <div style="display:flex; gap: 8px; flex-wrap: wrap;">
                            <button class="btn-status-action btn-success" style="padding: 8px 14px; font-size: 0.88rem; flex:1;" onclick="approveTableOrdersWithPin(${group.masa_id})">
                                ✅ Masadaki Tüm Siparişleri Doğrula & Mutfağa Gönder
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

                <div style="display:flex; flex-direction:column; gap: 8px; margin-top: 10px;">
                    ${group.has_ready ? `
                        <button class="btn-status-action btn-success" onclick="deliverTableOrdersWithPin(${group.masa_id})">
                            🚀 Masaya Teslim Et (Siparişi Kapat)
                        </button>
                    ` : (group.has_cash_pending || group.has_pending_approval ? '' : `
                        <div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; width: 100%; padding: 4px;">
                            ⏳ Mutfakta Hazırlanıyor...
                        </div>
                    `)}
                    <button class="btn-status-action btn-danger" style="font-size:0.8rem; padding:6px;" onclick="clearMasaWithPin(${group.masa_id})">
                        🧹 Masayı Temizle / Oturumu Kapat (CLEAR)
                    </button>
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
        if (!confirm(`Masa ${garson.garson_adi} yetkisiyle temizlenecek ve oturum kapatılacaktır. Onaylıyor musunuz?`)) return;
        try {
            const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
            if (res.ok) {
                loadWaiterData();
                showWaiterToast(`Masa ${garson.garson_adi} tarafından temizlendi ve sıfırlandı! 🧹`);
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

