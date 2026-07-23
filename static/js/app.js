// ==========================================================================
// CUSTOMER QR MENU & CART & LIVE ORDER TRACKING LOGIC (GÜNCELLENMİŞ)
// ==========================================================================

let state = {
    masaId: 1,
    masaNo: "Masa 1",
    kategoriler: [],
    urunler: [],
    activeKategoriId: null,
    cart: [],
    currentProduct: null,
    selectedSize: null,
    selectedExtras: [],
    activeNotes: [],
    currentOrder: null,
    selectedCard: "Garanti BBVA Bonus (**** 4821)",
    language: localStorage.getItem('qr_language') || null
};

// KATEGORİ İKONLARI
const CATEGORY_ICONS = {
    'corbalar': '🍲',
    'ana yemekler': '🍕',
    'tatlilar': '🍰',
    'icecekler': '🥤'
};

// PIZZA BOYUTLARI
const PIZZA_SIZES = [
    { id: 'small', name: 'Küçük Boy', detail: '20 cm • 1 Kişilik', priceDiff: 0 },
    { id: 'medium', name: 'Orta Boy', detail: '26 cm • 1-2 Kişilik', priceDiff: 40.00 },
    { id: 'large', name: 'Büyük Boy', detail: '32 cm • 2-3 Kişilik', priceDiff: 85.00 },
    { id: 'jumbo', name: 'Jumbo Boy', detail: '40 cm • 3-4 Kişilik', priceDiff: 140.00 }
];

// İÇECEK / YEMEK ÇİPLERİ
const CUSTOM_CHIPS_MAP = {
    'icecek': [
        { text: '🧊 Soğuk (Dolaptan)', group: 'temp' },
        { text: '🌡️ Oda Sıcaklığında', group: 'temp' },
        { text: '🧊 Ekstra Buzlu', group: 'extra', dependsOn: 'cold' },
        { text: '🥤 Pipetli Olsun', group: 'extra' }
    ],
    'pizza': [
        { text: '🚫 Biber Olmasın', group: 'extra' },
        { text: '🚫 Soğan Olmasın', group: 'extra' },
        { text: '🚫 Mantar Olmasın', group: 'extra' },
        { text: '🚫 Sucuk Olmasın', group: 'extra' },
        { text: '🚫 Mısır Olmasın', group: 'extra' }
    ],
    'corba_yemek': [
        { text: '🍞 Kruton Bol Olsun', group: 'extra' },
        { text: '🌶️ Acısız Olsun', group: 'extra' },
        { text: '🧅 Soğansız Olsun', group: 'extra' }
    ],
    'tatli': [
        { text: '🍯 Az Şerbetli', group: 'extra' },
        { text: '🔥 Bol Sıcak Servis', group: 'extra' }
    ]
};

// TATLI EKSTRALARI
const DESSERT_EXTRAS = [
    { id: 'kaymak', name: 'Ekstra Manda Kaymağı', price: 35.00 },
    { id: 'dondurma', name: 'Ekstra Maraş Dondurması', price: 40.00 },
    { id: 'cikolata', name: 'Ekstra Belçika Çikolata Sosu', price: 25.00 },
    { id: 'fistik', name: 'Ekstra Antep Fıstığı Tozu', price: 30.00 }
];

function playNotificationSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
        osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.3);
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const masaParam = urlParams.get('masa') || '1';
    state.masaId = parseInt(masaParam);
    state.masaNo = `Masa ${state.masaId}`;

    const tableBadge = document.getElementById('tableBadge');
    if (tableBadge) tableBadge.innerHTML = `🪑 ${state.masaNo}`;

    // Dil seçimi yapılmamışsa aç
    if (!state.language) {
        document.getElementById('languageModal').classList.add('active');
    }

    loadCategories();
    loadProducts();
    checkActiveOrder(); // F5 RECOVERY

    // Socket.io Canlı Dinleyici (Otomatik Reconnection Ayarları)
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

    socket.on('durum_guncellendi', (data) => {
        if (data.masa_id === state.masaId && state.currentOrder) {
            state.currentOrder.siparis_durumu = data.yeni_durum;
            if (data.odeme_durumu) state.currentOrder.odeme_durumu = data.odeme_durumu;
            renderOrderTrackingUI();
            playNotificationSound();
        }
    });

    socket.on('nakit_odendi', (data) => {
        if (data.masa_id === state.masaId && state.currentOrder) {
            state.currentOrder.odeme_durumu = 'odendi';
            renderOrderTrackingUI();
            playNotificationSound();
            showToast("💵 Garson nakit ödemenizi tahsil etti. Teşekkürler!");
        }
    });
});

async function checkActiveOrder() {
    try {
        const res = await fetch(`/api/masalar/${state.masaId}/aktif-siparis`);
        const data = await res.json();
        if (data.has_active && data.siparis) {
            state.currentOrder = data.siparis;
            renderOrderTrackingUI();
        }
    } catch (e) {
        console.error("Aktif sipariş yüklenemedi:", e);
    }
}

function selectLanguage(lang) {
    state.language = lang;
    localStorage.setItem('qr_language', lang);
    document.getElementById('languageModal').classList.remove('active');
    showToast(lang === 'tr' ? 'Menü Türkçe olarak ayarlandı.' : 'Menu set to English.');
}

async function loadCategories() {
    try {
        const res = await fetch('/api/kategoriler');
        state.kategoriler = await res.json();
        renderCategoryGrid();
    } catch (e) {
        console.error("Kategoriler yüklenemedi:", e);
    }
}

async function loadProducts(kategoriId = null) {
    try {
        let url = '/api/urunler';
        if (kategoriId) url += `?kategori_id=${kategoriId}`;
        const res = await fetch(url);
        state.urunler = await res.json();
        renderProducts();
    } catch (e) {
        console.error("Ürünler yüklenemedi:", e);
    }
}

// KUTU KUTU GÖRSELLİ KATEGORİLER
function renderCategoryGrid() {
    const container = document.getElementById('categoryGridBar');
    if (!container) return;

    let html = `
        <div class="category-card-box ${state.activeKategoriId === null ? 'active' : ''}" onclick="selectCategory(null)">
            <span class="category-card-icon">🍽️</span>
            <span class="category-card-title">Tümü</span>
        </div>
    `;

    state.kategoriler.forEach(cat => {
        const icon = CATEGORY_ICONS[cat.kategori_adi.toLowerCase()] || '🍴';
        html += `
            <div class="category-card-box ${state.activeKategoriId === cat.id ? 'active' : ''}" onclick="selectCategory(${cat.id})">
                <span class="category-card-icon">${icon}</span>
                <span class="category-card-title">${cat.kategori_adi}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

function selectCategory(catId) {
    state.activeKategoriId = catId;
    renderCategoryGrid();
    loadProducts(catId);
}

function renderProducts() {
    const grid = document.getElementById('productGrid');
    if (!grid) return;

    if (state.urunler.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 40px;">Ürün bulunmuyor.</div>`;
        return;
    }

    let html = '';
    state.urunler.forEach(prod => {
        html += `
            <div class="product-card">
                <div>
                    <div class="product-title">${prod.urun_adi}</div>
                    <div class="product-desc">${prod.aciklama || ''}</div>
                </div>
                <div class="product-footer">
                    <div class="product-price">${prod.fiyat.toFixed(2)} ₺</div>
                    <button class="btn-add" onclick="openProductNoteModal(${prod.id})">
                        <span>+ Ekle / Seç</span>
                    </button>
                </div>
            </div>
        `;
    });

    grid.innerHTML = html;
}

// ÜRÜN MODALİ
function openProductNoteModal(productId) {
    const prod = state.urunler.find(p => p.id === productId);
    if (!prod) return;

    state.currentProduct = prod;
    state.selectedSize = PIZZA_SIZES[0];
    state.selectedExtras = [];
    state.activeNotes = [];

    document.getElementById('modalProductTitle').innerText = prod.urun_adi;
    document.getElementById('modalProductDesc').innerText = prod.aciklama || '';
    document.getElementById('modalProductNote').value = '';
    document.getElementById('modalQuantity').value = '1';

    const catName = (prod.kategori_adi || '').toLowerCase();
    const prodName = (prod.urun_adi || '').toLowerCase();

    // Pizza Boyutları
    const pizzaSection = document.getElementById('pizzaSizeSection');
    if (prodName.includes('pizza') || catName.includes('pizza') || catName.includes('ana yemek')) {
        pizzaSection.style.display = 'block';
        renderPizzaSizes();
    } else {
        pizzaSection.style.display = 'none';
    }

    // Tatlı Ekstraları
    const extrasSection = document.getElementById('dessertExtrasSection');
    if (catName.includes('tatli') || prodName.includes('kunefe') || prodName.includes('tatlı')) {
        extrasSection.style.display = 'block';
        renderDessertExtras();
    } else {
        extrasSection.style.display = 'none';
    }

    renderQuickNotesChips(catName, prodName);
    updateModalCalculatedPrice();

    document.getElementById('productModal').classList.add('active');
}

function renderPizzaSizes() {
    const container = document.getElementById('pizzaSizeGrid');
    if (!container) return;

    let html = '';
    PIZZA_SIZES.forEach(size => {
        const isSelected = state.selectedSize.id === size.id;
        html += `
            <div class="size-option-card ${isSelected ? 'active' : ''}" onclick="selectPizzaSize('${size.id}')">
                <div class="size-name">${size.name}</div>
                <div class="size-detail">${size.detail}</div>
                <div class="size-price-diff">${size.priceDiff > 0 ? `+${size.priceDiff.toFixed(2)} ₺` : 'Standart'}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function selectPizzaSize(sizeId) {
    state.selectedSize = PIZZA_SIZES.find(s => s.id === sizeId) || PIZZA_SIZES[0];
    renderPizzaSizes();
    updateModalCalculatedPrice();
}

function renderDessertExtras() {
    const container = document.getElementById('dessertExtrasList');
    if (!container) return;

    let html = '';
    DESSERT_EXTRAS.forEach(extra => {
        const isSelected = state.selectedExtras.some(e => e.id === extra.id);
        html += `
            <div class="extra-item-row ${isSelected ? 'selected' : ''}" onclick="toggleDessertExtra('${extra.id}')">
                <div class="extra-name">${extra.name}</div>
                <div class="extra-price">+${extra.price.toFixed(2)} ₺</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function toggleDessertExtra(extraId) {
    const existingIndex = state.selectedExtras.findIndex(e => e.id === extraId);
    if (existingIndex > -1) {
        state.selectedExtras.splice(existingIndex, 1);
    } else {
        const extraObj = DESSERT_EXTRAS.find(e => e.id === extraId);
        if (extraObj) state.selectedExtras.push(extraObj);
    }
    renderDessertExtras();
    updateModalCalculatedPrice();
}

// BİRBİRİYLE ÇELİŞEN ÇİPLERİ ENGELLEYEN YAPI (Oda Sıcaklığında -> Buz Kapanır)
function renderQuickNotesChips(catName, prodName) {
    const container = document.getElementById('quickNotesContainer');
    if (!container) return;

    let chipsData = CUSTOM_CHIPS_MAP['corba_yemek'];

    if (catName.includes('icecek') || prodName.includes('kola') || prodName.includes('ayran')) {
        chipsData = CUSTOM_CHIPS_MAP['icecek'];
    } else if (catName.includes('pizza') || prodName.includes('pizza')) {
        chipsData = CUSTOM_CHIPS_MAP['pizza'];
    } else if (catName.includes('tatli') || prodName.includes('kunefe')) {
        chipsData = CUSTOM_CHIPS_MAP['tatli'];
    }

    const isRoomTempSelected = state.activeNotes.includes('🌡️ Oda Sıcaklığında');

    let html = '';
    chipsData.forEach(chipObj => {
        const chipText = chipObj.text;
        const isActive = state.activeNotes.includes(chipText);
        let isDisabled = false;

        // EĞER ODA SICAKLIĞINDA SEÇİLİYSEN BUZ SEÇENEĞİ KANANIR!
        if (chipObj.dependsOn === 'cold' && isRoomTempSelected) {
            isDisabled = true;
        }

        html += `
            <span class="quick-note-chip ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}" 
                  onclick="${isDisabled ? '' : `toggleNoteChip('${chipText.replace(/'/g, "\\'")}', '${chipObj.group || 'extra'}')`}">
                ${chipText}
            </span>
        `;
    });
    container.innerHTML = html;
}

function toggleNoteChip(text, group) {
    const noteInput = document.getElementById('modalProductNote');
    
    // Aynı gruptakileri yönet (Örn: Oda sıcaklığında seçildiğinde Soğuk dolaptan kapatılır)
    if (group === 'temp') {
        state.activeNotes = state.activeNotes.filter(n => !n.includes('Soğuk') && !n.includes('Oda Sıcaklığında'));
        if (text.includes('Oda Sıcaklığında')) {
            // Oda sıcaklığında seçildiyse buz çipini de notlardan sil!
            state.activeNotes = state.activeNotes.filter(n => !n.includes('Buzlu'));
        }
    }

    if (state.activeNotes.includes(text)) {
        state.activeNotes = state.activeNotes.filter(n => n !== text);
    } else {
        state.activeNotes.push(text);
    }

    noteInput.value = state.activeNotes.join(', ');

    const catName = (state.currentProduct.kategori_adi || '').toLowerCase();
    const prodName = (state.currentProduct.urun_adi || '').toLowerCase();
    renderQuickNotesChips(catName, prodName);
}

function updateModalCalculatedPrice() {
    if (!state.currentProduct) return;

    let basePrice = state.currentProduct.fiyat;
    const catName = (state.currentProduct.kategori_adi || '').toLowerCase();
    const prodName = (state.currentProduct.urun_adi || '').toLowerCase();
    
    if ((prodName.includes('pizza') || catName.includes('pizza')) && state.selectedSize) {
        basePrice += state.selectedSize.priceDiff;
    }

    state.selectedExtras.forEach(ex => {
        basePrice += ex.price;
    });

    const quantity = parseInt(document.getElementById('modalQuantity').value) || 1;
    document.getElementById('modalProductPrice').innerText = `${(basePrice * quantity).toFixed(2)} ₺`;
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function confirmAddToCart() {
    if (!state.currentProduct) return;

    const quantity = parseInt(document.getElementById('modalQuantity').value) || 1;
    const manualNote = document.getElementById('modalProductNote').value.trim();

    let calculatedUnitPrice = state.currentProduct.fiyat;
    let fullTitle = state.currentProduct.urun_adi;
    let combinedNotes = [];

    const catName = (state.currentProduct.kategori_adi || '').toLowerCase();
    const prodName = (state.currentProduct.urun_adi || '').toLowerCase();
    
    if ((prodName.includes('pizza') || catName.includes('pizza')) && state.selectedSize) {
        calculatedUnitPrice += state.selectedSize.priceDiff;
        fullTitle += ` (${state.selectedSize.name})`;
    }

    if (state.selectedExtras.length > 0) {
        state.selectedExtras.forEach(ex => {
            calculatedUnitPrice += ex.price;
            combinedNotes.push(`+ ${ex.name}`);
        });
    }

    if (manualNote) combinedNotes.push(manualNote);

    state.cart.push({
        id: Date.now(),
        urun_id: state.currentProduct.id,
        urun_adi: fullTitle,
        birim_fiyat: calculatedUnitPrice,
        adet: quantity,
        urun_notu: combinedNotes.join(' • '),
        ara_toplam: calculatedUnitPrice * quantity
    });

    closeModal('productModal');
    updateCartUI();
    playNotificationSound();
    showToast(`${fullTitle} sepete eklendi!`);
}

function updateCartUI() {
    const totalCount = state.cart.reduce((acc, item) => acc + item.adet, 0);
    const totalPrice = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    const floatingBtn = document.getElementById('cartFloatingBtn');
    const cartBadge = document.getElementById('cartBadge');
    const cartTotalPrice = document.getElementById('cartTotalPrice');

    if (cartBadge) cartBadge.innerText = totalCount;
    if (cartTotalPrice) cartTotalPrice.innerText = `${totalPrice.toFixed(2)} ₺`;

    if (floatingBtn) {
        floatingBtn.style.display = totalCount > 0 ? 'flex' : 'none';
    }
}

function openCartModal() {
    const cartItemsContainer = document.getElementById('cartItemsContainer');
    const modalCartTotal = document.getElementById('modalCartTotal');
    const totalPrice = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    if (state.cart.length === 0) {
        cartItemsContainer.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--text-secondary);">Sepetiniz boş.</div>`;
    } else {
        let html = '';
        state.cart.forEach((item, index) => {
            html += `
                <div class="order-item-row">
                    <div class="order-item-main">
                        <span>${item.adet}x ${item.urun_adi}</span>
                        <span>${item.ara_toplam.toFixed(2)} ₺</span>
                    </div>
                    ${item.urun_notu ? `<div class="order-item-note">Not / Opsiyon: ${item.urun_notu}</div>` : ''}
                    <div style="text-align: right; margin-top: 4px;">
                        <button style="background:none; color: var(--danger); font-size: 0.8rem; font-weight:700;" onclick="removeCartItem(${index})">Sil</button>
                    </div>
                </div>
            `;
        });
        cartItemsContainer.innerHTML = html;
    }

    if (modalCartTotal) modalCartTotal.innerText = `${totalPrice.toFixed(2)} ₺`;
    document.getElementById('cartModal').classList.add('active');
}

function removeCartItem(index) {
    state.cart.splice(index, 1);
    updateCartUI();
    openCartModal();
}

// PRATİK ÖDEME SEÇENEKLERİ (POS 1-TIK & MASADA NAKİT)
async function submitOrder(odemeYontemi) {
    if (state.cart.length === 0) return;

    if (odemeYontemi === 'pos') {
        // Doğrudan sipariş vermek yerine 2. Onay & Kart Seçim Modali Aç!
        closeModal('cartModal');
        openPayModal();
        return;
    }

    // Masada Nakit Öde seçeneği ise doğrudan siparişi gönder
    closeModal('cartModal');
    await executeOrderSubmit('nakit');
}

function openPayModal() {
    const totalAmount = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);
    const totalCount = state.cart.reduce((acc, item) => acc + item.adet, 0);

    const payModalAmount = document.getElementById('payModalAmount');
    const payModalItemCount = document.getElementById('payModalItemCount');

    if (payModalAmount) payModalAmount.innerText = `${totalAmount.toFixed(2)} ₺`;
    if (payModalItemCount) payModalItemCount.innerText = `${totalCount} adet ürün sepette`;

    document.getElementById('payModal').classList.add('active');
}

function selectPayCard(element, cardName) {
    document.querySelectorAll('.pay-card-item').forEach(el => {
        el.classList.remove('active');
        const check = el.querySelector('.pay-check-icon');
        if (check) check.style.display = 'none';
    });

    element.classList.add('active');
    const checkIcon = element.querySelector('.pay-check-icon');
    if (checkIcon) checkIcon.style.display = 'block';

    state.selectedCard = cardName;
}

async function confirmPaymentAndSubmit() {
    closeModal('payModal');
    await executeOrderSubmit('pos');
}

async function executeOrderSubmit(odemeYontemi) {
    const totalPrice = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    const payload = {
        masa_id: state.masaId,
        toplam_tutar: totalPrice,
        odeme_yontemi: odemeYontemi,
        urunler: state.cart.map(item => ({
            urun_id: item.urun_id,
            adet: item.adet,
            birim_fiyat: item.birim_fiyat,
            urun_notu: item.urun_notu
        }))
    };

    try {
        const res = await fetch('/api/siparisler', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok) {
            state.cart = [];
            state.currentOrder = data.siparis;
            updateCartUI();
            
            renderOrderTrackingUI();
            playNotificationSound();

            if (odemeYontemi === 'pos') {
                showToast(`💳 ${state.selectedCard || 'Kart'} ile ödeme onaylandı ve sipariş alındı!`);
            } else {
                showToast("💵 Masada nakit ödeme talebiniz iletildi!");
            }
        } else {
            alert(data.detail || "Hata oluştu.");
        }
    } catch (e) {
        alert("Sunucuya ulaşılamadı.");
    }
}

// CANLI SİPARİŞ TAKİP EKRANI (NET CANLI DURUM & VERİLEN SİPARİŞ LİSTESİ)
function renderOrderTrackingUI() {
    const container = document.getElementById('orderTrackingContainer');
    if (!container || !state.currentOrder) return;

    const status = state.currentOrder.siparis_durumu;
    const isCashPending = state.currentOrder.odeme_yontemi === 'nakit' && state.currentOrder.odeme_durumu !== 'odendi';
    
    container.style.display = 'block';

    // Teslim edildi durumu
    if (status === 'teslim_edildi') {
        container.innerHTML = `
            <div class="tracking-card" style="border-color: var(--success); background: rgba(16, 185, 129, 0.1);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <h3 style="font-size: 1.15rem; color: var(--success);">🎉 Masanıza Teslim Edildi</h3>
                    <button style="background:none; color:var(--text-secondary); font-size:0.85rem; cursor:pointer;" onclick="dismissTrackingUI()">Kapat ✖</button>
                </div>
                <div style="font-size: 0.88rem; color: var(--text-secondary);">Afiyet olsun! Bizi tercih ettiğiniz için teşekkür ederiz.</div>
            </div>
        `;
        return;
    }
    
    let currentStatusHTML = '';

    if (status === 'odendi_mutfakta') {
        if (isCashPending) {
            currentStatusHTML = `
                <div class="single-status-banner active-step-received" style="border-color: #fbbf24; background: rgba(245, 158, 11, 0.15);">
                    <div class="status-icon-large">💵</div>
                    <div class="status-info">
                        <div class="status-title-main" style="color:#fbbf24;">Garson Bekleniyor (Nakit Ödeme)</div>
                        <div class="status-sub-desc">Siparişiniz alındı mutfağa iletildi. Garson masanızdan nakit tahsilatı yapmak üzere geliyor.</div>
                    </div>
                </div>
            `;
        } else {
            currentStatusHTML = `
                <div class="single-status-banner active-step-received">
                    <div class="status-icon-large">✅</div>
                    <div class="status-info">
                        <div class="status-title-main">Siparişiniz Alındı</div>
                        <div class="status-sub-desc">Ödemeniz Onaylandı • Mutfak onayına sunuldu.</div>
                    </div>
                </div>
            `;
        }
    } else if (status === 'hazirlaniyor') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-preparing">
                <div class="status-icon-large">👨‍🍳</div>
                <div class="status-info">
                    <div class="status-title-main">Mutfakta Hazırlanıyor</div>
                    <div class="status-sub-desc">Şeflerimiz siparişinizi hazırlıyor. Tahmini süre: <strong style="color:#fbbf24;">~10 - 15 dk</strong></div>
                </div>
            </div>
        `;
    } else if (status === 'hazir') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-ready">
                <div class="status-icon-large">🔔</div>
                <div class="status-info">
                    <div class="status-title-main">Yemeğiniz Hazır!</div>
                    <div class="status-sub-desc">Garson siparişinizi masanıza getirmek üzere servis tepsisine aldı.</div>
                </div>
            </div>
        `;
    }

    // ÜRÜN DETAYLARI LİSTESİ (MÜŞTERİ NE SİPARİŞ ETTİĞİNİ GÖREBİLİR)
    let detailsHTML = '';
    const detaylar = state.currentOrder.detaylar || [];
    detaylar.forEach(item => {
        detailsHTML += `
            <div class="order-item-row" style="padding: 6px 0;">
                <div class="order-item-main" style="font-size: 0.95rem;">
                    <span>${item.adet}x ${item.urun_adi}</span>
                    <span>${(item.ara_toplam || (item.adet * item.birim_fiyat)).toFixed(2)} ₺</span>
                </div>
                ${item.urun_notu ? `<div class="order-item-note" style="font-size: 0.78rem;">${item.urun_notu}</div>` : ''}
            </div>
        `;
    });

    const paymentBadge = isCashPending
        ? `<span class="table-badge" style="background: #d97706;">💵 Masada Nakit (Bekliyor)</span>`
        : `<span class="table-badge" style="background: var(--success);">💳 Ödendi / Onaylı</span>`;

    let html = `
        <div class="tracking-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
                <span style="font-size: 0.8rem; font-weight:800; color: var(--primary); letter-spacing: 0.5px;">🚀 CANLI SİPARİŞ TAKİBİ (${state.currentOrder.siparis_kodu || ''})</span>
                <span class="table-badge">🪑 ${state.masaNo}</span>
            </div>
            
            ${currentStatusHTML}

            <!-- VERİLEN SİPARİŞİN İÇERİĞİ -->
            <div style="margin-top: 16px; background: rgba(0,0,0,0.2); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 8px;">
                    <span style="font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">🛒 Verilen Sipariş Detayı:</span>
                    ${paymentBadge}
                </div>
                
                <div style="max-height: 200px; overflow-y: auto;">
                    ${detailsHTML}
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px; font-weight: 800;">
                    <span>Toplam Tutar:</span>
                    <span style="color: #fbbf24; font-size: 1.15rem;">${(state.currentOrder.toplam_tutar || 0).toFixed(2)} ₺</span>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function dismissTrackingUI() {
    state.currentOrder = null;
    document.getElementById('orderTrackingContainer').style.display = 'none';
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: #fff;
        padding: 12px 24px;
        border-radius: 12px;
        font-weight: 700;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        z-index: 9999;
    `;
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3500);
}
