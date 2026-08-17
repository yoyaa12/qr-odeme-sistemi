const escapeHtml = window.SecurityText.escapeHtml;

let kasaTables = [];
let kasaOrders = [];
let kasaDynamicQRs = {};
let activeMasaId = null;
let activeFilter = 'all';
let currentTableItems = [];

// VEGA İSKONTO VE ÖDEME DURUMLARI
let discountType = 'percent'; // 'percent' or 'amount'
let discountValue = 0;
let partialPaymentsMap = {};

// GRUPLANMIŞ ADİSYON (SEÇENEK 1) & AYRINTILAR DURUMU
let ticketViewMode = 'grouped'; // 'grouped' veya 'batches'
let expandedGroupDetailsMap = {};
let renderedGroupKeys = [];

window.setTicketViewMode = function (mode) {
    ticketViewMode = mode;
    renderActiveTicketWorkstation();
};

window.toggleGroupDetails = function (groupIndex, event) {
    if (event) event.stopPropagation();
    const groupKey = renderedGroupKeys[groupIndex];
    if (groupKey === undefined) return;
    expandedGroupDetailsMap[groupKey] = !expandedGroupDetailsMap[groupKey];
    const box = document.getElementById(`groupDetails_${groupIndex}`);
    const btn = document.getElementById(`btnAyrintilar_${groupIndex}`);
    if (box) {
        box.style.display = expandedGroupDetailsMap[groupKey] ? 'block' : 'none';
    }
    if (btn) {
        btn.textContent = expandedGroupDetailsMap[groupKey] ? '▲ Gizle' : '🔍 Ayrıntılar';
    }
};

function updateKasaSocketBadge(isConnected) {
    const badge = document.getElementById('socketStatusBadge');
    if (badge) {
        badge.innerHTML = isConnected ? `🟢 Canlı Bağlantı` : `🔴 Bağlantı Kesildi`;
        badge.className = isConnected ? `socket-badge connected` : `socket-badge disconnected`;
    }
}

function updateDynamicQRBadgeTimers() {
    Object.keys(kasaDynamicQRs).forEach(mId => {
        const qr = kasaDynamicQRs[mId];
        const timerEl = document.getElementById(`qrTimer_${mId}`);
        if (timerEl && qr) {
            timerEl.innerText = `${qr.remaining_seconds}s`;
        }
    });
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
    } catch (e) { }
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

/**
 * Para ve masa kapatma gibi geri alinamaz POST'lar icin.
 * Basarisiz yanitta hata firlatir; cagiran taraf kullaniciya bildirmek
 * zorunda kalir. Sessizce yutulan 401/403/500 yuzunden "butona bastim ama
 * bir sey olmadi" durumu olusmamali.
 */
async function apiPost(url, body) {
    const options = { method: 'POST' };
    if (body !== undefined) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(body);
    }

    const res = await authFetch(url, options);
    if (!res.ok) {
        let detail = '';
        try {
            const payload = await res.json();
            if (payload && payload.detail) detail = payload.detail;
        } catch (e) { }
        throw new Error(detail || `Sunucu ${res.status} yanıtı döndü.`);
    }
    return res;
}

let kasaSocket = null;

function initKasaSocket() {
    const token = getStaffToken();
    if (kasaSocket) {
        try {
            kasaSocket.disconnect();
        } catch (e) { }
        kasaSocket = null;
    }

    kasaSocket = io({
        auth: { token: token },
        query: { token: token || '' },
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000
    });

    kasaSocket.on('connect', () => updateKasaSocketBadge(true));
    kasaSocket.on('disconnect', () => updateKasaSocketBadge(false));

    kasaSocket.on('durum_guncellendi', () => loadKasaData());
    kasaSocket.on('yeni_siparis', () => loadKasaData());
    kasaSocket.on('masa_durumu_degisti', () => loadKasaData());
    kasaSocket.on('masa_tasindi', () => loadKasaData());
    kasaSocket.on('garson_onay_talebi', () => loadKasaData());
    kasaSocket.on('nakit_odeme_talebi', () => loadKasaData());
    kasaSocket.on('nakit_odendi', () => loadKasaData());
    kasaSocket.on('masa_temizlendi', () => loadKasaData());
}

window.addEventListener('staff-authenticated', () => {
    initKasaSocket();
    loadKasaData();
});

window.addEventListener('staff-auth-cleared', () => {
    if (kasaSocket) {
        kasaSocket.disconnect();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    loadKasaData();

    setInterval(() => {
        let needRefresh = false;
        Object.keys(kasaDynamicQRs).forEach(mId => {
            if (kasaDynamicQRs[mId] && kasaDynamicQRs[mId].remaining_seconds > 0) {
                kasaDynamicQRs[mId].remaining_seconds -= 1;
            } else {
                needRefresh = true;
            }
        });
        if (needRefresh) {
            loadKasaData();
        } else {
            updateDynamicQRBadgeTimers();
        }
    }, 1000);

    if (getStaffToken()) {
        initKasaSocket();
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            const activeModal = document.querySelector('.modal-overlay.active');
            if (activeModal) {
                activeModal.classList.remove('active');
                return;
            }
            const masaDetay = document.getElementById('viewMasaDetay');
            if (masaDetay && masaDetay.style.display !== 'none') {
                closeMasaDetayView();
                return;
            }
        }
        if (['F1', 'F2', 'F3', 'F4', 'F6', 'F7', 'F8'].includes(e.key)) {
            e.preventDefault();
            handleShortcut(e.key);
        }
    });
});

async function loadKasaData() {
    try {
        const [tablesRes, ordersRes, qrsRes, tahsRes] = await Promise.all([
            authFetch('/api/masalar'),
            authFetch('/api/siparisler'),
            authFetch('/api/masalar/all-dynamic-qrs'),
            authFetch('/api/masalar/all-tahsilatlar')
        ]);
        const tablesData = await tablesRes.json();
        const ordersData = await ordersRes.json();

        kasaTables = Array.isArray(tablesData) ? tablesData : [];
        kasaOrders = Array.isArray(ordersData) ? ordersData : [];

        if (qrsRes.ok) {
            kasaDynamicQRs = await qrsRes.json();
        }
        if (tahsRes.ok) {
            partialPaymentsMap = await tahsRes.json();
        }

        updateFilterCounts();
        renderKasaGrid();

        if (activeMasaId) {
            renderActiveTicketWorkstation();
        }
    } catch (e) {
        console.error("Kasa verileri yüklenemedi:", e);
    }
}

function updateFilterCounts() {
    let cntDolu = 0;
    let cntHesap = 0;
    let cntBos = 0;

    kasaTables.forEach(t => {
        const masaOrders = kasaOrders.filter(o => o.masa_id == t.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
        const isHesap = t.durum === 'hesap_istendi';
        const isDolu = t.durum === 'dolu' || masaOrders.length > 0;

        if (isHesap) {
            cntHesap++;
        } else if (isDolu) {
            cntDolu++;
        } else {
            cntBos++;
        }
    });

    document.getElementById('cntAll').innerText = kasaTables.length;
    document.getElementById('cntDolu').innerText = cntDolu;
    document.getElementById('cntHesap').innerText = cntHesap;
    document.getElementById('cntBos').innerText = cntBos;
}

window.filterKasaTables = function (filterType) {
    activeFilter = filterType;
    document.querySelectorAll('.vega-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filterType);
    });
    renderKasaGrid();
};

function getFormattedMasaNo(masa_no) {
    if (!masa_no) return '';
    if (masa_no.startsWith('S-')) {
        return 'Salon ' + masa_no.substring(2);
    } else if (masa_no.startsWith('B-')) {
        return 'Bahçe ' + masa_no.substring(2);
    }
    return masa_no;
}

function renderKasaGrid() {

    const query = (document.getElementById('kasaSearchInput')?.value || '').toLowerCase().trim();

    let filtered = kasaTables.filter(t => {
        const masaOrders = kasaOrders.filter(o => o.masa_id == t.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
        const isHesap = t.durum === 'hesap_istendi';
        const isDolu = t.durum === 'dolu' || masaOrders.length > 0;

        let nameLower = t.masa_no.toLowerCase();
        let queryMatched = nameLower.includes(query);
        if (!queryMatched) {
            let formattedLower = getFormattedMasaNo(t.masa_no).toLowerCase();
            queryMatched = formattedLower.includes(query);
        }
        if (query && !queryMatched) return false;

        if (activeFilter === 'dolu') return isDolu && !isHesap;
        if (activeFilter === 'hesap') return isHesap;
        if (activeFilter === 'bos') return !isDolu && !isHesap;
        return true;
    });

    let salonHtml = '';
    let bahceHtml = '';

    filtered.forEach(t => {
        const masaOrders = kasaOrders.filter(o => o.masa_id == t.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
        const isHesap = t.durum === 'hesap_istendi';
        const isDolu = t.durum === 'dolu' || masaOrders.length > 0;
        const totalBill = masaOrders.reduce((sum, o) => sum + (parseFloat(o.toplam_tutar) || 0), 0);

        let statusClass = 'status-bos';
        if (isHesap) {
            statusClass = 'status-hesap';
        } else if (isDolu) {
            statusClass = 'status-dolu';
        }

        const isSelected = activeMasaId == t.id;
        const isSourceSelected = moveSourceTableId == t.id;
        const formattedMasaNo = getFormattedMasaNo(t.masa_no);
        const isSalon = t.masa_no.startsWith('S-');

        const cardHtml = `
            <div class="vega-table-card ${statusClass} ${isSelected ? 'selected-table' : ''} ${isSourceSelected ? 'source-selected' : ''}" onclick="selectKasaMasa(${t.id})" style="position:relative;">
                <button type="button" class="card-qr-badge-btn" onclick="event.stopPropagation(); showDynamicQRModal(${t.id})" title="Masaya Ait Canlı QR Kodunu Aç" style="position:absolute; top:50%; transform:translateY(-50%); right:10px; width:60px; height:60px; background:rgba(99, 102, 241, 0.25); color:#a5b4fc; border:1px solid rgba(99, 102, 241, 0.5); border-radius:10px; font-size:1rem; font-weight:800; cursor:pointer; z-index:10; display:flex; align-items:center; justify-content:center; padding:0; box-shadow:0 4px 10px rgba(0,0,0,0.3);">
                    QR
                </button>
                <div class="card-table-no">🪑 ${formattedMasaNo}</div>
                ${isDolu || isHesap ? `
                    <div class="card-table-bill">${totalBill.toFixed(2)} ₺</div>
                    <div class="card-table-count">${masaOrders.length} Sipariş</div>
                ` : `
                    <div class="card-table-empty">Masa Boş</div>
                `}
            </div>
        `;

        if (isSalon) {
            salonHtml += cardHtml;
        } else {
            bahceHtml += cardHtml;
        }
    });

    const salonContainer = document.getElementById('kasaGridSalon');
    const bahceContainer = document.getElementById('kasaGridBahce');

    if (salonContainer) {
        salonContainer.innerHTML = salonHtml || `<div style="color:var(--text-muted); padding:20px; grid-column:1/-1; text-align:center;">Masa bulunamadı.</div>`;
    }
    if (bahceContainer) {
        bahceContainer.innerHTML = bahceHtml || `<div style="color:var(--text-muted); padding:20px; grid-column:1/-1; text-align:center;">Masa bulunamadı.</div>`;
    }
}


window.selectKasaMasa = function (tableId) {
    if (isTableMoveMode) {
        handleTableClickInMoveMode(tableId);
        return;
    }
    activeMasaId = tableId;
    discountValue = 0;
    isHalfModeSelected = false;

    const nakitEl = document.getElementById('tutarNakitInput');
    const kartEl = document.getElementById('tutarKartInput');
    if (nakitEl) nakitEl.value = '';
    if (kartEl) kartEl.value = '';

    const viewGrid = document.getElementById('viewMasaHaritasi');
    const viewDetay = document.getElementById('viewMasaDetay');

    if (viewGrid) viewGrid.style.display = 'none';
    if (viewDetay) viewDetay.style.display = 'flex';

    const banner = document.getElementById('paymentFeedbackBanner');
    if (banner) banner.style.display = 'none';

    renderKasaGrid();
    renderActiveTicketWorkstation();
};

window.closeMasaDetayView = function () {
    activeMasaId = null;
    discountValue = 0;
    isHalfModeSelected = false;

    const nakitEl = document.getElementById('tutarNakitInput');
    const kartEl = document.getElementById('tutarKartInput');
    if (nakitEl) nakitEl.value = '';
    if (kartEl) kartEl.value = '';

    const viewGrid = document.getElementById('viewMasaHaritasi');
    const viewDetay = document.getElementById('viewMasaDetay');

    if (viewDetay) viewDetay.style.display = 'none';
    if (viewGrid) viewGrid.style.display = 'flex';

    const banner = document.getElementById('paymentFeedbackBanner');
    if (banner) banner.style.display = 'none';

    renderKasaGrid();
};

window.toggleRowSelection = function (index) {
    if (currentTableItems[index]) {
        if (currentTableItems[index].isFullyPaid) return;
        currentTableItems[index].selected = !currentTableItems[index].selected;
        renderActiveTicketWorkstation();
    }
};

window.paySingleSiparisBatch = async function (siparisId, tutar) {
    const onaylandi = await appConfirm(
        `Fiş #${siparisId} paketinin ${tutar.toFixed(2)} ₺ tutarındaki ödemesini alıp kapatmak istiyor musunuz?`,
        { title: '💵 Fiş Ödemesi', okText: 'Evet, ödemeyi al' }
    );
    if (!onaylandi) return;
    try {
        const res = await fetch(`/api/siparisler/${siparisId}/durum`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                yeni_durum: 'nakit_tahsil_edildi',
                garson_adi: 'Kasa Yetkilisi'
            })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            const banner = document.getElementById('paymentFeedbackBanner');
            const feedbackText = document.getElementById('feedbackText');
            if (banner && feedbackText) {
                feedbackText.innerText = `Fiş #${siparisId} (${tutar.toFixed(2)} ₺) Tahsil Edildi ve Kapatıldı!`;
                banner.style.display = 'flex';
            }
            await loadKasaData();
            renderActiveTicketWorkstation();
        } else {
            appAlert("Fiş tahsilatı yapılırken hata oluştu: " + (data.message || 'Bilinmeyen hata'));
        }
    } catch (e) {
        console.error("Single batch pay error:", e);
        appAlert("Bağlantı hatası!");
    }
};

function renderActiveTicketWorkstation() {
    const table = kasaTables.find(t => t.id == activeMasaId);
    const titleEl = document.getElementById('ticketMasaTitle');
    const badgeEl = document.getElementById('ticketMasaStatusBadge');
    const metaEl = document.getElementById('ticketMetaInfo');
    const tbody = document.getElementById('ticketItemsBody');
    renderedGroupKeys = [];

    if (!table) {
        if (titleEl) titleEl.innerText = "🪑 MASA SEÇİLMEDİ";
        if (badgeEl) { badgeEl.innerText = "Masa Seçiniz"; badgeEl.className = "vega-badge-status"; }
        if (metaEl) metaEl.innerText = "";
        if (tbody) tbody.innerHTML = `<div class="vega-empty-ticket" style="text-align:center; padding:40px 20px; color:var(--text-muted);"><div style="font-size:2.5rem; margin-bottom:8px;">🛒</div><div>Lütfen masalar ekranından bir masaya tıklayınız.</div></div>`;
        updateFinancialSummary(0, 0);
        return;
    }

    const allMasaOrders = kasaOrders.filter(o => o.masa_id == table.id && o.siparis_durumu !== 'iptal' && o.siparis_durumu !== 'odendi_kapatildi');
    const openMasaOrders = allMasaOrders.filter(o => o.odeme_durumu !== 'odendi');

    const isHesap = table.durum === 'hesap_istendi';
    const isDolu = table.durum === 'dolu' || openMasaOrders.length > 0;

    if (titleEl) titleEl.innerText = `🪑 ${getFormattedMasaNo(table.masa_no)} - ADİSYON DETAYI`;
    if (badgeEl) {
        badgeEl.innerText = isHesap ? '🟡 HESAP İSTENDİ' : (isDolu ? '🔴 HESAP AÇIK' : '🟢 BOŞ');
        badgeEl.className = isHesap ? 'vega-badge-status status-hesap' : (isDolu ? 'vega-badge-status status-dolu' : 'vega-badge-status status-bos');
    }

    const isFirstLoad = (currentTableItems.length === 0);
    const selectedStateMap = {};
    const ikramStateMap = {};
    if (!isFirstLoad) {
        currentTableItems.forEach(item => {
            selectedStateMap[item.uniqueId] = item.selected;
            ikramStateMap[item.uniqueId] = item.isIkram;
        });
    }

    currentTableItems = [];
    let grandTotalSum = 0;
    let alreadyPaidSum = 0;

    if (allMasaOrders.length === 0 || openMasaOrders.length === 0 || table.durum === 'bos') {
        currentTableItems = [];
        if (metaEl) {
            metaEl.innerHTML = `<span>Açık Sipariş Bulunmuyor</span>`;
        }
        if (tbody) {
            tbody.innerHTML = `<div class="vega-empty-ticket" style="text-align:center; padding:40px 20px; color:var(--text-muted);"><div style="font-size:2.5rem; margin-bottom:8px;">🍽️</div><div>Bu masaya ait sipariş bulunmuyor.</div></div>`;
        }
        updateFinancialSummary(0, 0);
        return;
    } else {
        const modeSelectorHtml = `
            <div style="display:flex; gap:8px; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px;">
                <button type="button" class="btn-add" style="flex:1; justify-content:center; padding:8px; font-size:0.88rem; font-weight:800; background:${ticketViewMode === 'grouped' ? 'linear-gradient(135deg, #6366f1, #4f46e5)' : 'rgba(255,255,255,0.06)'}; color:${ticketViewMode === 'grouped' ? '#fff' : '#cbd5e1'};" onclick="setTicketViewMode('grouped')">
                    📊 Gruplanmış Adisyon (Tek Satır)
                </button>
                <button type="button" class="btn-add" style="flex:1; justify-content:center; padding:8px; font-size:0.88rem; font-weight:800; background:${ticketViewMode === 'batches' ? 'linear-gradient(135deg, #6366f1, #4f46e5)' : 'rgba(255,255,255,0.06)'}; color:${ticketViewMode === 'batches' ? '#fff' : '#cbd5e1'};" onclick="setTicketViewMode('batches')">
                    📦 Fiş Paketleri (${allMasaOrders.length} Paket)
                </button>
            </div>
        `;

        if (ticketViewMode === 'grouped') {
            const groupedMap = {};

            allMasaOrders.forEach((o) => {
                const isOrderPaid = (o.odeme_durumu === 'odendi');
                let timeStr = '';
                if (o.olusturma_tarihi) {
                    if (o.olusturma_tarihi.includes('T')) {
                        timeStr = o.olusturma_tarihi.split('T')[1].substring(0, 5);
                    } else if (o.olusturma_tarihi.length >= 16) {
                        timeStr = o.olusturma_tarihi.substring(11, 16);
                    } else {
                        timeStr = o.olusturma_tarihi;
                    }
                }

                (o.detaylar || []).forEach(d => {
                    const groupKey = `${d.urun_id}_${d.birim_fiyat}_${(d.urun_notu || '').trim().toLowerCase()}`;
                    if (!groupedMap[groupKey]) {
                        groupedMap[groupKey] = {
                            urun_id: d.urun_id,
                            urun_adi: d.urun_adi,
                            birim_fiyat: parseFloat(d.birim_fiyat) || 0,
                            urun_notu: d.urun_notu || '',
                            toplam_adet: 0,
                            toplam_ara: 0,
                            paid_adet: 0,
                            unpaid_adet: 0,
                            orders_list: []
                        };
                    }
                    const adet = parseInt(d.adet) || 1;
                    const ara = parseFloat(d.ara_toplam) || (adet * parseFloat(d.birim_fiyat) || 0);

                    groupedMap[groupKey].toplam_adet += adet;
                    groupedMap[groupKey].toplam_ara += ara;

                    if (isOrderPaid) {
                        groupedMap[groupKey].paid_adet += adet;
                    } else {
                        groupedMap[groupKey].unpaid_adet += adet;
                    }

                    groupedMap[groupKey].orders_list.push({
                        siparis_id: o.id,
                        timeStr: timeStr,
                        garson_adi: o.garson_adi || 'Müşteri QR',
                        adet: adet,
                        ara: ara,
                        isPaid: isOrderPaid
                    });
                });
            });

            let itemIndex = 0;
            let rowsHtml = '';

            Object.keys(groupedMap).forEach(key => {
                const grp = groupedMap[key];
                renderedGroupKeys[itemIndex] = key;
                const uniqueId = `item_grp_${grp.urun_id}_${itemIndex}`;
                const isFullyPaid = (grp.unpaid_adet === 0 && grp.paid_adet > 0);
                const wasSelected = isFullyPaid ? false : (selectedStateMap[uniqueId] || false);
                const wasIkram = ikramStateMap[uniqueId] || false;

                const itemObj = {
                    index: itemIndex,
                    uniqueId: uniqueId,
                    urun_id: grp.urun_id,
                    urun_adi: grp.urun_adi,
                    adet: grp.toplam_adet,
                    birim_fiyat: grp.birim_fiyat,
                    ara_toplam: grp.toplam_ara,
                    unpaid_adet: grp.unpaid_adet,
                    paid_adet: grp.paid_adet,
                    selected: wasSelected,
                    isIkram: wasIkram,
                    isFullyPaid: isFullyPaid
                };
                currentTableItems.push(itemObj);

                const lineTotal = parseFloat(grp.toplam_ara) || 0;
                const paidLineSum = (grp.paid_adet || 0) * (parseFloat(grp.birim_fiyat) || 0);

                if (!wasIkram) {
                    grandTotalSum += lineTotal;
                }
                alreadyPaidSum += paidLineSum;

                let sublinesHtml = '';
                grp.orders_list.forEach(sub => {
                    sublinesHtml += `
                        <div class="detail-subline ${sub.isPaid ? 'paid-line' : 'unpaid-line'}">
                            <span>📦 Fiş #${escapeHtml(sub.siparis_id)} ${sub.timeStr ? `(${escapeHtml(sub.timeStr)})` : ''} - ${escapeHtml(sub.garson_adi)}: ${sub.adet} Adet</span>
                            <strong>${sub.ara.toFixed(2)} ₺ ${sub.isPaid ? '✅ (Ödendi)' : '⏳ (Açık)'}</strong>
                        </div>
                    `;
                });

                const isExpanded = expandedGroupDetailsMap[key] || false;

                rowsHtml += `
                    <tr class="ticket-row-clickable ${wasSelected ? 'selected-row' : ''} ${isFullyPaid ? 'paid-row-disabled' : ''}" 
                        ${isFullyPaid ? 'style="opacity: 0.55; background: rgba(15,23,42,0.4); cursor: not-allowed;"' : `onclick="toggleRowSelection(${itemIndex})"`}>
                        <td style="padding:10px 8px;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <input type="checkbox" ${isFullyPaid ? 'disabled' : (wasSelected ? 'checked' : '')} 
                                    ${isFullyPaid ? '' : `onclick="event.stopPropagation(); toggleRowSelection(${itemIndex})"`} 
                                    style="width:18px; height:18px; cursor:${isFullyPaid ? 'not-allowed' : 'pointer'};">
                                <div>
                                    <strong style="color:${isFullyPaid ? '#94a3b8' : '#fff'}; font-size:0.95rem; ${isFullyPaid ? 'text-decoration: line-through;' : ''}">
                                        ${escapeHtml(grp.urun_adi)}
                                    </strong>
                                    ${grp.urun_notu ? `<div style="font-size:0.75rem; color:#f59e0b; font-style:italic;">📝 ${escapeHtml(grp.urun_notu)}</div>` : ''}
                                    <button type="button" id="btnAyrintilar_${itemIndex}" class="btn-ayrintilar-chip" onclick="toggleGroupDetails(${itemIndex}, event)">
                                        ${isExpanded ? '▲ Gizle' : '🔍 Ayrıntılar'}
                                    </button>
                                </div>
                            </div>
                            <div id="groupDetails_${itemIndex}" class="grouped-details-box" style="display:${isExpanded ? 'block' : 'none'};">
                                <div class="grouped-details-header">📋 Fiş & Zaman Ayrıntıları:</div>
                                ${sublinesHtml}
                            </div>
                        </td>
                        <td style="text-align:center; font-weight:800; font-size:1rem; color:#cbd5e1; ${isFullyPaid ? 'text-decoration: line-through;' : ''}">${grp.toplam_adet}</td>
                        <td style="text-align:right; font-weight:700; color:#cbd5e1; ${isFullyPaid ? 'text-decoration: line-through;' : ''}">${grp.birim_fiyat.toFixed(2)} ₺</td>
                        <td style="text-align:right;">
                            ${isFullyPaid
                        ? `<span style="background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.4); padding:3px 8px; border-radius:6px; font-size:0.8rem; font-weight:800;">✅ ÖDENDİ</span>`
                        : (wasIkram
                            ? `<span style="background:rgba(239,68,68,0.2); color:#f87171; padding:2px 6px; border-radius:4px; font-weight:800; font-size:0.75rem;">🎁 İKRAM</span>`
                            : `<span style="color:#64748b;">-</span>`)}
                        </td>
                        <td style="text-align:right; font-weight:900; font-size:1.05rem; color:${isFullyPaid ? '#64748b' : (wasIkram ? '#f87171' : '#34d399')}; ${isFullyPaid ? 'text-decoration: line-through;' : ''}">
                            ${wasIkram ? '0.00 ₺' : `${grp.toplam_ara.toFixed(2)} ₺`}
                        </td>
                    </tr>
                `;
                itemIndex++;
            });

            const tableHtml = `
                ${modeSelectorHtml}
                <table class="vega-ticket-table" style="width:100%;">
                    <thead>
                        <tr>
                            <th>Ürün Adı & Ayrıntılar</th>
                            <th style="text-align:center; width:50px;">Adet</th>
                            <th style="text-align:right; width:90px;">Fiyat</th>
                            <th style="text-align:right; width:80px;">Durum</th>
                            <th style="text-align:right; width:90px;">Toplam</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            `;

            if (tbody) tbody.innerHTML = tableHtml;
        } else {
            let batchesHtml = modeSelectorHtml;

            allMasaOrders.forEach((o) => {
                const orderId = Number(o.id);
                if (!Number.isInteger(orderId) || orderId <= 0) return;
                let itemsRows = '';
                let batchTotal = 0;

                (o.detaylar || []).forEach(d => {
                    const adet = parseInt(d.adet) || 1;
                    const bFiyat = parseFloat(d.birim_fiyat) || 0;
                    const ara = parseFloat(d.ara_toplam) || (adet * bFiyat);
                    batchTotal += ara;

                    itemsRows += `
                        <tr>
                            <td>
                                <strong>${escapeHtml(d.urun_adi)}</strong>
                                ${d.urun_notu ? `<div style="font-size:0.75rem; color:#f59e0b;">Not: ${escapeHtml(d.urun_notu)}</div>` : ''}
                            </td>
                            <td style="text-align:center;">${adet}</td>
                            <td style="text-align:right;">${bFiyat.toFixed(2)} ₺</td>
                            <td style="text-align:right; color:#64748b;">-</td>
                            <td style="text-align:right; font-weight:800; color:#34d399;">${ara.toFixed(2)} ₺</td>
                        </tr>
                    `;
                });

                const isPaid = (o.odeme_durumu === 'odendi');
                let createdTimeStr = '';
                if (o.olusturma_tarihi) {
                    if (o.olusturma_tarihi.includes('T')) {
                        createdTimeStr = o.olusturma_tarihi.split('T')[1].substring(0, 5);
                    } else if (o.olusturma_tarihi.length >= 16) {
                        createdTimeStr = o.olusturma_tarihi.substring(11, 16);
                    } else {
                        createdTimeStr = o.olusturma_tarihi;
                    }
                }

                batchesHtml += `
                    <div class="batch-card" style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid rgba(255, 255, 255, 0.12); border-radius: 12px; margin-bottom: 16px; padding: 14px; box-shadow: 0 4px 14px rgba(0,0,0,0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px; margin-bottom: 10px;">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <span style="font-size: 1.05rem; font-weight: 800; color: #fbbf24;">📦 FİŞ #${orderId} (${escapeHtml(o.siparis_kodu || 'SİPARİŞ')})</span>
                                ${createdTimeStr ? `<span style="font-size: 0.8rem; background: rgba(255,255,255,0.08); color: #cbd5e1; padding: 2px 8px; border-radius: 6px;">⏰ Saat: ${escapeHtml(createdTimeStr)}</span>` : ''}
                            </div>
                            <div>
                                ${isPaid
                        ? `<span style="background: rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.4); padding:3px 8px; border-radius:6px; font-size:0.8rem; font-weight:700;">✅ ÖDENDİ</span>`
                        : `<span style="background: rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:3px 8px; border-radius:6px; font-size:0.8rem; font-weight:700;">⏳ NAKİT TAHSİLAT BEKLİYOR</span>`}
                            </div>
                        </div>

                        <table class="vega-ticket-table" style="width:100%; margin-bottom: 10px;">
                            <thead>
                                <tr>
                                    <th>Ürün Adı & Notu</th>
                                    <th style="text-align: center; width: 60px;">Adet</th>
                                    <th style="text-align: right; width: 100px;">Birim Fiyat</th>
                                    <th style="text-align: right; width: 120px;">İskonto/İkram</th>
                                    <th style="text-align: right; width: 100px;">Toplam</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${itemsRows}
                            </tbody>
                        </table>

                        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 8px; border-top: 1px solid rgba(255,255,255,0.05);">
                            <div>
                                <span style="font-size: 0.88rem; color: #cbd5e1;">Fiş Paketi Tutarı:</span>
                                <strong style="font-size: 1.15rem; color: #fff; margin-left: 6px;">${batchTotal.toFixed(2)} ₺</strong>
                            </div>
                            ${!isPaid ? `
                                <button type="button" class="btn-add" style="padding: 7px 16px; font-size: 0.85rem; font-weight: 800; background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 4px 12px rgba(16,185,129,0.35);" onclick="paySingleSiparisBatch(${orderId}, ${batchTotal})">
                                    💵 Bu Fiş Paketini Tahsil Et (${batchTotal.toFixed(2)} ₺)
                                </button>
                            ` : ''}
                        </div>
                    </div>
                `;
            });

            if (tbody) tbody.innerHTML = batchesHtml;
        }

        if (metaEl) {
            metaEl.innerHTML = `
                <span>Masa Sipariş Paketleri: <strong>${allMasaOrders.length} Fiş</strong></span> | 
                <span>Açık Paket: <strong>${openMasaOrders.length} Adet</strong></span>
            `;
        }
    }

    updateFinancialSummary(grandTotalSum, alreadyPaidSum);
}

function getActiveMasaSubtotal() {
    const table = kasaTables.find(t => t.id == activeMasaId);
    if (!table || table.durum === 'bos') return 0;

    const openMasaOrders = kasaOrders.filter(o =>
        o.masa_id == table.id &&
        o.odeme_durumu !== 'odendi' &&
        o.siparis_durumu !== 'iptal' &&
        o.siparis_durumu !== 'odendi_kapatildi'
    );

    if (openMasaOrders.length === 0) return 0;

    let itemsTotalSum = 0;
    currentTableItems.forEach(item => {
        if (!item.isIkram) {
            itemsTotalSum += parseFloat(item.ara_toplam) || 0;
        }
    });

    let orderTotalSum = 0;
    openMasaOrders.forEach(o => {
        orderTotalSum += parseFloat(o.toplam_tutar) || 0;
    });

    return itemsTotalSum > 0 ? itemsTotalSum : orderTotalSum;
}

function updateFinancialSummary(subtotal, alreadyPaidFromOrders = 0) {
    const table = kasaTables.find(t => t.id == activeMasaId);
    let subtotalVal = 0;
    if (table && table.durum !== 'bos') {
        subtotalVal = subtotal > 0 ? subtotal : getActiveMasaSubtotal();
    }

    let calculatedDiscount = 0;
    if (subtotalVal > 0 && discountValue > 0) {
        if (discountType === 'percent') {
            calculatedDiscount = (subtotalVal * discountValue) / 100;
        } else {
            calculatedDiscount = Math.min(subtotalVal, discountValue);
        }
    }

    const manualPartialPaid = (activeMasaId && subtotalVal > 0) ? (parseFloat(partialPaymentsMap[activeMasaId]) || 0) : 0;
    const paidBefore = alreadyPaidFromOrders + manualPartialPaid;

    const toplamVal = Math.max(0, subtotalVal);
    const kalanVal = Math.max(0, toplamVal - calculatedDiscount - paidBefore);

    let secimVal = 0;
    currentTableItems.forEach(i => {
        if (i.selected) {
            secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
        }
    });

    const elToplam = document.getElementById('valToplam');
    const elDiscount = document.getElementById('valDiscount');
    const rowDiscountDetail = document.getElementById('rowDiscountDetail');
    const elOdenen = document.getElementById('valOdenen');
    const elKalan = document.getElementById('valKalan');
    const elSecim = document.getElementById('valSecim');
    const rowSecimDetail = document.getElementById('rowSecimDetail');

    if (elToplam) elToplam.innerText = `${toplamVal.toFixed(2)} ₺`;
    if (rowDiscountDetail) {
        if (discountValue > 0 && subtotalVal > 0) {
            rowDiscountDetail.style.visibility = 'visible';
            if (elDiscount) elDiscount.innerText = `${calculatedDiscount.toFixed(2)} ₺ (${discountType === 'percent' ? '%' + discountValue : 'Sabit'})`;
        } else {
            rowDiscountDetail.style.visibility = 'hidden';
        }
    }
    if (elOdenen) elOdenen.innerText = `${paidBefore.toFixed(2)} ₺`;
    if (elKalan) elKalan.innerText = `${kalanVal.toFixed(2)} ₺`;

    const btnClearTable = document.getElementById('btnManualClearTable');
    if (btnClearTable) {
        if (!activeMasaId) {
            btnClearTable.style.display = 'none';
        } else {
            btnClearTable.style.display = 'flex';
        }
    }

    if (rowSecimDetail) {
        if (secimVal > 0 && subtotalVal > 0) {
            rowSecimDetail.style.visibility = 'visible';
            if (elSecim) elSecim.innerText = `${secimVal.toFixed(2)} ₺`;
        } else {
            rowSecimDetail.style.visibility = 'hidden';
        }
    }

    updateDualPaymentSum();
}

function showPaymentFeedback(amount, paymentMethod) {
    const banner = document.getElementById('paymentFeedbackBanner');
    const textEl = document.getElementById('feedbackText');
    if (banner && textEl) {
        textEl.innerText = `💵 ${amount.toFixed(2)} ₺ ${paymentMethod} ödemesi alındı!`;
        banner.style.display = 'flex';
    }
}

window.updateDualPaymentSum = function () {
    const subtotal = getActiveMasaSubtotal();
    const paidBefore = activeMasaId ? (parseFloat(partialPaymentsMap[activeMasaId]) || 0) : 0;

    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }
    const remainingTotal = Math.max(0, subtotal - calculatedDiscount - paidBefore);

    const nakit = parseFloat(document.getElementById('tutarNakitInput')?.value) || 0;
    const kart = parseFloat(document.getElementById('tutarKartInput')?.value) || 0;
    const currentInputPayment = nakit + kart;

    if (document.getElementById('dualSumLabel')) {
        let displaySum = currentInputPayment;
        if (displaySum === 0) {
            if (remainingTotal <= 0.05) {
                displaySum = 0;
            } else {
                let secimVal = 0;
                currentTableItems.forEach(i => {
                    if (i.selected) {
                        secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
                    }
                });
                displaySum = secimVal > 0 ? secimVal : remainingTotal;
            }
        }
        document.getElementById('dualSumLabel').innerText = `${displaySum.toFixed(2)} ₺`;
    }

    // Buton vurgularını güncelle
    let activeType = 'none';
    if (nakit > 0 && kart === 0) activeType = 'nakit';
    else if (kart > 0 && nakit === 0) activeType = 'pos';
    updateQuickButtonHighlights(activeType);
};

let isHalfModeSelected = false;

function updateQuickButtonHighlights(activeType) {
    const btnNakit = document.getElementById('btnChipNakit');
    const btnPos = document.getElementById('btnChipPos');
    const btnHalf = document.getElementById('btnChipHalf');

    if (btnNakit) {
        const isNakitActive = (activeType === 'nakit');
        btnNakit.style.background = isNakitActive ? '#10b981' : 'rgba(255, 255, 255, 0.08)';
        btnNakit.style.color = isNakitActive ? '#ffffff' : '#cbd5e1';
        btnNakit.style.borderColor = isNakitActive ? '#34d399' : 'rgba(255, 255, 255, 0.15)';
        btnNakit.style.boxShadow = isNakitActive ? '0 0 14px rgba(16, 185, 129, 0.6)' : 'none';
        btnNakit.style.transform = isNakitActive ? 'scale(1.04)' : 'scale(1)';
    }

    if (btnPos) {
        const isPosActive = (activeType === 'pos');
        btnPos.style.background = isPosActive ? '#06b6d4' : 'rgba(255, 255, 255, 0.08)';
        btnPos.style.color = isPosActive ? '#ffffff' : '#cbd5e1';
        btnPos.style.borderColor = isPosActive ? '#38bdf8' : 'rgba(255, 255, 255, 0.15)';
        btnPos.style.boxShadow = isPosActive ? '0 0 14px rgba(6, 182, 212, 0.6)' : 'none';
        btnPos.style.transform = isPosActive ? 'scale(1.04)' : 'scale(1)';
    }

    if (btnHalf) {
        const isHalfActive = isHalfModeSelected;
        btnHalf.style.background = isHalfActive ? '#6366f1' : 'rgba(99, 102, 241, 0.15)';
        btnHalf.style.color = isHalfActive ? '#ffffff' : '#818cf8';
        btnHalf.style.borderColor = isHalfActive ? '#818cf8' : 'rgba(99, 102, 241, 0.4)';
        btnHalf.style.boxShadow = isHalfActive ? '0 0 14px rgba(99, 102, 241, 0.6)' : 'none';
    }
}

window.fillDualAmount = function (type) {
    if (!activeMasaId) return;

    const subtotal = getActiveMasaSubtotal();
    const paidBefore = parseFloat(partialPaymentsMap[activeMasaId]) || 0;

    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }
    const remainingTotal = Math.max(0, subtotal - calculatedDiscount - paidBefore);

    if (remainingTotal <= 0.05 && type !== 'clear') {
        showKasaToast("⚠️ Masanın borcu zaten ödenmiştir.");
        return;
    }

    let secimVal = 0;
    currentTableItems.forEach(i => {
        if (i.selected) {
            secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
        }
    });

    const fullTarget = (secimVal > 0 && remainingTotal > 0.05) ? secimVal : remainingTotal;
    const halfTarget = fullTarget / 2;

    const nakitEl = document.getElementById('tutarNakitInput');
    const kartEl = document.getElementById('tutarKartInput');

    if (type === 'half') {
        isHalfModeSelected = true;
        const currentKart = parseFloat(kartEl?.value) || 0;
        if (currentKart > 0) {
            if (kartEl) kartEl.value = halfTarget > 0 ? halfTarget.toFixed(2) : '';
            if (nakitEl) nakitEl.value = '';
            updateQuickButtonHighlights('pos');
        } else {
            if (nakitEl) nakitEl.value = halfTarget > 0 ? halfTarget.toFixed(2) : '';
            if (kartEl) kartEl.value = '';
            updateQuickButtonHighlights('nakit');
        }
        showKasaToast(`⚖️ Yarısı (${halfTarget.toFixed(2)} ₺) hesaplandı.`);
    } else if (type === 'nakit' || type === 'nakit_all') {
        const amount = isHalfModeSelected ? halfTarget : fullTarget;
        if (nakitEl) nakitEl.value = amount > 0 ? amount.toFixed(2) : '';
        if (kartEl) kartEl.value = '';
        updateQuickButtonHighlights('nakit');
    } else if (type === 'pos' || type === 'pos_all') {
        const amount = isHalfModeSelected ? halfTarget : fullTarget;
        if (kartEl) kartEl.value = amount > 0 ? amount.toFixed(2) : '';
        if (nakitEl) nakitEl.value = '';
        updateQuickButtonHighlights('pos');
    } else if (type === 'clear') {
        isHalfModeSelected = false;
        if (nakitEl) nakitEl.value = '';
        if (kartEl) kartEl.value = '';
        updateQuickButtonHighlights('none');
    }

    updateDualPaymentSum();
};

window.toggleItemSelection = function (index) {
    if (currentTableItems[index]) {
        if (currentTableItems[index].isFullyPaid) return;
        currentTableItems[index].selected = !currentTableItems[index].selected;
        renderActiveTicketWorkstation();
    }
};

window.toggleSelectAllItems = function (isChecked) {
    currentTableItems.forEach(item => {
        if (!item.isFullyPaid) {
            item.selected = isChecked;
        }
    });
    renderActiveTicketWorkstation();
};

window.processQuickPayment = async function (paymentMethod) {
    if (!activeMasaId) {
        appAlert("Lütfen tahsilat yapmak için önce bir masa seçiniz.");
        return;
    }

    const table = kasaTables.find(t => t.id == activeMasaId);
    if (!table) return;

    const subtotal = getActiveMasaSubtotal();
    const paidBefore = activeMasaId ? (parseFloat(partialPaymentsMap[activeMasaId]) || 0) : 0;

    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }

    const remaining = Math.max(0, subtotal - calculatedDiscount - paidBefore);

    if (remaining <= 0 && subtotal === 0) {
        appAlert("Bu masada ödenecek adisyon tutarı bulunmuyor.");
        return;
    }

    let selectedItemsSum = 0;
    const selectedItems = currentTableItems.filter(i => i.selected);
    if (selectedItems.length > 0) {
        selectedItemsSum = selectedItems.reduce((sum, i) => sum + (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0), 0);
    }

    const payAmount = selectedItemsSum > 0 ? selectedItemsSum : remaining;

    let confirmMsg = `${getFormattedMasaNo(table.masa_no)} için `;
    if (selectedItemsSum > 0) {
        confirmMsg += `seçilen ürünlerin tutarı olan ${payAmount.toFixed(2)} ₺ (${paymentMethod}) olarak tahsil edilecek. Masa açık kalacaktır. Onaylıyor musunuz?`;
    } else {
        confirmMsg += `kalan borç tutarı olan ${payAmount.toFixed(2)} ₺ (${paymentMethod}) olarak tahsil edilecek. Onaylıyor musunuz?`;
    }

    const tahsilatOnayi = await appConfirm(confirmMsg, {
        title: '💵 Tahsilat Onayı',
        okText: 'Evet, tahsil et'
    });
    if (!tahsilatOnayi) return;

    // Yerel toplam ancak sunucu tahsilatı kaydettikten sonra artırılır; aksi halde
    // kasada alınmamış para alınmış gibi görünür.
    try {
        await apiPost(`/api/masalar/${activeMasaId}/tahsilat`, { tutar: payAmount, odeme_yontemi: paymentMethod });
    } catch (e) {
        console.error("Tahsilat kayıt hatası:", e);
        showKasaToast(`⚠️ Tahsilat kaydedilemedi: ${e.message}`);
        return;
    }

    if (!partialPaymentsMap[activeMasaId]) partialPaymentsMap[activeMasaId] = 0;
    partialPaymentsMap[activeMasaId] += payAmount;

    showPaymentFeedback(payAmount, paymentMethod);

    currentTableItems.forEach(i => i.selected = false);

    const updatedRemaining = Math.max(0, subtotal - calculatedDiscount - partialPaymentsMap[activeMasaId]);

    if (updatedRemaining <= 0.05) {
        try {
            await apiPost(`/api/masalar/${activeMasaId}/clear`);
            delete partialPaymentsMap[activeMasaId];
            discountValue = 0;
            const masaNo = getFormattedMasaNo(table.masa_no);
            showKasaToast(`✅ ${masaNo} hesabındaki borç tamamen kapandı ve masa temizlendi!`);
            closeMasaDetayView();
            await loadKasaData();
            return;
        } catch (e) {
            console.error("Masa temizleme hatası:", e);
            showKasaToast(`⚠️ Tahsilat alındı ancak masa kapatılamadı: ${e.message}`);
            renderActiveTicketWorkstation();
            return;
        }
    }

    showKasaToast(`💵 ${payAmount.toFixed(2)} ₺ (${paymentMethod}) parçalı/erken tahsilat alındı.`);
    renderActiveTicketWorkstation();
};

let pendingPaymentData = null;

window.processMainPaymentSubmit = function () {
    if (!activeMasaId) {
        showKasaToast("⚠️ Lütfen tahsilat yapmak için önce bir masa seçiniz.");
        return;
    }

    const table = kasaTables.find(t => t.id == activeMasaId);
    if (!table) return;

    const subtotal = getActiveMasaSubtotal();
    const paidBefore = parseFloat(partialPaymentsMap[activeMasaId]) || 0;

    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }
    const remaining = Math.max(0, subtotal - calculatedDiscount - paidBefore);

    if (remaining <= 0.05) {
        showKasaToast("⚠️ Bu masanın hesabı zaten tamamen ödenmiştir (Kalan: 0.00 ₺). Masayı kapatabilir veya F8 ile fiş yazdırabilirsiniz.");
        return;
    }

    let nakitPay = parseFloat(document.getElementById('tutarNakitInput')?.value) || 0;
    let kartPay = parseFloat(document.getElementById('tutarKartInput')?.value) || 0;

    if (nakitPay === 0 && kartPay === 0) {
        let secimVal = 0;
        currentTableItems.forEach(i => {
            if (i.selected) {
                secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
            }
        });
        const targetAmount = secimVal > 0 ? secimVal : remaining;

        if (targetAmount <= 0) {
            showKasaToast("⚠️ Adisyonda ödenecek tutar bulunmuyor.");
            return;
        }

        nakitPay = targetAmount;
        if (document.getElementById('tutarNakitInput')) {
            document.getElementById('tutarNakitInput').value = targetAmount.toFixed(2);
        }
    }

    const totalInputPayment = nakitPay + kartPay;
    if (totalInputPayment <= 0) {
        showKasaToast("⚠️ Geçersiz ödeme tutarı.");
        return;
    }

    pendingPaymentData = {
        table,
        nakitPay,
        kartPay,
        totalInputPayment,
        subtotal,
        calculatedDiscount
    };

    const confirmMasaInfo = document.getElementById('posConfirmMasaInfo');
    const confirmDetailsBox = document.getElementById('posConfirmDetailsBox');

    if (confirmMasaInfo) {
        confirmMasaInfo.innerText = `${getFormattedMasaNo(table.masa_no)} - ÖDEME ALINIYOR`;
    }

    if (confirmDetailsBox) {
        let html = ``;
        if (nakitPay > 0) {
            html += `<div style="display:flex; justify-content:space-between;"><span>💵 Nakit Ödeme:</span><strong style="color:#34d399; font-size:1.1rem;">${nakitPay.toFixed(2)} ₺</strong></div>`;
        }
        if (kartPay > 0) {
            html += `<div style="display:flex; justify-content:space-between;"><span>💳 Kredi Kartı / POS:</span><strong style="color:#38bdf8; font-size:1.1rem;">${kartPay.toFixed(2)} ₺</strong></div>`;
        }
        html += `<div style="display:flex; justify-content:space-between; border-top:1px dashed rgba(255,255,255,0.2); padding-top:8px; margin-top:4px; font-weight:900; font-size:1.15rem; color:#fbbf24;"><span>TOPLAM TAHSİLAT:</span><strong>${totalInputPayment.toFixed(2)} ₺</strong></div>`;
        confirmDetailsBox.innerHTML = html;
    }

    const modal = document.getElementById('posPaymentConfirmModal');
    if (modal) modal.classList.add('active');
};

window.executeConfirmedMainPayment = async function (shouldPrintAndClose = false) {
    if (!pendingPaymentData || !activeMasaId) return;

    const { table, nakitPay, kartPay, totalInputPayment, subtotal, calculatedDiscount } = pendingPaymentData;

    closeModal('posPaymentConfirmModal');

    const paymentLabel = nakitPay > 0 && kartPay > 0 ? "Nakit + POS" : (nakitPay > 0 ? "Nakit" : "Kredi Kartı");

    try {
        await apiPost(`/api/masalar/${activeMasaId}/tahsilat`, { tutar: totalInputPayment, odeme_yontemi: paymentLabel });
    } catch (e) {
        console.error("Tahsilat kayıt hatası:", e);
        showKasaToast(`⚠️ Tahsilat kaydedilemedi: ${e.message}`);
        pendingPaymentData = null;
        return;
    }

    if (!partialPaymentsMap[activeMasaId]) partialPaymentsMap[activeMasaId] = 0;
    partialPaymentsMap[activeMasaId] += totalInputPayment;

    if (document.getElementById('tutarNakitInput')) document.getElementById('tutarNakitInput').value = '';
    if (document.getElementById('tutarKartInput')) document.getElementById('tutarKartInput').value = '';
    currentTableItems.forEach(i => i.selected = false);

    showPaymentFeedback(totalInputPayment, paymentLabel);

    const updatedRemaining = Math.max(0, subtotal - calculatedDiscount - partialPaymentsMap[activeMasaId]);

    if (shouldPrintAndClose) {
        printReceiptPreview();
        try {
            await apiPost(`/api/masalar/${activeMasaId}/clear`);
            delete partialPaymentsMap[activeMasaId];
            discountValue = 0;
            const masaNo = getFormattedMasaNo(table.masa_no);
            showKasaToast(`✅ ${masaNo} ödemesi alındı, fiş yazdırıldı ve masa kapatıldı!`);
            pendingPaymentData = null;
            closeMasaDetayView();
            await loadKasaData();
            return;
        } catch (e) {
            console.error("Masa kapatma hatası:", e);
            showKasaToast(`⚠️ Ödeme alındı ancak masa kapatılamadı: ${e.message}`);
            pendingPaymentData = null;
            renderActiveTicketWorkstation();
            return;
        }
    } else {
        if (updatedRemaining <= 0.05) {
            showKasaToast(`💵 ${totalInputPayment.toFixed(2)} ₺ ödeme alındı! Borç sıfırlandı. (Masada kalındı - Fiş için F8)`);
        } else {
            showKasaToast(`💵 ${totalInputPayment.toFixed(2)} ₺ ödeme alındı. Kalan borç: ${updatedRemaining.toFixed(2)} ₺`);
        }
        pendingPaymentData = null;
        renderActiveTicketWorkstation();
    }
};

window.clearActiveTableManually = async function () {
    if (!activeMasaId) return;
    const table = kasaTables.find(t => t.id == activeMasaId);

    const masaNo = table ? getFormattedMasaNo(table.masa_no) : '';
    const onaylandi = await appConfirm(
        `${masaNo} masasını zorla kapatmak ve temizlemek üzeresiniz. Ödenmemiş siparişler varsa hepsi iptal edilecektir. Devam edilsin mi?`,
        { title: '🧹 Masayı Zorla Kapat', okText: 'Evet, masayı kapat' }
    );
    if (!onaylandi) return;

    try {
        await apiPost(`/api/masalar/${activeMasaId}/clear`);
        delete partialPaymentsMap[activeMasaId];
        discountValue = 0;
        showKasaToast(`🧹 ${masaNo} masası zorla kapatıldı ve temizlendi!`);
        closeMasaDetayView();
        await loadKasaData();
    } catch (e) {
        console.error("Masa temizleme hatası:", e);
        showKasaToast(`⚠️ ${masaNo} masası kapatılamadı: ${e.message}`);
    }
};

window.handleShortcut = function (key) {
    switch (key) {
        case 'F1':
            processQuickPayment('Nakit');
            break;
        case 'F2':
            processQuickPayment('Kredi Kartı');
            break;
        case 'F3':
            processQuickPayment('Yemek Kartı (Sodexo/Ticket)');
            break;
        case 'F4':
            document.getElementById('tutarNakitInput')?.focus();
            break;
        case 'F5':
            openDiscountModal();
            break;
        case 'F6':
            applyIkramToSelectedItems();
            break;
        case 'F7':
            toggleTableMoveMode();
            break;
        case 'F8':
            printReceiptPreview();
            break;
    }
};

window.openDiscountModal = function () {
    if (!activeMasaId) {
        appAlert("Lütfen iskonto uygulamak için bir masa seçiniz.");
        return;
    }
    document.getElementById('discountValueInput').value = discountValue ? parseFloat(discountValue).toFixed(2) : '';
    document.getElementById('discountModal').classList.add('active');
};

window.setDiscountType = function (type) {
    discountType = type;
    const btnP = document.getElementById('btnDiscPercent');
    const btnA = document.getElementById('btnDiscAmount');
    const label = document.getElementById('discInputLabel');
    const quickGroup = document.getElementById('quickPercentGroup');

    if (type === 'percent') {
        if (btnP) { btnP.style.background = 'var(--primary)'; btnP.style.color = '#000'; }
        if (btnA) { btnA.style.background = 'rgba(255,255,255,0.1)'; btnA.style.color = '#fff'; }
        if (label) label.innerText = 'İndirim Oranı (%)';
        if (quickGroup) {
            quickGroup.style.visibility = 'visible';
            quickGroup.style.pointerEvents = 'auto';
        }
    } else {
        if (btnA) { btnA.style.background = 'var(--primary)'; btnA.style.color = '#000'; }
        if (btnP) { btnP.style.background = 'rgba(255,255,255,0.1)'; btnP.style.color = '#fff'; }
        if (label) label.innerText = 'İndirim Tutarı (₺)';
        if (quickGroup) {
            quickGroup.style.visibility = 'hidden';
            quickGroup.style.pointerEvents = 'none';
        }
    }
};

window.applyQuickPercent = function (percent) {
    discountType = 'percent';
    discountValue = percent;
    document.getElementById('discountValueInput').value = percent;
    confirmDiscount();
};

window.confirmDiscount = function () {
    let val = parseFloat(document.getElementById('discountValueInput').value) || 0;
    val = parseFloat(val.toFixed(2)); // Sadece 2 basamak
    discountValue = val;
    closeModal('discountModal');
    renderActiveTicketWorkstation();
    showKasaToast(`🏷️ İskonto uygulandı: ${discountType === 'percent' ? '%' + val : val + ' ₺'}`);
};

window.clearDiscount = function () {
    discountValue = 0;
    closeModal('discountModal');
    renderActiveTicketWorkstation();
    showKasaToast(`İskonto kaldırıldı.`);
};

window.applyIkramToSelectedItems = function () {
    const selected = currentTableItems.filter(i => i.selected);
    if (selected.length === 0) {
        appAlert("Lütfen ikram etmek veya ikramı iptal etmek istediğiniz en az 1 ürünü tablodan seçiniz.");
        return;
    }

    const isFirstAlreadyIkram = selected[0].isIkram;
    selected.forEach(item => {
        item.isIkram = !isFirstAlreadyIkram;
    });

    renderActiveTicketWorkstation();
    showKasaToast(isFirstAlreadyIkram ? `🎁 Seçilen ${selected.length} kalemin ikramı iptal edildi.` : `🎁 Seçilen ${selected.length} kalem ikram olarak işaretlendi.`);
};

// MASA TAŞIMA MODALİ (F7)
window.openMoveTableModal = function () {
    if (!activeMasaId) {
        appAlert("Lütfen taşımak istediğiniz masayı seçiniz.");
        return;
    }
    const table = kasaTables.find(t => t.id === activeMasaId);
    document.getElementById('moveFromMasaName').innerText = table ? getFormattedMasaNo(table.masa_no) : '';

    const select = document.getElementById('targetMasaSelect');
    let html = '';
    kasaTables.filter(t => t.id !== activeMasaId).forEach(t => {
        html += `<option value="${t.id}">🪑 ${getFormattedMasaNo(t.masa_no)} (${t.durum === 'dolu' ? '🔴 Dolu - Birleştirilecek' : '🟢 Boş'})</option>`;
    });
    select.innerHTML = html;
    document.getElementById('moveTableModal').classList.add('active');
};

window.confirmMoveTable = async function () {
    const targetId = parseInt(document.getElementById('targetMasaSelect').value);
    if (!targetId) return;

    try {
        const res = await fetch('/api/masalar/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_masa_id: activeMasaId, to_masa_id: targetId })
        });
        if (res.ok) {
            closeModal('moveTableModal');
            const targetTable = kasaTables.find(t => t.id === targetId);
            activeMasaId = targetId;
            await loadKasaData();
            showKasaToast(`🔄 Masa hesabı başarıyla ${targetTable ? getFormattedMasaNo(targetTable.masa_no) : ''} hesabına aktarıldı.`);
        }
    } catch (e) {
        appAlert("Masa taşıma başarısız oldu.");
    }
};

// FİŞ / ADİSYON YAZDIRMA ÖNİZLEMESİ (F8)
window.printReceiptPreview = function () {
    if (!activeMasaId) {
        appAlert("Lütfen adisyon fişi yazdırmak için bir masa seçiniz.");
        return;
    }
    const table = kasaTables.find(t => t.id === activeMasaId);
    const area = document.getElementById('receiptPrintArea');

    const subtotal = currentTableItems.reduce((sum, item) => sum + (item.isIkram ? 0 : item.ara_toplam), 0);
    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }
    const grandTotal = Math.max(0, subtotal - calculatedDiscount);

    const nowStr = new Date().toLocaleString('tr-TR');

    let html = `
        <div style="text-align:center; font-weight:bold; font-size:1.1rem; margin-bottom:4px;">LEZZET DÜNYASI RESTORAN</div>
        <div style="text-align:center; font-size:0.75rem; margin-bottom:12px;">Lezzet Dünyası Kasa Adisyon Fişi</div>
        <div style="border-bottom:1px dashed #000; margin-bottom:8px;"></div>
        <div>Masa: <strong>${table ? getFormattedMasaNo(table.masa_no) : ''}</strong></div>
        <div>Tarih: ${nowStr}</div>
        <div style="border-bottom:1px dashed #000; margin:8px 0;"></div>
        <div style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom:4px;">
            <span>Ürün</span>
            <span>Tutar</span>
        </div>
    `;

    currentTableItems.forEach(item => {
        html += `
            <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                <span>${item.adet}x ${escapeHtml(item.urun_adi)}</span>
                <span>${item.isIkram ? 'IKRAM' : item.ara_toplam.toFixed(2) + ' TL'}</span>
            </div>
        `;
    });

    html += `
        <div style="border-bottom:1px dashed #000; margin:8px 0;"></div>
        <div style="display:flex; justify-content:space-between;">
            <span>Ara Toplam:</span>
            <span>${subtotal.toFixed(2)} TL</span>
        </div>
    `;

    if (calculatedDiscount > 0) {
        html += `
            <div style="display:flex; justify-content:space-between; color:#d97706;">
                <span>İskonto İndirimi:</span>
                <span>-${calculatedDiscount.toFixed(2)} TL</span>
            </div>
        `;
    }

    html += `
        <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.05rem; margin-top:6px; border-top:1px solid #000; padding-top:4px;">
            <span>GENEL TOPLAM:</span>
            <span>${grandTotal.toFixed(2)} TL</span>
        </div>
        <div style="border-bottom:1px dashed #000; margin:12px 0 8px 0;"></div>
        <div style="text-align:center; font-size:0.75rem;">Bizi Tercih Ettiğiniz İçin Teşekkür Ederiz!<br>Afiyet Olsun.</div>
    `;

    area.innerHTML = html;
    document.getElementById('printReceiptModal').classList.add('active');
};

window.closeModal = function (modalId) {
    document.getElementById(modalId).classList.remove('active');
};

// GÖRSEL MASA & ÜRÜN TAŞIMA MODU MANTIĞI
let isTableMoveMode = false;
let moveSourceTableId = null;
let moveTargetTableId = null;
let selectedTransferType = 'all';

window.toggleTableMoveMode = function () {
    if (isTableMoveMode) {
        cancelTableMoveMode();
    } else {
        isTableMoveMode = true;
        moveSourceTableId = null;
        moveTargetTableId = null;
        const banner = document.getElementById('moveModeBanner');
        const text = document.getElementById('moveModeBannerText');
        if (text) text.innerText = 'MASA TAŞIMA MODU: Lütfen taşınacak (Kaynak) masaya tıklayınız...';
        if (banner) banner.style.display = 'flex';
        renderKasaGrid();
        showKasaToast('🔄 Masa taşıma modu aktif. Taşınacak masayı seçiniz.');
    }
};

window.cancelTableMoveMode = function () {
    isTableMoveMode = false;
    moveSourceTableId = null;
    moveTargetTableId = null;
    const banner = document.getElementById('moveModeBanner');
    if (banner) banner.style.display = 'none';
    renderKasaGrid();
};

function handleTableClickInMoveMode(tableId) {
    const table = kasaTables.find(t => t.id == tableId);
    if (!table) return;

    if (!moveSourceTableId) {
        const masaOrders = kasaOrders.filter(o => o.masa_id == table.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
        if (table.durum === 'bos' && masaOrders.length === 0) {
            showKasaToast('⚠️ Bu masa boş, taşınacak adisyon bulunmuyor.');
            return;
        }
        moveSourceTableId = tableId;
        const text = document.getElementById('moveModeBannerText');
        if (text) text.innerText = `🔄 ${getFormattedMasaNo(table.masa_no)} SEÇİLDİ ➔ Lütfen aktarılacağı YENİ MASAYA (Hedef Masa) tıklayınız.`;
        renderKasaGrid();
        showKasaToast(`🔄 Kaynak Masa: ${getFormattedMasaNo(table.masa_no)} seçildi. Şimdi hedef masayı seçiniz.`);
    } else {
        if (tableId == moveSourceTableId) {
            showKasaToast('⚠️ Hedef masa kaynak masayla aynı olamaz.');
            return;
        }
        moveTargetTableId = tableId;
        openVisualTransferModal();
    }
}

function openVisualTransferModal() {
    const sourceTable = kasaTables.find(t => t.id == moveSourceTableId);
    const targetTable = kasaTables.find(t => t.id == moveTargetTableId);
    if (!sourceTable || !targetTable) return;

    const routeTitle = document.getElementById('transferRouteTitle');
    if (routeTitle) {
        routeTitle.innerText = `${getFormattedMasaNo(sourceTable.masa_no)} ➔ ${getFormattedMasaNo(targetTable.masa_no)}`;
    }

    setTransferType('all');
    document.getElementById('visualTransferModal').classList.add('active');
}

window.setTransferType = function (type) {
    selectedTransferType = type;
    const btnAll = document.getElementById('btnTransferTypeAll');
    const btnItems = document.getElementById('btnTransferTypeItems');
    const itemsContainer = document.getElementById('transferItemsContainer');

    if (type === 'all') {
        if (btnAll) { btnAll.style.background = '#6366f1'; btnAll.style.color = '#fff'; }
        if (btnItems) { btnItems.style.background = 'rgba(255,255,255,0.1)'; btnItems.style.color = '#cbd5e1'; }
        if (itemsContainer) {
            itemsContainer.innerHTML = '<div style="font-size:0.9rem; color:#cbd5e1; text-align:center; padding-top:45px;">📦 Masadaki tüm adisyon kalemleri eksiksiz aktarılacaktır.</div>';
        }
    } else {
        if (btnItems) { btnItems.style.background = '#6366f1'; btnItems.style.color = '#fff'; }
        if (btnAll) { btnAll.style.background = 'rgba(255,255,255,0.1)'; btnAll.style.color = '#cbd5e1'; }
        if (itemsContainer) {
            renderTransferItemsList();
        }
    }
};

function renderTransferItemsList() {
    const itemsContainer = document.getElementById('transferItemsContainer');
    if (!itemsContainer || !moveSourceTableId) return;

    const masaOrders = kasaOrders.filter(o => o.masa_id == moveSourceTableId && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
    let items = [];
    masaOrders.forEach(o => {
        (o.detaylar || []).forEach(d => items.push({ ...d, order_id: o.id }));
    });

    if (items.length === 0) {
        itemsContainer.innerHTML = '<div style="font-size:0.88rem; color:#94a3b8; text-align:center; padding-top:45px;">Aktarılacak ürün bulunamadı.</div>';
        return;
    }

    let html = '';
    items.forEach((item, idx) => {
        html += `
            <label style="display:flex; justify-content:space-between; align-items:center; padding:6px 4px; border-bottom:1px solid rgba(255,255,255,0.08); cursor:pointer;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <input type="checkbox" class="transfer-item-checkbox" value="${item.id || idx}" checked style="accent-color:#6366f1; width:16px; height:16px;">
                    <span style="font-weight:700; font-size:0.9rem; color:#fff;">${item.adet}x ${escapeHtml(item.urun_adi)}</span>
                </div>
                <span style="font-weight:800; color:#fbbf24; font-size:0.9rem;">${(item.ara_toplam || (item.birim_fiyat * item.adet)).toFixed(2)} ₺</span>
            </label>
        `;
    });
    itemsContainer.innerHTML = html;
}

window.confirmVisualTableTransfer = async function () {
    if (!moveSourceTableId || !moveTargetTableId) return;

    const sourceTable = kasaTables.find(t => t.id == moveSourceTableId);
    const targetTable = kasaTables.find(t => t.id == moveTargetTableId);

    try {
        const res = await fetch('/api/masalar/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_masa_id: moveSourceTableId, to_masa_id: moveTargetTableId })
        });

        closeModal('visualTransferModal');
        cancelTableMoveMode();

        if (res.ok) {
            const sourceNo = sourceTable ? getFormattedMasaNo(sourceTable.masa_no) : '';
            const targetNo = targetTable ? getFormattedMasaNo(targetTable.masa_no) : '';
            showKasaToast(`🔄 ${sourceNo} hesabı başarıyla ${targetNo} hesabına aktarıldı!`);
            await loadKasaData();
        } else {
            showKasaToast('⚠️ Masa taşıma işlemi başarısız oldu.');
        }
    } catch (e) {
        closeModal('visualTransferModal');
        cancelTableMoveMode();
        showKasaToast('⚠️ Masa taşıma işlemi başarısız oldu.');
    }
};

let activeQRInterval = null;

window.showDynamicQRModal = async function (masaId) {
    if (activeQRInterval) clearInterval(activeQRInterval);

    let existingModal = document.getElementById("kasaQRModal");
    if (existingModal) existingModal.remove();

    const fetchAndUpdateModal = async () => {
        try {
            const res = await fetch(`/api/masalar/${masaId}/dynamic-qr`);
            const data = await res.json();
            const qrImg = document.getElementById("modalQRImage");
            const tokenEl = document.getElementById("modalQRToken");
            const timerEl = document.getElementById("qrRemainingTimer");
            const linkEl = document.getElementById("modalQRLink");

            let baseOrigin = window.location.origin;
            if (baseOrigin.includes("localhost") || baseOrigin.includes("127.0.0.1")) {
                baseOrigin = "http://192.168.1.100:8000";
            }
            const qrTargetUrl = baseOrigin + data.qr_url;
            const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(qrTargetUrl)}`;

            if (qrImg) qrImg.src = qrApiUrl;
            if (tokenEl) tokenEl.innerText = data.token;
            if (timerEl) timerEl.innerText = data.remaining_seconds;
            if (linkEl) linkEl.href = data.qr_url;
            return data;
        } catch (e) {
            console.error("QR modal update error:", e);
        }
    };

    try {
        const res = await fetch(`/api/masalar/${masaId}/dynamic-qr`);
        const data = await res.json();

        let baseOrigin = window.location.origin;
        if (baseOrigin.includes("localhost") || baseOrigin.includes("127.0.0.1")) {
            baseOrigin = "http://192.168.1.100:8000";
        }
        const qrTargetUrl = baseOrigin + data.qr_url;
        const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(qrTargetUrl)}`;

        const modalHtml = `
            <div id="kasaQRModal" class="modal-overlay active" style="z-index: 99999; display:flex; align-items:center; justify-content:center;">
                <div class="modal-content" style="max-width: 380px; text-align: center; background:#181824; color:#fff; padding:28px; border-radius:20px; position:relative; box-shadow:0 20px 60px rgba(0,0,0,0.6); border:1px solid rgba(255,188,0,0.25);">
                    <button style="position:absolute; top:12px; right:16px; background:none; border:none; color:#aaa; font-size:26px; cursor:pointer;" onclick="clearInterval(activeQRInterval); document.getElementById('kasaQRModal').remove()">&times;</button>
                    
                    <h3 style="color:#ffbc00; margin:0 0 6px 0; font-size:1.3rem;">📱 Canlı Dinamik QR (Masa #${data.masa_no || masaId})</h3>
                    <p style="font-size:0.82rem; color:#aaa; margin:0 0 18px 0;">Telefon kamerası ile okutarak doğrudan masa oturumuna girebilirsiniz:</p>
                    
                    <div style="background:#ffffff; padding:18px; border-radius:16px; display:inline-block; margin-bottom:18px; box-shadow:0 8px 25px rgba(0,0,0,0.3);">
                        <img id="modalQRImage" src="${qrApiUrl}" width="200" height="200" alt="Canlı QR Kodu" style="display:block; border-radius:8px;">
                    </div>
                    
                    <div style="background:rgba(255,255,255,0.05); padding:10px; border-radius:12px; margin-bottom:12px; display:flex; flex-direction:column; align-items:center; gap:4px;">
                        <div style="font-size:0.75rem; color:#aaa; font-weight:bold;">🔑 CANLI MASA GÜVENLİK KODU</div>
                        <div style="display:flex; align-items:center; justify-content:center; gap:10px;">
                            <div style="font-weight:900; font-size:1.4rem; color:#10b981; font-family:monospace; letter-spacing:3px;" id="modalQRToken">${data.token}</div>
                            <button type="button" onclick="copyDynamicQRToken(event)" title="Kopyala" style="background:rgba(16, 185, 129, 0.2); border:1px solid #10b981; color:#10b981; border-radius:8px; padding:4px 8px; font-size:0.95rem; cursor:pointer; touch-action:manipulation; user-select:none;">📋</button>
                        </div>
                    </div>

                    <div style="font-size:0.85rem; color:#fbbf24; font-weight:bold;">
                        ⏳ QR Yenilenme Süresi: <span id="qrRemainingTimer">${data.remaining_seconds}</span> saniye
                    </div>
                    
                    <div style="margin-top:14px; display:flex; align-items:center; justify-content:center; gap:8px;">
                        <a id="modalQRLink" href="${data.qr_url}" target="_blank" style="color:#818cf8; font-size:0.85rem; font-weight:700; text-decoration:underline;">🔗 Masa Menü Linkine Doğrudan Git</a>
                        <button type="button" onclick="copyDynamicQRLink(event)" title="Kopyala" style="background:rgba(99, 102, 241, 0.2); border:1px solid #6366f1; color:#818cf8; border-radius:8px; padding:4px 8px; font-size:0.85rem; cursor:pointer; touch-action:manipulation; user-select:none;">📋</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML("beforeend", modalHtml);

        activeQRInterval = setInterval(async () => {
            const timerEl = document.getElementById("qrRemainingTimer");
            if (!timerEl) {
                clearInterval(activeQRInterval);
                return;
            }
            let current = intVal(timerEl.innerText);
            if (current <= 1) {
                await fetchAndUpdateModal();
            } else {
                timerEl.innerText = current - 1;
            }
        }, 1000);

    } catch (e) {
        appAlert("Dinamik QR verisi çekilemedi.");
    }
};

function intVal(val) {
    const parsed = parseInt(val, 10);
    return isNaN(parsed) ? 30 : parsed;
}

window.copyDynamicQRToken = function (event) {
    if (event) event.stopPropagation();
    const tokenEl = document.getElementById("modalQRToken");
    if (!tokenEl) return;
    const text = tokenEl.innerText.trim();
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showKasaToast("📋 Güvenlik kodu kopyalandı!");
        }).catch(() => fallbackCopyText(text, "📋 Güvenlik kodu kopyalandı!"));
    } else {
        fallbackCopyText(text, "📋 Güvenlik kodu kopyalandı!");
    }
};

window.copyDynamicQRLink = function (event) {
    if (event) event.stopPropagation();
    const linkEl = document.getElementById("modalQRLink");
    if (!linkEl) return;
    const url = linkEl.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
            showKasaToast("📋 Masa QR linki kopyalandı!");
        }).catch(() => fallbackCopyText(url, "📋 Masa QR linki kopyalandı!"));
    } else {
        fallbackCopyText(url, "📋 Masa QR linki kopyalandı!");
    }
};

function fallbackCopyText(text, msg) {
    const input = document.createElement("input");
    input.value = text;
    document.body.appendChild(input);
    input.select();
    try {
        document.execCommand("copy");
        showKasaToast(msg);
    } catch (e) { }
    document.body.removeChild(input);
}

window.showKasaToast = function (msg) {
    let container = document.getElementById('kasaToastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'kasaToastContainer';
        container.style.cssText = 'position:fixed; bottom:30px; left:50%; transform:translateX(-50%); z-index:999999; display:flex; flex-direction:column; gap:8px; pointer-events:none;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.style.cssText = 'background:rgba(15, 23, 42, 0.96); border:1px solid rgba(16, 185, 129, 0.6); color:#6ee7b7; padding:8px 18px; border-radius:100px; font-weight:800; font-size:0.85rem; box-shadow:0 8px 24px rgba(0,0,0,0.6); white-space:nowrap; text-align:center; transition:opacity 0.2s ease;';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    }, 2200);
};

