let kasaTables = [];
let kasaOrders = [];
let activeKasaMasaId = null;
let currentTableItems = [];

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
        kasaTables = await tablesRes.json();
        kasaOrders = await ordersRes.json();

        renderKasaGrid();
    } catch(e) {
        console.error("Kasa verileri yüklenemedi:", e);
    }
}

function renderKasaGrid() {
    const container = document.getElementById('kasaGrid');
    if (!container) return;

    let html = '';
    kasaTables.forEach(t => {
        // ÖNEMLİ: Garson teslim etmiş olsa bile ('teslim_edildi'), ödemesi henüz kasada alınmadıysa ('odeme_durumu != odendi') adisyon Kasada AÇIK kalır!
        const masaOrders = kasaOrders.filter(o => o.masa_id === t.id && o.odeme_durumu !== 'odendi' && ['odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir', 'teslim_edildi'].includes(o.siparis_durumu));
        const pendingApprovalOrders = kasaOrders.filter(o => o.masa_id === t.id && o.siparis_durumu === 'garson_onayi_bekliyor');
        
        const totalBill = masaOrders.reduce((sum, o) => sum + o.toplam_tutar, 0);
        const isDolu = t.durum === 'dolu' || masaOrders.length > 0;
        const isPaidOnline = masaOrders.length > 0 && masaOrders.every(o => o.odeme_durumu === 'odendi');

        // Ürün bazlı toplama
        const itemsList = [];
        masaOrders.forEach(o => {
            (o.detaylar || []).forEach(d => {
                itemsList.push({
                    siparis_id: o.id,
                    urun_adi: d.urun_adi,
                    adet: d.adet,
                    birim_fiyat: d.birim_fiyat,
                    ara_toplam: d.ara_toplam || (d.adet * d.birim_fiyat),
                    urun_notu: d.urun_notu || '',
                    odeme_durumu: o.odeme_durumu
                });
            });
        });

        html += `
            <div class="order-card" style="border-color: ${isDolu ? (isPaidOnline ? '#10b981' : '#f59e0b') : 'rgba(255,255,255,0.1)'};">
                <div class="order-header">
                    <div>
                        <div class="order-table-title">🪑 ${t.masa_no}</div>
                        <div class="order-code">Aktif Kalem: ${itemsList.length} Ürün</div>
                    </div>
                    <span class="table-badge" style="background:${isDolu ? (isPaidOnline ? '#10b981' : '#f59e0b') : '#64748b'}; color:#fff; font-weight:800;">
                        ${isDolu ? (isPaidOnline ? '💳 ÖDENDİ (Masada Yiyor)' : '🟡 HESAP AÇIK (Kasada Ödeyecek)') : '🟢 BOŞ'}
                    </span>
                </div>

                ${pendingApprovalOrders.length > 0 ? `
                    <div style="background:rgba(59,130,246,0.12); border:1px solid #3b82f6; padding:8px 12px; border-radius:var(--radius-sm); font-size:0.8rem; color:#60a5fa; margin-bottom:10px;">
                        🛎️ Garson Masada Sipariş Onayında (${pendingApprovalOrders.length} Sipariş Onay Bekliyor)
                    </div>
                ` : ''}

                <div style="margin: 10px 0; padding:12px; background:rgba(0,0,0,0.2); border:1px solid var(--border-color); border-radius:var(--radius-md);">
                    <div style="font-size:0.82rem; font-weight:700; color:var(--text-secondary); margin-bottom:6px;">📋 Adisyon Detayı (Ürün Listesi):</div>
                    
                    ${itemsList.length === 0 ? '<div style="font-size:0.82rem; color:var(--text-muted);">Henüz onaylanmış ürün yok.</div>' : ''}
                    
                    <div style="max-height:180px; overflow-y:auto; display:flex; flex-direction:column; gap:4px;">
                        ${itemsList.map(item => `
                            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.88rem; padding:4px 0; border-bottom:1px dashed rgba(255,255,255,0.05);">
                                <div>
                                    <span style="font-weight:700;">${item.adet}x ${item.urun_adi}</span>
                                    ${item.urun_notu ? `<div style="font-size:0.75rem; color:var(--text-secondary);">${item.urun_notu}</div>` : ''}
                                </div>
                                <span style="font-weight:800; color:#fbbf24;">${item.ara_toplam.toFixed(2)} ₺</span>
                            </div>
                        `).join('')}
                    </div>

                    <div style="display:flex; justify-content:space-between; border-top:1px solid rgba(255,255,255,0.1); margin-top:8px; padding-top:6px; font-weight:800; font-size:1.05rem; color:#fbbf24;">
                        <span>Toplam Masa Adisyonu:</span>
                        <span>${totalBill.toFixed(2)} ₺</span>
                    </div>
                </div>

                ${isDolu ? (masaOrders.length > 0 ? `
                    <div style="display:flex; flex-direction:column; gap:8px;">
                        <button class="btn-add" style="justify-center; width:100%; padding:10px; font-size:0.9rem; background:linear-gradient(135deg, #3b82f6, #1d4ed8);" onclick="openParcaliModal(${t.id})">
                            💵 Tahsilat Yap / Parçalı Ödeme
                        </button>
                        <button class="btn-status-action btn-success" style="width:100%; padding:10px; font-weight:800; font-size:0.9rem;" onclick="collectAndClearTable(${t.id})">
                            Tüm Ödemeyi Tahsil Et & Oturumu Sonlandır
                        </button>
                    </div>
                ` : `
                    <div style="background:rgba(245,158,11,0.15); border:1px solid #f59e0b; padding:10px; border-radius:var(--radius-md); font-size:0.85rem; color:#fbbf24; text-align:center; font-weight:700;">
                        🛎️ Garson Masada Sipariş Onayında (Henüz Kesinleşmedi)
                    </div>
                `) : '<div style="font-size:0.85rem; color:var(--text-muted); text-align:center; padding:8px;">Masa boş ve hazır.</div>'}
            </div>
        `;
    });

    container.innerHTML = html || '<div style="color:var(--text-muted);">Masa bulunamadı.</div>';
}

let currentTableTotalBill = 0;
let currentTablePaidBill = 0;
let currentTableRemainingBill = 0;
let activeParcaliTab = 'kalem';

window.switchParcaliTab = function(tabName) {
    activeParcaliTab = tabName;
    const btnKalem = document.getElementById('tabBtnKalem');
    const btnTutar = document.getElementById('tabBtnTutar');
    const contentKalem = document.getElementById('tabContentKalem');
    const contentTutar = document.getElementById('tabContentTutar');

    if (tabName === 'kalem') {
        if (btnKalem) { btnKalem.style.background = 'var(--primary)'; btnKalem.style.color = '#000'; }
        if (btnTutar) { btnTutar.style.background = 'rgba(255,255,255,0.08)'; btnTutar.style.color = '#fff'; }
        if (contentKalem) contentKalem.style.display = 'block';
        if (contentTutar) contentTutar.style.display = 'none';
    } else {
        if (btnTutar) { btnTutar.style.background = 'var(--primary)'; btnTutar.style.color = '#000'; }
        if (btnKalem) { btnKalem.style.background = 'rgba(255,255,255,0.08)'; btnKalem.style.color = '#fff'; }
        if (contentTutar) contentTutar.style.display = 'block';
        if (contentKalem) contentKalem.style.display = 'none';
        updateTutarTabUI();
    }
};

function openParcaliModal(masaId) {
    activeKasaMasaId = masaId;
    const table = kasaTables.find(t => t.id === masaId);
    const modalTitle = document.getElementById('parcaliModalTitle');
    if (modalTitle) modalTitle.innerText = `💳 ${table ? table.masa_no : ''} - Tahsilat & Parçalı Ödeme`;

    const masaOrders = kasaOrders.filter(o => o.masa_id === masaId && o.odeme_durumu !== 'odendi' && ['odendi_mutfakta', 'garson_onayladi_mutfakta', 'hazirlaniyor', 'hazir', 'teslim_edildi'].includes(o.siparis_durumu));
    
    currentTableItems = [];
    currentTableTotalBill = 0;

    masaOrders.forEach(o => {
        (o.detaylar || []).forEach((d, idx) => {
            const itemTotal = d.ara_toplam || (d.adet * d.birim_fiyat);
            currentTableTotalBill += itemTotal;
            currentTableItems.push({
                uniqueId: `${o.id}_${idx}`,
                siparis_id: o.id,
                urun_adi: d.urun_adi,
                adet: d.adet,
                birim_fiyat: d.birim_fiyat,
                ara_toplam: itemTotal,
                selected: false
            });
        });
    });

    if (!window.partialPaymentsMap) window.partialPaymentsMap = {};
    currentTablePaidBill = window.partialPaymentsMap[masaId] || 0;
    currentTableRemainingBill = Math.max(0, currentTableTotalBill - currentTablePaidBill);

    switchParcaliTab('kalem');
    renderParcaliModalItems();
    document.getElementById('parcaliOdemeModal').classList.add('active');
}

function updateTutarTabUI() {
    const totalEl = document.getElementById('tutarModalTotal');
    const paidEl = document.getElementById('tutarModalPaid');
    const remainingEl = document.getElementById('tutarModalRemaining');
    const inputEl = document.getElementById('tutarInputAmount');

    if (totalEl) totalEl.innerText = `${currentTableTotalBill.toFixed(2)} ₺`;
    if (paidEl) paidEl.innerText = `${currentTablePaidBill.toFixed(2)} ₺`;
    if (remainingEl) remainingEl.innerText = `${currentTableRemainingBill.toFixed(2)} ₺`;
    if (inputEl) inputEl.value = currentTableRemainingBill.toFixed(2);
}

window.fillRemainingAmount = function() {
    const inputEl = document.getElementById('tutarInputAmount');
    if (inputEl) inputEl.value = currentTableRemainingBill.toFixed(2);
};

window.processTutarPayment = async function(paymentMethod) {
    const inputEl = document.getElementById('tutarInputAmount');
    const amount = parseFloat(inputEl ? inputEl.value : 0);

    if (isNaN(amount) || amount <= 0) {
        alert("Lütfen geçerli bir tahsilat tutarı giriniz.");
        return;
    }

    if (amount > currentTableRemainingBill + 0.05) {
        alert(`Girdiğiniz tutar kalan bakiyeden (${currentTableRemainingBill.toFixed(2)} ₺) fazla olamaz.`);
        return;
    }

    if (!confirm(`${amount.toFixed(2)} ₺ (${paymentMethod}) tahsilatını onaylıyor musunuz?`)) return;

    if (!window.partialPaymentsMap) window.partialPaymentsMap = {};
    window.partialPaymentsMap[activeKasaMasaId] = (window.partialPaymentsMap[activeKasaMasaId] || 0) + amount;
    
    currentTablePaidBill = window.partialPaymentsMap[activeKasaMasaId];
    currentTableRemainingBill = Math.max(0, currentTableTotalBill - currentTablePaidBill);

    showKasaToast(`💵 ${amount.toFixed(2)} ₺ ${paymentMethod} ile tahsil edildi!`);

    if (currentTableRemainingBill <= 0.05) {
        delete window.partialPaymentsMap[activeKasaMasaId];
        closeParcaliModal();
        await collectAndClearTable(activeKasaMasaId, false);
    } else {
        updateTutarTabUI();
        loadKasaData();
    }
};

function renderParcaliModalItems() {
    const container = document.getElementById('parcaliItemList');
    const totalSpan = document.getElementById('parcaliSelectedTotal');

    let selectedSum = 0;
    let html = '';

    currentTableItems.forEach((item, index) => {
        if (item.selected) selectedSum += item.ara_toplam;

        html += `
            <label style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px; background:${item.selected ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.03)'}; border:1px solid ${item.selected ? 'var(--success)' : 'var(--border-color)'}; border-radius:var(--radius-md); cursor:pointer;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <input type="checkbox" ${item.selected ? 'checked' : ''} onchange="toggleParcaliItem(${index})" style="width:18px; height:18px; accent-color:var(--success);">
                    <span style="font-weight:700; font-size:0.95rem;">${item.adet}x ${item.urun_adi}</span>
                </div>
                <span style="font-weight:800; color:#fbbf24;">${item.ara_toplam.toFixed(2)} ₺</span>
            </label>
        `;
    });

    container.innerHTML = html || '<div style="color:var(--text-muted); padding:10px;">Tahsil edilecek ürün bulunmuyor.</div>';
    if (totalSpan) totalSpan.innerText = `${selectedSum.toFixed(2)} ₺`;
}

function toggleParcaliItem(index) {
    if (currentTableItems[index]) {
        currentTableItems[index].selected = !currentTableItems[index].selected;
        renderParcaliModalItems();
    }
}

function closeParcaliModal() {
    document.getElementById('parcaliOdemeModal').classList.remove('active');
    activeKasaMasaId = null;
    currentTableItems = [];
}

async function processParcaliPayment(paymentMethod) {
    const selectedItems = currentTableItems.filter(i => i.selected);
    if (selectedItems.length === 0) {
        alert("Lütfen tahsil edilmek istenen en az 1 ürün seçiniz.");
        return;
    }

    const selectedTotal = selectedItems.reduce((sum, i) => sum + i.ara_toplam, 0);

    if (!confirm(`${selectedItems.length} kalem ürün için toplam ${selectedTotal.toFixed(2)} ₺ (${paymentMethod}) tahsilatını onaylıyor musunuz?`)) return;

    try {
        closeParcaliModal();
        showKasaToast(`💵 ${selectedTotal.toFixed(2)} ₺ ${paymentMethod} ile tahsil edildi!`);
        
        if (selectedItems.length === currentTableItems.length) {
            await collectAndClearTable(activeKasaMasaId, false);
        } else {
            if (!window.partialPaymentsMap) window.partialPaymentsMap = {};
            window.partialPaymentsMap[activeKasaMasaId] = (window.partialPaymentsMap[activeKasaMasaId] || 0) + selectedTotal;
            loadKasaData();
        }
    } catch(e) {
        alert("Tahsilat işlemi sırasında hata oluştu.");
    }
}

async function collectAndClearTable(masaId, askConfirm = true) {
    if (askConfirm && !confirm("Masa ödemesi kasada tamamen tahsil edilecek ve masa oturumu sonlandırılacaktır. Onaylıyor musunuz?")) return;
    try {
        const res = await fetch(`/api/masalar/${masaId}/clear`, { method: 'POST' });
        if (res.ok) {
            if (window.partialPaymentsMap) delete window.partialPaymentsMap[masaId];
            loadKasaData();
            showKasaToast("Ödeme tahsil edildi, masa oturumu sonlandırıldı!");
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
