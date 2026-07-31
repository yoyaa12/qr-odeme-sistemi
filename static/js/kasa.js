let kasaTables = [];
let kasaOrders = [];
let activeMasaId = null;
let activeFilter = 'all';
let currentTableItems = [];

// VEGA İSKONTO VE ÖDEME DURUMLARI
let discountType = 'percent'; // 'percent' or 'amount'
let discountValue = 0;
let partialPaymentsMap = {};

document.addEventListener('DOMContentLoaded', () => {
    loadKasaData();

    // SOCKET.IO CANLI DİNLEME
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

    // F1 - F8 KLAVYE KISAYOLLARI DİNLEYİCİSİ
    document.addEventListener('keydown', (e) => {
        if (['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8'].includes(e.key)) {
            e.preventDefault();
            handleShortcut(e.key);
        }
    });
});

function updateKasaSocketBadge(isConnected) {
    const badge = document.getElementById('socketStatusBadge');
    if (badge) {
        badge.innerHTML = isConnected ? `🟢 Canlı Bağlantı` : `🔴 Bağlantı Kesildi`;
        badge.className = isConnected ? `socket-badge connected` : `socket-badge disconnected`;
    }
}

async function loadKasaData() {
    try {
        const [tablesRes, ordersRes] = await Promise.all([
            fetch('/api/masalar'),
            fetch('/api/siparisler')
        ]);
        kasaTables = await tablesRes.json();
        kasaOrders = await ordersRes.json();

        updateFilterCounts();
        renderKasaGrid();

        // Eğer bir masa seçiliyse iş istasyonunu güncelle
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
    const salonContainer = document.getElementById('kasaGridSalon');
    const bahceContainer = document.getElementById('kasaGridBahce');
    if (!salonContainer || !bahceContainer) return;

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
        const formattedMasaNo = getFormattedMasaNo(t.masa_no);
        const isSalon = t.masa_no.startsWith('S-');

        const cardHtml = `
            <div class="vega-table-card ${statusClass} ${isSelected ? 'selected-table' : ''}" onclick="selectKasaMasa(${t.id})">
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

    salonContainer.innerHTML = salonHtml || `<div style="color:var(--text-muted); padding:20px; grid-column:1/-1; text-align:center;">Masa bulunamadı.</div>`;
    bahceContainer.innerHTML = bahceHtml || `<div style="color:var(--text-muted); padding:20px; grid-column:1/-1; text-align:center;">Masa bulunamadı.</div>`;
}

window.selectKasaMasa = function (masaId) {
    activeMasaId = masaId;
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
        currentTableItems[index].selected = !currentTableItems[index].selected;
        renderActiveTicketWorkstation();
    }
};

function renderActiveTicketWorkstation() {
    const table = kasaTables.find(t => t.id == activeMasaId);
    const titleEl = document.getElementById('ticketMasaTitle');
    const badgeEl = document.getElementById('ticketMasaStatusBadge');
    const metaEl = document.getElementById('ticketMetaInfo');
    const tbody = document.getElementById('ticketItemsBody');

    if (!table) {
        if (titleEl) titleEl.innerText = "🪑 MASA SEÇİLMEDİ";
        if (badgeEl) { badgeEl.innerText = "Masa Seçiniz"; badgeEl.className = "vega-badge-status"; }
        if (metaEl) metaEl.innerText = "";
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="vega-empty-ticket"><div style="font-size:2.5rem; margin-bottom:8px;">🛒</div><div>Lütfen masalar ekranından bir masaya tıklayınız.</div></td></tr>`;
        updateFinancialSummary(0);
        return;
    }

    const masaOrders = kasaOrders.filter(o => o.masa_id == table.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
    const isHesap = table.durum === 'hesap_istendi';
    const isDolu = table.durum === 'dolu' || masaOrders.length > 0;

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
    let subtotal = 0;

    masaOrders.forEach(o => {
        (o.detaylar || []).forEach((d, idx) => {
            const lineTotal = parseFloat(d.ara_toplam) || ((parseFloat(d.adet) || 0) * (parseFloat(d.birim_fiyat) || 0));
            const uniqueId = `${o.id}_${idx}`;
            const isIkramNow = (uniqueId in ikramStateMap) ? ikramStateMap[uniqueId] : (d.is_ikram || false);
            
            if (!isIkramNow) {
                subtotal += lineTotal;
            }

            currentTableItems.push({
                uniqueId: uniqueId,
                siparis_id: o.id,
                urun_adi: d.urun_adi,
                adet: parseInt(d.adet) || 1,
                birim_fiyat: parseFloat(d.birim_fiyat) || 0,
                ara_toplam: lineTotal,
                urun_notu: d.urun_notu || '',
                isIkram: isIkramNow,
                selected: !!selectedStateMap[uniqueId]
            });
        });
    });

    if (metaEl) {
        metaEl.innerHTML = `
            <span>Kalem Sayısı: <strong>${currentTableItems.length} Ürün</strong></span> | 
            <span>Sipariş Sayısı: <strong>${masaOrders.length} Adisyon</strong></span>
        `;
    }

    if (currentTableItems.length === 0) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="vega-empty-ticket"><div style="font-size:2rem; margin-bottom:6px;">🍽️</div><div>Bu masaya ait açık sipariş bulunmuyor.</div></td></tr>`;
    } else {
        let html = '';
        currentTableItems.forEach((item, index) => {
            html += `
                <tr class="ticket-row-clickable ${item.selected ? 'selected-row' : ''} ${item.isIkram ? 'ikram-row' : ''}" onclick="toggleRowSelection(${index})">
                    <td>
                        <strong style="color:#fff;">${item.urun_adi}</strong>
                        ${item.urun_notu ? `<div style="font-size:0.75rem; color:var(--text-secondary);">${item.urun_notu}</div>` : ''}
                    </td>
                    <td style="text-align: center; font-weight:800; color:#fff;">${item.adet}</td>
                    <td style="text-align: right; color:#94a3b8;">${item.birim_fiyat.toFixed(2)} ₺</td>
                    <td style="text-align: right; font-weight:700;">
                        ${item.isIkram ? `<span style="color:#ef4444; background:rgba(239,68,68,0.15); padding:2px 6px; border-radius:4px;">🎁 İKRAM (0 ₺)</span>` : '-'}
                    </td>
                    <td style="text-align: right; font-weight:800; color:#fbbf24;">${item.isIkram ? '0.00 ₺' : item.ara_toplam.toFixed(2) + ' ₺'}</td>
                </tr>
            `;
        });
        if (tbody) tbody.innerHTML = html;
    }

    updateFinancialSummary(subtotal);
}

function getActiveMasaSubtotal() {
    const table = kasaTables.find(t => t.id == activeMasaId);
    if (!table) return 0;
    const masaOrders = kasaOrders.filter(o => o.masa_id == table.id && o.odeme_durumu !== 'odendi' && o.siparis_durumu !== 'iptal');
    
    let itemsTotalSum = 0;
    currentTableItems.forEach(item => {
        if (!item.isIkram) {
            itemsTotalSum += parseFloat(item.ara_toplam) || 0;
        }
    });

    let orderTotalSum = 0;
    masaOrders.forEach(o => {
        orderTotalSum += parseFloat(o.toplam_tutar) || 0;
    });

    return itemsTotalSum > 0 ? itemsTotalSum : orderTotalSum;
}

function updateFinancialSummary(subtotal) {
    const subtotalVal = subtotal > 0 ? subtotal : getActiveMasaSubtotal();
    
    let calculatedDiscount = 0;
    if (discountValue > 0) {
        if (discountType === 'percent') {
            calculatedDiscount = (subtotalVal * discountValue) / 100;
        } else {
            calculatedDiscount = Math.min(subtotalVal, discountValue);
        }
    }

    const paidBefore = activeMasaId ? (parseFloat(partialPaymentsMap[activeMasaId]) || 0) : 0;
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
        if (discountValue > 0) {
            rowDiscountDetail.style.display = 'flex';
            if (elDiscount) elDiscount.innerText = `${calculatedDiscount.toFixed(2)} ₺ (${discountType === 'percent' ? '%' + discountValue : 'Sabit'})`;
        } else {
            rowDiscountDetail.style.display = 'none';
        }
    }
    if (elOdenen) elOdenen.innerText = `${paidBefore.toFixed(2)} ₺`;
    if (elKalan) elKalan.innerText = `${kalanVal.toFixed(2)} ₺`;
    
    if (rowSecimDetail) {
        if (secimVal > 0) {
            rowSecimDetail.style.display = 'flex';
            if (elSecim) elSecim.innerText = `${secimVal.toFixed(2)} ₺`;
        } else {
            rowSecimDetail.style.display = 'none';
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
    const toplam = Math.max(0, subtotal - calculatedDiscount);

    const nakit = parseFloat(document.getElementById('tutarNakitInput')?.value) || 0;
    const kart = parseFloat(document.getElementById('tutarKartInput')?.value) || 0;
    const currentInputPayment = nakit + kart;

    if (document.getElementById('dualSumLabel')) {
        let displaySum = currentInputPayment;
        if (displaySum === 0) {
            let secimVal = 0;
            currentTableItems.forEach(i => {
                if (i.selected) {
                    secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
                }
            });
            displaySum = secimVal > 0 ? secimVal : Math.max(0, toplam - paidBefore);
        }
        document.getElementById('dualSumLabel').innerText = `${displaySum.toFixed(2)} ₺`;
    }
};

window.fillDualAmount = function (type) {
    if (!activeMasaId) return;

    const subtotal = getActiveMasaSubtotal();
    const paidBefore = parseFloat(partialPaymentsMap[activeMasaId]) || 0;

    let calculatedDiscount = 0;
    if (discountValue > 0) {
        calculatedDiscount = discountType === 'percent' ? (subtotal * discountValue) / 100 : Math.min(subtotal, discountValue);
    }
    const remainingTotal = Math.max(0, subtotal - calculatedDiscount - paidBefore);

    let secimVal = 0;
    currentTableItems.forEach(i => {
        if (i.selected) {
            secimVal += (i.isIkram ? 0 : parseFloat(i.ara_toplam) || 0);
        }
    });

    const targetAmount = secimVal > 0 ? secimVal : remainingTotal;

    const nakitEl = document.getElementById('tutarNakitInput');
    const kartEl = document.getElementById('tutarKartInput');

    if (type === 'nakit_all') {
        if (nakitEl) nakitEl.value = targetAmount > 0 ? targetAmount.toFixed(2) : '';
        if (kartEl) kartEl.value = '';
    } else if (type === 'pos_all') {
        if (kartEl) kartEl.value = targetAmount > 0 ? targetAmount.toFixed(2) : '';
        if (nakitEl) nakitEl.value = '';
    } else if (type === 'split_half') {
        const half = targetAmount / 2;
        if (nakitEl) nakitEl.value = half > 0 ? half.toFixed(2) : '';
        if (kartEl) kartEl.value = half > 0 ? half.toFixed(2) : '';
    } else if (type === 'clear') {
        if (nakitEl) nakitEl.value = '';
        if (kartEl) kartEl.value = '';
    }

    updateDualPaymentSum();
};

window.toggleItemSelection = function (index) {
    if (currentTableItems[index]) {
        currentTableItems[index].selected = !currentTableItems[index].selected;
        renderActiveTicketWorkstation();
    }
};

window.toggleSelectAllItems = function (isChecked) {
    currentTableItems.forEach(item => item.selected = isChecked);
    renderActiveTicketWorkstation();
};

window.processQuickPayment = async function (paymentMethod) {
    if (!activeMasaId) {
        alert("Lütfen tahsilat yapmak için önce bir masa seçiniz.");
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
        alert("Bu masada ödenecek adisyon tutarı bulunmuyor.");
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

    if (!confirm(confirmMsg)) return;

    if (!partialPaymentsMap[activeMasaId]) partialPaymentsMap[activeMasaId] = 0;
    partialPaymentsMap[activeMasaId] += payAmount;

    showPaymentFeedback(payAmount, paymentMethod);

    currentTableItems.forEach(i => i.selected = false);

    const updatedRemaining = Math.max(0, subtotal - calculatedDiscount - partialPaymentsMap[activeMasaId]);

    if (updatedRemaining <= 0.05) {
        try {
            await fetch(`/api/masalar/${activeMasaId}/clear`, { method: 'POST' });
            delete partialPaymentsMap[activeMasaId];
            discountValue = 0;
            const masaNo = getFormattedMasaNo(table.masa_no);
            showKasaToast(`✅ ${masaNo} hesabındaki borç tamamen kapandı ve masa temizlendi!`);
            closeMasaDetayView();
            await loadKasaData();
            return;
        } catch (e) {
            console.error("Masa temizleme hatası:", e);
        }
    }

    showKasaToast(`💵 ${payAmount.toFixed(2)} ₺ (${paymentMethod}) parçalı/erken tahsilat alındı.`);
    renderActiveTicketWorkstation();
};

window.processMainPaymentSubmit = async function () {
    if (!activeMasaId) {
        alert("Lütfen tahsilat yapmak için önce bir masa seçiniz.");
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
            alert("Adisyonda ödenecek tutar bulunmuyor.");
            return;
        }

        const isNakit = confirm(`Ödemeyi NAKİT olarak almak için 'Tamam', KREDİ KARTI / POS olarak almak için 'İptal' butonuna basınız.\nTutar: ${targetAmount.toFixed(2)} ₺`);
        if (isNakit) {
            nakitPay = targetAmount;
        } else {
            kartPay = targetAmount;
        }
    }

    const totalInputPayment = nakitPay + kartPay;
    if (totalInputPayment <= 0) {
        alert("Geçersiz ödeme tutarı.");
        return;
    }

    let confirmMsg = `${getFormattedMasaNo(table.masa_no)} için `;
    if (nakitPay > 0 && kartPay > 0) {
        confirmMsg += `${nakitPay.toFixed(2)} ₺ Nakit ve ${kartPay.toFixed(2)} ₺ Kredi Kartı ödemesi tahsil edilecek. Onaylıyor musunuz?`;
    } else if (nakitPay > 0) {
        confirmMsg += `${nakitPay.toFixed(2)} ₺ Nakit ödemesi tahsil edilecek. Onaylıyor musunuz?`;
    } else {
        confirmMsg += `${kartPay.toFixed(2)} ₺ Kredi Kartı ödemesi tahsil edilecek. Onaylıyor musunuz?`;
    }

    if (!confirm(confirmMsg)) return;

    if (!partialPaymentsMap[activeMasaId]) partialPaymentsMap[activeMasaId] = 0;
    partialPaymentsMap[activeMasaId] += totalInputPayment;

    document.getElementById('tutarNakitInput').value = '';
    document.getElementById('tutarKartInput').value = '';
    currentTableItems.forEach(i => i.selected = false);

    const paymentLabel = nakitPay > 0 && kartPay > 0 ? "Nakit + POS" : (nakitPay > 0 ? "Nakit" : "Kredi Kartı");
    showPaymentFeedback(totalInputPayment, paymentLabel);

    const updatedRemaining = Math.max(0, subtotal - calculatedDiscount - partialPaymentsMap[activeMasaId]);

    if (updatedRemaining <= 0.05) {
        try {
            await fetch(`/api/masalar/${activeMasaId}/clear`, { method: 'POST' });
            delete partialPaymentsMap[activeMasaId];
            discountValue = 0;
            const masaNo = getFormattedMasaNo(table.masa_no);
            showKasaToast(`✅ ${masaNo} hesabı tamamen kapatıldı!`);
            closeMasaDetayView();
            await loadKasaData();
            return;
        } catch (e) {
            console.error("Masa kapatılamadı:", e);
        }
    }

    showKasaToast(`💵 ${totalInputPayment.toFixed(2)} ₺ ödeme alındı. Kalan: ${updatedRemaining.toFixed(2)} ₺`);
    renderActiveTicketWorkstation();
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
            openMoveTableModal();
            break;
        case 'F8':
            printReceiptPreview();
            break;
    }
};

window.openDiscountModal = function () {
    if (!activeMasaId) {
        alert("Lütfen iskonto uygulamak için bir masa seçiniz.");
        return;
    }
    document.getElementById('discountValueInput').value = discountValue || '';
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
        if (quickGroup) quickGroup.style.display = 'flex';
    } else {
        if (btnA) { btnA.style.background = 'var(--primary)'; btnA.style.color = '#000'; }
        if (btnP) { btnP.style.background = 'rgba(255,255,255,0.1)'; btnP.style.color = '#fff'; }
        if (label) label.innerText = 'İndirim Tutarı (₺)';
        if (quickGroup) quickGroup.style.display = 'none';
    }
};

window.applyQuickPercent = function (percent) {
    discountType = 'percent';
    discountValue = percent;
    document.getElementById('discountValueInput').value = percent;
    confirmDiscount();
};

window.confirmDiscount = function () {
    const val = parseFloat(document.getElementById('discountValueInput').value) || 0;
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
        alert("Lütfen ikram etmek veya ikramı iptal etmek istediğiniz en az 1 ürünü tablodan seçiniz.");
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
        alert("Lütfen taşımak istediğiniz masayı seçiniz.");
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
        alert("Masa taşıma başarısız oldu.");
    }
};

// FİŞ / ADİSYON YAZDIRMA ÖNİZLEMESİ (F8)
window.printReceiptPreview = function () {
    if (!activeMasaId) {
        alert("Lütfen adisyon fişi yazdırmak için bir masa seçiniz.");
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
                <span>${item.adet}x ${item.urun_adi}</span>
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

function showKasaToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification-waiter';
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
