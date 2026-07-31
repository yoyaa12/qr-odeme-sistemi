// ==========================================================================
// CUSTOMER QR MENU & CART & LIVE ORDER TRACKING LOGIC (GÜNCELLENMİŞ)
// ==========================================================================

let socket = null;

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
    selectedPaymentMethod: 'pos',
    language: localStorage.getItem('qr_language') || null,
    deviceId: (function() {
        let did = localStorage.getItem('qr_device_id');
        if (!did) {
            did = 'dev-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
            localStorage.setItem('qr_device_id', did);
        }
        return did;
    })()
};

// KATEGORİ İKONLARI
const CATEGORY_ICONS = {
    'tümü': '🍽️',
    'tumu': '🍽️',
    'corbalar': '🍲',
    'çorbalar': '🍲',
    'ana yemekler': '🥩',
    'ana yemek': '🥩',
    'tatlilar': '🍰',
    'tatlılar': '🍰',
    'icecekler': '🥤',
    'içecekler': '🥤',
    'aperatifler': '🍟',
    'salatalar': '🥗',
    'soslar': '🥣',
    'pizzalar': '🍕',
    'pizzalar & pideler': '🍕',
    'makarnalar': '🍝',
    'fast food': '🍔',
    'kahvalti': '🍳',
    'kahvaltı': '🍳'
};

function getCategoryIcon(catName) {
    if (!catName) return '🍴';
    const name = catName.toLowerCase().trim();
    if (CATEGORY_ICONS[name]) return CATEGORY_ICONS[name];
    for (let key in CATEGORY_ICONS) {
        if (name.includes(key) || key.includes(name)) return CATEGORY_ICONS[key];
    }
    return '🍴';
}

// PIZZA BOYUTLARI
const PIZZA_SIZES = [
    { id: 'small', name: 'Küçük Boy', detail: '20 cm • 1 Kişilik', priceDiff: 0 },
    { id: 'medium', name: 'Orta Boy', detail: '26 cm • 1-2 Kişilik', priceDiff: 40.00 },
    { id: 'large', name: 'Büyük Boy', detail: '32 cm • 2-3 Kişilik', priceDiff: 85.00 },
    { id: 'jumbo', name: 'Jumbo Boy', detail: '40 cm • 3-4 Kişilik', priceDiff: 140.00 }
];

// PORSIYON SEÇENEKLERİ (YEMEKLER / IZGARALAR İÇİN)
const PORTION_OPTIONS = [
    { id: 'p1', name: '1 Porsiyon', detail: 'Standart Porsiyon', multiplier: 1.0 },
    { id: 'p1_5', name: '1.5 Porsiyon', detail: '%40 Ekstra Porsiyon', multiplier: 1.40 },
    { id: 'p2', name: '2 Porsiyon (Çift)', detail: 'Doyurucu Çift Porsiyon', multiplier: 1.80 }
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
    } catch (e) { }
}

document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const masaParam = urlParams.get('masa') || '1';
    state.masaId = parseInt(masaParam);
    state.masaNo = `Masa ${state.masaId}`; // Fallback
    
    try {
        const mRes = await fetch('/api/masalar');
        const mData = await mRes.json();
        const gercekMasa = mData.find(m => m.id === state.masaId);
        if (gercekMasa) {
            state.masaNo = gercekMasa.masa_no;
        }
    } catch (e) { console.error(e); }

    const tableBadge = document.getElementById('tableBadge');
    if (tableBadge) tableBadge.innerHTML = `🪑 ${state.masaNo}`;

    // Dil seçimi yapılmamışsa aç
    if (!state.language) {
        document.getElementById('languageModal').classList.add('active');
    }

    loadCategories();
    loadProducts();
    checkActiveOrder(); // F5 RECOVERY: Sayfa yenilendiğinde aktif siparişi getirir!

    // Socket.io Canlı Dinleyici (Otomatik Reconnection Ayarları)
    socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

    socket.on('connect', () => {
        // Müşteri QR menüyü açtığında garsona anında canlı bildirim gönderilir
        socket.emit('musteri_oturdu', { masa_id: state.masaId, masa_no: state.masaNo });
    });

    socket.on('durum_guncellendi', (data) => {
        if (data.masa_id === state.masaId) {
            if (data.yeni_durum === 'bos') {
                state.currentOrder = null;
                const container = document.getElementById('orderTrackingContainer');
                if (container) container.style.display = 'none';
            } else {
                checkActiveOrder();
                playNotificationSound();
            }
        }
    });

    socket.on('masa_temizlendi', (data) => {
        if (data && data.masa_id === state.masaId) {
            state.currentOrder = null;
            state.cart = [];
            updateCartUI();
            const container = document.getElementById('orderTrackingContainer');
            if (container) container.style.display = 'none';
            showToast("ℹ️ Masa hesabı kapatıldı ve oturum sıfırlandı.");
        }
    });

    socket.on('masa_durumu_degisti', (data) => {
        if (data && data.masa_id === state.masaId && data.durum === 'bos') {
            state.currentOrder = null;
            state.cart = [];
            updateCartUI();
            const container = document.getElementById('orderTrackingContainer');
            if (container) container.style.display = 'none';
        }
    });

    socket.on('nakit_odendi', (data) => {
        if (data.masa_id === state.masaId) {
            checkActiveOrder();
            playNotificationSound();
            showToast("💵 Garson nakit ödemenizi tahsil etti. Teşekkürler!");
        }
    });
});

// F5 İLE SAYFA YENİLENDİĞİNDE MÜŞTERİNİN AKTİF SİPARİŞİNİ KURTARAN FONKSİYON
async function checkActiveOrder() {
    try {
        const res = await fetch(`/api/masalar/${state.masaId}/aktif-siparis`);
        const data = await res.json();
        if (data.has_active && data.siparis) {
            state.currentOrder = data.siparis;
            renderOrderTrackingUI();
        } else {
            state.currentOrder = null;
            const container = document.getElementById('orderTrackingContainer');
            if (container) container.style.display = 'none';
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

// DİKEY KATEGORİ SİDEBARI RENDER
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
        const icon = getCategoryIcon(cat.kategori_adi);
        const isActive = state.activeKategoriId === cat.id;
        html += `
            <div class="category-card-box ${isActive ? 'active' : ''}" onclick="selectCategory(${cat.id})">
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
    updateCategoryHeaderTitle(catId);
    loadProducts(catId);
}

function updateCategoryHeaderTitle(catId) {
    const titleEl = document.getElementById('activeCategoryTitle');
    if (!titleEl) return;
    if (catId === null) {
        titleEl.innerText = "Tümü";
    } else {
        const cat = state.kategoriler.find(c => c.id === catId);
        titleEl.innerText = cat ? cat.kategori_adi : "Tümü";
    }
}

// ÜRÜN KARTLARI (2 KOLONLU, SEÇİLİLER MAVİ PARLAYAN VE AÇIKLAMASIZ TASARIM)
function renderProducts() {
    const grid = document.getElementById('productGrid');
    if (!grid) return;

    if (state.urunler.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 40px; background: rgba(255,255,255,0.02); border-radius: 16px; border: 1px dashed var(--border-color);">Bu kategoride henüz ürün bulunmuyor.</div>`;
        return;
    }

    let html = '';
    const dummyRatings = ['4.9', '4.8', '5.0', '4.7', '4.9', '4.8'];

    state.urunler.forEach((prod, index) => {
        const catName = prod.kategori_adi ? prod.kategori_adi : '';
        const icon = getCategoryIcon(catName);
        const rating = dummyRatings[index % dummyRatings.length];
        const hasImage = prod.gorsel_url && prod.gorsel_url.trim().length > 0;

        // Sepette bu üründen kaç tane var?
        const cartItems = state.cart.filter(item => item.urun_id === prod.id);
        const inCartQty = cartItems.reduce((sum, item) => sum + item.adet, 0);
        const isSelected = inCartQty > 0;

        html += `
            <div class="product-card ${isSelected ? 'selected' : ''}" onclick="openProductNoteModal(${prod.id})">
                <div class="product-card-image-box">
                    ${hasImage
                        ? `<img src="${prod.gorsel_url}" alt="${prod.urun_adi}" class="product-card-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                           <div class="product-card-placeholder" style="display:none;"><span>${icon}</span></div>`
                        : `<div class="product-card-placeholder"><span>${icon}</span></div>`
                    }
                    <div class="product-badge-price">₺${prod.fiyat.toFixed(0)}</div>
                    <div class="product-badge-rating">★ ${rating}</div>
                </div>
                
                <div class="product-card-body">
                    <div class="product-title" title="${prod.urun_adi}">${prod.urun_adi}</div>
                </div>

                <div class="product-card-footer">
                    <div class="product-price-bottom">₺${prod.fiyat.toFixed(0)}</div>
                    <div class="product-card-footer-right">
                        ${isSelected ? `<span class="product-cart-qty">${inCartQty}</span>` : ''}
                        <button class="btn-add-circle ${isSelected ? 'active' : ''}" title="Sepete Ekle / Seç" onclick="event.stopPropagation(); openProductNoteModal(${prod.id})">
                            <span>+</span>
                        </button>
                    </div>
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
    state.selectedPortion = PORTION_OPTIONS[0];
    state.selectedExtras = [];
    state.activeNotes = [];

    document.getElementById('modalProductTitle').innerText = prod.urun_adi;
    document.getElementById('modalProductDesc').innerText = prod.aciklama || '';
    document.getElementById('modalProductNote').value = '';
    document.getElementById('modalQuantity').value = '1';

    const catName = (prod.kategori_adi || '').toLowerCase();
    const prodName = (prod.urun_adi || '').toLowerCase();

    const isPizza = prodName.includes('pizza') || catName.includes('pizza');
    const isDish = catName.includes('ana yemek') || catName.includes('izgara') || catName.includes('kebap') || catName.includes('yemek') || prodName.includes('kofte') || prodName.includes('köfte') || prodName.includes('döner') || prodName.includes('doner') || prodName.includes('tavuk') || prodName.includes('et') || prodName.includes('izgara');

    // Pizza Boyutları mi yoksa Yemek Porsiyonları mı?
    const pizzaSection = document.getElementById('pizzaSizeSection');
    const portionSection = document.getElementById('portionSizeSection');

    if (isPizza) {
        if (pizzaSection) pizzaSection.style.display = 'block';
        if (portionSection) portionSection.style.display = 'none';
        renderPizzaSizes();
    } else if (isDish) {
        if (pizzaSection) pizzaSection.style.display = 'none';
        if (portionSection) portionSection.style.display = 'block';
        renderPortionSizes();
    } else {
        if (pizzaSection) pizzaSection.style.display = 'none';
        if (portionSection) portionSection.style.display = 'none';
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
        const isSelected = state.selectedSize && state.selectedSize.id === size.id;
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

function renderPortionSizes() {
    const container = document.getElementById('portionSizeGrid');
    if (!container || !state.currentProduct) return;

    const basePrice = state.currentProduct.fiyat;
    let html = '';
    PORTION_OPTIONS.forEach(p => {
        const isSelected = state.selectedPortion && state.selectedPortion.id === p.id;
        const portionPrice = basePrice * p.multiplier;
        const diff = portionPrice - basePrice;
        html += `
            <div class="size-option-card ${isSelected ? 'active' : ''}" onclick="selectPortionSize('${p.id}')">
                <div class="size-name">${p.name}</div>
                <div class="size-detail">${p.detail}</div>
                <div class="size-price-diff">${diff > 0 ? `+${diff.toFixed(2)} ₺ (${portionPrice.toFixed(2)} ₺)` : 'Standart'}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function selectPortionSize(portionId) {
    state.selectedPortion = PORTION_OPTIONS.find(p => p.id === portionId) || PORTION_OPTIONS[0];
    renderPortionSizes();
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

    if (group === 'temp') {
        state.activeNotes = state.activeNotes.filter(n => !n.includes('Soğuk') && !n.includes('Oda Sıcaklığında'));
        if (text.includes('Oda Sıcaklığında')) {
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
    const isPizza = prodName.includes('pizza') || catName.includes('pizza');
    const isDish = catName.includes('ana yemek') || catName.includes('izgara') || catName.includes('kebap') || catName.includes('yemek') || prodName.includes('kofte') || prodName.includes('köfte') || prodName.includes('döner') || prodName.includes('doner') || prodName.includes('tavuk') || prodName.includes('et') || prodName.includes('izgara');

    if (isPizza && state.selectedSize) {
        basePrice += state.selectedSize.priceDiff;
    } else if (isDish && state.selectedPortion) {
        basePrice = basePrice * state.selectedPortion.multiplier;
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
    const isPizza = prodName.includes('pizza') || catName.includes('pizza');
    const isDish = catName.includes('ana yemek') || catName.includes('izgara') || catName.includes('kebap') || catName.includes('yemek') || prodName.includes('kofte') || prodName.includes('köfte') || prodName.includes('döner') || prodName.includes('doner') || prodName.includes('tavuk') || prodName.includes('et') || prodName.includes('izgara');

    if (isPizza && state.selectedSize) {
        calculatedUnitPrice += state.selectedSize.priceDiff;
        fullTitle += ` (${state.selectedSize.name})`;
    } else if (isDish && state.selectedPortion) {
        calculatedUnitPrice = calculatedUnitPrice * state.selectedPortion.multiplier;
        if (state.selectedPortion.multiplier !== 1.0) {
            fullTitle += ` (${state.selectedPortion.name})`;
        }
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

    notifyCartUpdateToSocket();

    closeModal('productModal');
    updateCartUI();
    playNotificationSound();
    showToast(`${fullTitle} sepete eklendi!`);
}

function notifyCartUpdateToSocket() {
    if (socket && socket.connected) {
        const totalCount = state.cart.reduce((acc, item) => acc + item.adet, 0);
        const lastItem = state.cart.length > 0 ? state.cart[state.cart.length - 1].urun_adi : '';
        socket.emit('musteri_urun_secti', {
            masa_id: state.masaId,
            masa_no: state.masaNo,
            item_count: totalCount,
            last_item: lastItem
        });
    }
}

// EN ALTTA ÇAKIŞMAYAN SABİT SEPET BARI GÜNCELLEMESİ
function updateCartUI() {
    const totalCount = state.cart.reduce((acc, item) => acc + item.adet, 0);
    const totalPrice = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    const cartDock = document.getElementById('cartStickyDock');
    const cartCount = document.getElementById('cartDockItemCount');
    const cartPrice = document.getElementById('cartDockTotalPrice');

    if (cartCount) cartCount.innerText = `${totalCount} Adet Ürün Eklendi`;
    if (cartPrice) cartPrice.innerText = `${totalPrice.toFixed(2)} ₺`;

    if (cartDock) {
        cartDock.style.display = totalCount > 0 ? 'flex' : 'none';
    }

    // Sepet değiştiğinde ürün kartlarındaki mavi neon seçili parlama ve adet rozetini güncelle
    renderProducts();
}

window.changeModalQuantity = function (delta) {
    const input = document.getElementById('modalQuantity');
    if (!input) return;
    let current = parseInt(input.value) || 1;
    current += delta;
    if (current < 1) current = 1;
    if (current > 20) current = 20;
    input.value = current;
    updateModalCalculatedPrice();
};

window.updateCartItemQuantity = function (index, delta) {
    if (!state.cart[index]) return;
    
    // Eğer adet 1 ise ve azaltılmak isteniyorsa onay isteyelim
    if (state.cart[index].adet === 1 && delta === -1) {
        if (confirm("Bu ürünü sepetten kaldırmak istiyor musunuz?")) {
            state.cart.splice(index, 1);
        } else {
            return; // Adeti 1'de tut, silme işlemini iptal et
        }
    } else {
        state.cart[index].adet += delta;
        if (state.cart[index].adet <= 0) {
            state.cart.splice(index, 1);
        } else {
            state.cart[index].ara_toplam = state.cart[index].birim_fiyat * state.cart[index].adet;
        }
    }
    
    notifyCartUpdateToSocket();
    updateCartUI();
    openCartModal();
};

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
                <div class="order-item-row" style="padding: 10px 0; border-bottom: 1px dashed rgba(255,255,255,0.08);">
                    <div class="order-item-main" style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-weight:700; font-size:0.95rem;">${item.urun_adi}</div>
                        <div style="font-weight:800; color:#fbbf24;">${item.ara_toplam.toFixed(2)} ₺</div>
                    </div>
                    ${item.urun_notu ? `<div class="order-item-note" style="margin-top:2px;">Not: ${item.urun_notu}</div>` : ''}
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <button type="button" onclick="window.updateCartItemQuantity(${index}, -1)" style="width:36px; height:36px; font-weight:800; font-size:1.2rem; border-radius:var(--radius-sm); background:rgba(255,255,255,0.12); border:1px solid var(--border-color); color:#fff; cursor:pointer; user-select:none; touch-action:manipulation;">-</button>
                            <span style="font-weight:800; font-size:1.1rem; min-width:28px; text-align:center;">${item.adet}</span>
                            <button type="button" onclick="window.updateCartItemQuantity(${index}, 1)" style="width:36px; height:36px; font-weight:800; font-size:1.2rem; border-radius:var(--radius-sm); background:rgba(255,255,255,0.12); border:1px solid var(--border-color); color:#fff; cursor:pointer; user-select:none; touch-action:manipulation;">+</button>
                        </div>
                        <button style="background:none; border:none; color: var(--danger); font-size: 0.85rem; font-weight:700; cursor:pointer;" onclick="removeCartItem(${index})">🗑️ Sil</button>
                    </div>
                </div>
            `;
        });
        cartItemsContainer.innerHTML = html;
    }

    if (modalCartTotal) modalCartTotal.innerText = `${totalPrice.toFixed(2)} ₺`;
    document.getElementById('cartModal').classList.add('active');
}

function updateCartItemQuantity(index, delta) {
    if (!state.cart[index]) return;
    state.cart[index].adet += delta;
    if (state.cart[index].adet <= 0) {
        state.cart.splice(index, 1);
    } else {
        state.cart[index].ara_toplam = state.cart[index].birim_fiyat * state.cart[index].adet;
    }
    notifyCartUpdateToSocket();
    updateCartUI();
    openCartModal();
}

function removeCartItem(index) {
    state.cart.splice(index, 1);
    notifyCartUpdateToSocket();
    updateCartUI();
    openCartModal();
}

// ÖDEME ONAY VE KART SEÇİM / DEKONT EKRANI MODALİ
function openPaymentCheckout(method) {
    if (state.cart.length === 0) return;

    state.selectedPaymentMethod = method;
    closeModal('cartModal');

    const totalAmount = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    document.getElementById('checkoutTotalAmount').innerText = `${totalAmount.toFixed(2)} ₺`;

    let summaryHTML = '';
    state.cart.forEach(item => {
        summaryHTML += `
            <div style="display:flex; justify-content:space-between;">
                <span>${item.adet}x ${item.urun_adi}</span>
                <span style="font-weight:700;">${item.ara_toplam.toFixed(2)} ₺</span>
            </div>
            ${item.urun_notu ? `<div style="font-size:0.75rem; color:var(--text-secondary); padding-left:8px;">• ${item.urun_notu}</div>` : ''}
        `;
    });
    document.getElementById('checkoutSummaryList').innerHTML = summaryHTML;

    const cardSection = document.getElementById('cardSelectSection');
    const cashSection = document.getElementById('cashNoticeSection');
    const title = document.getElementById('checkoutModalTitle');
    const btnConfirm = document.getElementById('btnConfirmFinalPayment');

    if (method === 'pos') {
        if (title) title.innerText = '💳 Online Kart İle Hızlı Ödeme';
        if (cardSection) cardSection.style.display = 'block';
        if (cashSection) cashSection.style.display = 'none';
        if (btnConfirm) btnConfirm.innerText = '✅ Ödemeyi Yap ve Siparişi Anında Gönder';
    } else if (method === 'garson_kasada') {
        if (title) title.innerText = '🛎️ Garson Onaylı Sipariş (Kasada Öde)';
        if (cardSection) cardSection.style.display = 'none';
        if (cashSection) {
            cashSection.style.display = 'block';
            cashSection.innerHTML = `
                <div style="text-align:center; padding:12px; background:rgba(59,130,246,0.1); border:1px solid #3b82f6; border-radius:var(--radius-md);">
                    <div style="font-size:1.3rem; margin-bottom:4px;">🛎️</div>
                    <div style="font-weight:700; color:#3b82f6;">Garson Teyit Edecek</div>
                    <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:4px;">Garson masanıza gelip siparişi teyit ettikten sonra mutfağa aktarılacaktır. Ödemeyi yemeğin sonunda KASADA yapabilirsiniz.</div>
                </div>
            `;
        }
        if (btnConfirm) btnConfirm.innerText = '📩 Garson Onayı İle Siparişi Gönder';
    }

    document.getElementById('paymentCheckoutModal').classList.add('active');
}

async function confirmFinalOrder() {
    const actionBox = document.getElementById('checkoutActionBox');
    const originalHTML = actionBox.innerHTML;
    const method = state.selectedPaymentMethod;

    let text = '⏳ Ödemeniz İşleniyor...';
    if (method === 'garson_kasada') text = '⏳ Siparişiniz İletiliyor... Garson Masaya Yönlendiriliyor...';

    actionBox.innerHTML = `
        <div style="text-align:center; padding:14px; font-weight:800; color:var(--primary); font-size:1rem;">
            ${text}
        </div>
    `;

    setTimeout(async () => {
        await executeOrderSubmit(state.selectedPaymentMethod || 'pos');
        closeModal('paymentCheckoutModal');
        actionBox.innerHTML = originalHTML;
    }, 1200);
}

async function executeOrderSubmit(odemeYontemi) {
    const totalPrice = state.cart.reduce((acc, item) => acc + item.ara_toplam, 0);

    const payload = {
        masa_id: state.masaId,
        toplam_tutar: totalPrice,
        odeme_yontemi: odemeYontemi,
        device_id: state.deviceId,
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
                showToast("💳 Ödemeniz onaylandı ve siparişiniz alındı!");
            } else {
                showToast("🛎️ Siparişiniz iletildi! Garsonumuz masanıza geliyor.");
            }
        } else {
            alert(data.detail || "Hata oluştu.");
        }
    } catch (e) {
        alert("Sunucuya ulaşılamadı.");
    }
}

// CANLI SİPARİŞ TAKİP EKRANI (F5 İLE KANANMAZ + SİPARİŞ VERİLEN ÜRÜNLERİN LİSTESİ)
function renderOrderTrackingUI() {
    const container = document.getElementById('orderTrackingContainer');
    if (!container || !state.currentOrder) return;

    const status = state.currentOrder.siparis_durumu;

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

    if (status === 'garson_onayi_bekliyor') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-received" style="border-color: #3b82f6; background: rgba(59, 130, 246, 0.15);">
                <div class="status-icon-large">🛎️</div>
                <div class="status-info">
                    <div class="status-title-main" style="color:#3b82f6;">Garson Onayı Bekleniyor</div>
                    <div class="status-sub-desc">Garsonumuz siparişi fiziken teyit etmek üzere masanıza geliyor. Ödemeyi yemeğin sonunda KASADA yapabilirsiniz.</div>
                </div>
            </div>
        `;
    } else if (status === 'odendi_mutfakta' || status === 'garson_onayladi_mutfakta') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-received">
                <div class="status-icon-large">✅</div>
                <div class="status-info">
                    <div class="status-title-main">Siparişiniz Alındı</div>
                    <div class="status-sub-desc">Siparişiniz doğrulandı • Şeflerimiz siparişinizi hazırlamaya başladı! 👨‍🍳</div>
                </div>
            </div>
        `;
    } else if (status === 'hazirlaniyor') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-preparing">
                <div class="status-icon-large">👨‍🍳</div>
                <div class="status-info">
                    <div class="status-title-main">Mutfakta Hazırlanıyor</div>
                    <div class="status-sub-desc">Tahmini Hazırlanma Süresi: <strong style="color:#fbbf24;">~12 - 15 dk</strong></div>
                </div>
            </div>
        `;
    } else if (status === 'hazir') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-ready">
                <div class="status-icon-large">🔔</div>
                <div class="status-info">
                    <div class="status-title-main">Siparişiniz Hazır!</div>
                    <div class="status-sub-desc">Garson yemeğinizi masanıza getirmek üzere yola çıktı.</div>
                </div>
            </div>
        `;
    }

    // ÜRÜN DETAYLARI LİSTESİ
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

    const isPaid = state.currentOrder.odeme_durumu === 'odendi';
    const paymentBadge = isPaid
        ? `<span class="table-badge" style="background: var(--success); font-weight:800;">💳 Ödendi</span>`
        : `<span class="table-badge" style="background: #f59e0b; color:#fff; font-weight:800;">🟡 ÖDEME KASADA YAPILACAK</span>`;

    let html = `
        <div class="tracking-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
                <span style="font-size: 0.8rem; font-weight:800; color: var(--primary); letter-spacing: 0.5px;">🚀 CANLI SİPARİŞ DURUMU</span>
                <span class="table-badge">🪑 ${state.masaNo}</span>
            </div>
            
            ${currentStatusHTML}

            <!-- VERİLEN SİPARİŞİN İÇERİĞİ -->
            <div style="margin-top: 16px; background: rgba(0,0,0,0.25); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 8px;">
                    <span style="font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">📋 Sipariş Ettiğiniz Ürünler:</span>
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
    toast.className = 'toast-notification';
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3500);
}
