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
    selectedFreeDrink: null,
    selectedExtras: [],
    activeNotes: [],
    currentOrder: null,
    selectedPaymentMethod: 'pos',
    language: localStorage.getItem('qr_language') || null,
    deviceId: (function () {
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
    { id: 'medium', name: 'Orta Boy', detail: '26 cm • 1-2 Kişilik (🎁 Hediye İçecekli)', priceDiff: 40.00 },
    { id: 'large', name: 'Büyük Boy', detail: '32 cm • 2-3 Kişilik', priceDiff: 85.00 },
    { id: 'jumbo', name: 'En Büyük Boy', detail: '40 cm • 3-4 Kişilik (🎁 Hediye İçecekli)', priceDiff: 140.00 }
];

// ORTA BOY HEDİYE İÇECEK SEÇENEKLERİ (1L veya 2 Büyük Ayran)
const FREE_DRINKS_MEDIUM = [
    { id: 'm_cola', name: '1L Coca-Cola', detail: '1 Litre Şişe' },
    { id: 'm_fanta', name: '1L Fanta', detail: '1 Litre Şişe' },
    { id: 'm_sprite', name: '1L Sprite', detail: '1 Litre Şişe' },
    { id: 'm_ayran', name: '2x Büyük Ayran (330ml)', detail: '2 Adet 330ml Cam/Şişe' }
];

// EN BÜYÜK BOY HEDİYE İÇECEK SEÇENEKLERİ (1.5L veya 3 Büyük Ayran)
const FREE_DRINKS_JUMBO = [
    { id: 'j_cola', name: '1.5L Coca-Cola', detail: '1.5 Litre Şişe' },
    { id: 'j_fanta', name: '1.5L Fanta', detail: '1.5 Litre Şişe' },
    { id: 'j_sprite', name: '1.5L Sprite', detail: '1.5 Litre Şişe' },
    { id: 'j_ayran', name: '3x Büyük Ayran (330ml)', detail: '3 Adet 330ml Cam/Şişe' }
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

function showSecurityError(msg) {
    const errModal = document.getElementById('securityErrorModal');
    const errMsg = document.getElementById('securityErrorMessage');
    if (errMsg) errMsg.innerText = msg;
    if (errModal) errModal.classList.add('active');

    // Arka planı gizle ki tıklama yapamasınlar
    const mainLayout = document.querySelector('.menu-layout-container');
    const cartDock = document.getElementById('cartStickyDock');
    if (mainLayout) mainLayout.style.display = 'none';
    if (cartDock) cartDock.style.display = 'none';
}

function formatShortMasaNo(masaNo) {
    if (!masaNo) return 'M-1';
    let str = masaNo.trim();
    if (str.toLowerCase().includes('developer')) return 'DEV';

    const parts = str.split(/\s+/);
    if (parts.length >= 2) {
        const firstChar = parts[0].charAt(0).toUpperCase();
        const number = parts[parts.length - 1];
        if (/^\d+$/.test(number)) {
            return `${firstChar}-${number}`;
        }
    }
    if (str.toLowerCase().startsWith('masa ')) {
        return 'M-' + str.substring(5).trim();
    }
    return str;
}

document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    let masaParam = urlParams.get('masa') || '1';
    const tokenParam = urlParams.get('token');

    // 192.168.1.100:8000 ile bağlanan kullanıcılar masa 1 butonuna tıkladığında veya masa 1 açıldığında dev masası (99) açılsın
    if ((window.location.hostname === '192.168.1.100' || window.location.host === '192.168.1.100:8000') && masaParam === '1' && !tokenParam) {
        masaParam = '99';
    }

    state.masaId = parseInt(masaParam);
    state.masaNo = state.masaId === 99 ? 'Developer Masası' : `Masa ${state.masaId}`; // Fallback

    // --- DİNAMİK QR GÜVENLİK KONTROLÜ ---
    if (state.masaId !== 99) {
        if (!tokenParam) {
            showSecurityError("Geçersiz giriş! Lütfen masanızdaki QR kodu okutarak sisteme giriniz.");
            return;
        }

        try {
            const verifyRes = await fetch(`/api/masalar/${state.masaId}/verify-qr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: tokenParam, device_id: state.deviceId })
            });
            const verifyData = await verifyRes.json();
            if (!verifyData.valid) {
                showSecurityError(verifyData.message || "Süresi dolmuş QR kod! Lütfen masadaki ekranı yenileyip güncel kodu okutun.");
                return;
            }
        } catch (e) {
            showSecurityError("Güvenlik doğrulaması yapılamadı. Sunucuya ulaşılamıyor.");
            return;
        }
    }
    // --- GÜVENLİK KONTROLÜ SONU ---

    try {
        const mRes = await fetch('/api/masalar');
        const mData = await mRes.json();

        const gercekMasa = mData.find(m => m.id === state.masaId);
        if (gercekMasa) {
            state.masaNo = gercekMasa.masa_no;
        }
    } catch (e) { console.error(e); }

    const tableBadge = document.getElementById('tableBadge');
    if (tableBadge) {
        const shortNo = formatShortMasaNo(state.masaNo);
        tableBadge.innerHTML = `🪑 ${shortNo}`;
        tableBadge.title = state.masaNo;
    }

    // Dil seçimi yapılmamışsa aç
    if (!state.language) {
        document.getElementById('languageModal').classList.add('active');
    }

    loadCategories();
    loadProducts();
    checkActiveOrder(); // F5 RECOVERY: Sayfa yenilendiğinde aktif siparişi getirir!
    initCategoryScrollNavigation(); // Kategori otomatik kaydırma geçişi

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
        if (data && data.from_masa_id && parseInt(data.from_masa_id) === parseInt(state.masaId)) {
            handleTableMove(data.from_masa_id, data.to_masa_id, data.to_masa_no, data.from_masa_no);
            return;
        }
        if (data && data.is_move) return;
        if (data && data.masa_id === state.masaId) {
            if (data.yeni_durum === 'bos') {
                state.currentOrder = null;
                state.activeOrders = [];
                const container = document.getElementById('orderTrackingContainer');
                if (container) container.style.display = 'none';
            } else {
                checkActiveOrder();
                playNotificationSound();
            }
        }
    });

    socket.on('masa_temizlendi', (data) => {
        if (data && data.is_move) return;
        if (data && data.masa_id === state.masaId) {
            state.currentOrder = null;
            state.activeOrders = [];
            state.cart = [];
            updateCartUI();
            const container = document.getElementById('orderTrackingContainer');
            if (container) container.style.display = 'none';
            showToast("ℹ️ Masa hesabı kapatıldı ve oturum sıfırlandı.");
        }
    });

    socket.on('masa_durumu_degisti', (data) => {
        if (data && data.is_move) return;
        if (data && data.masa_id === state.masaId && data.durum === 'bos') {
            state.currentOrder = null;
            state.activeOrders = [];
            state.cart = [];
            updateCartUI();
            const container = document.getElementById('orderTrackingContainer');
            if (container) container.style.display = 'none';
        }
    });

    socket.on('nakit_odendi', (data) => {
        if (data && data.masa_id === state.masaId) {
            checkActiveOrder();
            playNotificationSound();
            showToast("💵 Garson nakit ödemenizi tahsil etti. Teşekkürler!");
        }
    });

    socket.on('yeni_siparis', (data) => {
        if (data && data.masa_id === state.masaId) {
            checkActiveOrder();
            playNotificationSound();
        }
    });

    socket.on('masa_tasindi', (data) => {
        if (data && parseInt(data.from_masa_id) === parseInt(state.masaId)) {
            handleTableMove(data.from_masa_id, data.to_masa_id, data.to_masa_no, data.from_masa_no);
        }
    });

    // Otomatik Masa Taşıma Kontrolü (Socket harici 3 saniyelik periyodik canlı kontrol)
    setInterval(() => {
        if (state.masaId) {
            checkActiveOrder();
        }
    }, 3000);

    // Sekme/Ekran tekrar aktif olduğunda kontrol et
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && state.masaId) {
            checkActiveOrder();
        }
    });
});

window.handleTableMove = function (fromMasaId, toMasaId, toMasaNo, fromMasaNo) {
    if (!toMasaId) return;

    const isAlreadyOnNewTable = parseInt(toMasaId) === parseInt(state.masaId);
    const modalIsActive = document.getElementById('tableTransferModal')?.classList.contains('active');

    if (isAlreadyOnNewTable && modalIsActive) {
        return;
    }

    const oldMasaNo = fromMasaNo || state.masaNo || `Masa ${fromMasaId}`;
    state.masaId = parseInt(toMasaId);
    state.masaNo = toMasaNo || `Masa ${toMasaId}`;

    const url = new URL(window.location.href);
    url.searchParams.set('masa', state.masaId);
    window.history.replaceState({}, '', url);

    if (socket && socket.connected) {
        socket.emit('musteri_oturdu', { masa_id: state.masaId, masa_no: state.masaNo });
    }

    const masaBadge = document.getElementById('tableBadge');
    if (masaBadge) {
        const shortNo = formatShortMasaNo(state.masaNo);
        masaBadge.innerHTML = `🪑 ${shortNo}`;
        masaBadge.title = state.masaNo;
        masaBadge.classList.remove('badge-pulse');
        void masaBadge.offsetWidth;
        masaBadge.classList.add('badge-pulse');
    }

    const fromBadgeEl = document.getElementById('transferFromBadge');
    const toBadgeEl = document.getElementById('transferToBadge');
    const transferModal = document.getElementById('tableTransferModal');
    if (fromBadgeEl) fromBadgeEl.innerText = formatShortMasaNo(oldMasaNo);
    if (toBadgeEl) toBadgeEl.innerText = formatShortMasaNo(state.masaNo);
    if (transferModal) transferModal.classList.add('active');

    playNotificationSound();
    showToast(`🔄 Adisyonunuz ve oturumunuz ${state.masaNo} masasına taşındı.`);
};

// AKICI VE KESİNTİSİZ NATIVE KATEGORİ KAYDIRMA SİSTEMİ (INTERSECTION OBSERVER)
let categoryObserver = null;

function initCategoryIntersectionObserver() {
    const section = document.querySelector('.menu-products-section');
    if (!section) return;

    if (categoryObserver) {
        categoryObserver.disconnect();
    }

    const options = {
        root: section,
        rootMargin: '-10% 0px -65% 0px',
        threshold: 0
    };

    categoryObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const catIdAttr = entry.target.getAttribute('data-cat-id');
                const catId = (catIdAttr && catIdAttr !== 'other') ? parseInt(catIdAttr) : null;
                if (state.activeKategoriId !== catId) {
                    state.activeKategoriId = catId;
                    updateSidebarActiveStateOnly();
                }
            }
        });
    }, options);

    const sections = section.querySelectorAll('.category-section');
    sections.forEach(s => categoryObserver.observe(s));
}

function updateSidebarActiveStateOnly() {
    const container = document.getElementById('categoryGridBar');
    if (!container) return;

    const cards = container.querySelectorAll('.category-card-box');
    cards.forEach(card => {
        const onclickAttr = card.getAttribute('onclick') || '';
        if (state.activeKategoriId !== null && onclickAttr.includes(`selectCategory(${state.activeKategoriId})`)) {
            card.classList.add('active');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            card.classList.remove('active');
        }
    });

    updateCategoryHeaderTitle(state.activeKategoriId);
}

function selectCategory(catId) {
    if (!catId) return;
    state.activeKategoriId = catId;
    updateSidebarActiveStateOnly();

    const targetSec = document.getElementById(`cat-section-${catId}`);
    if (targetSec) {
        targetSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function updateCategoryHeaderTitle(catId) {
    const titleEl = document.getElementById('activeCategoryTitle');
    if (!titleEl) return;
    const cat = state.kategoriler.find(c => c.id === catId);
    if (cat) {
        titleEl.innerText = cat.kategori_adi;
    } else if (state.kategoriler.length > 0) {
        titleEl.innerText = state.kategoriler[0].kategori_adi;
    }
}

let isTrackingCollapsed = false;

function toggleTrackingUI() {
    isTrackingCollapsed = !isTrackingCollapsed;
    renderOrderTrackingUI();
}

// SAYFA YENİLENDİĞİNDE VEYA SEKME DEĞİŞTİĞİNDE MÜŞTERİNİN TÜM AKTİF SİPARİŞLERİNİ GETİREN FONKSİYON
async function checkActiveOrder() {
    try {
        const res = await fetch(`/api/masalar/${state.masaId}/aktif-siparis`);
        const data = await res.json();

        if (data.redirect_masa_id && parseInt(data.redirect_masa_id) !== parseInt(state.masaId)) {
            const fromId = state.masaId;
            const toId = parseInt(data.redirect_masa_id);
            const toNo = data.redirect_masa_no || `Masa ${toId}`;
            handleTableMove(fromId, toId, toNo);
            return;
        }

        if (data.has_active && (data.siparisler && data.siparisler.length > 0 || data.siparis)) {
            state.activeOrders = data.siparisler || [data.siparis];
            state.currentOrder = data.siparis || state.activeOrders[state.activeOrders.length - 1];
            state.genelToplam = data.genel_toplam || state.activeOrders.reduce((sum, o) => sum + (o.toplam_tutar || 0), 0);
            renderOrderTrackingUI();
        } else {
            state.activeOrders = [];
            state.currentOrder = null;
            state.genelToplam = 0;
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
        if (state.kategoriler.length > 0 && !state.activeKategoriId) {
            state.activeKategoriId = state.kategoriler[0].id;
        }
        renderCategoryGrid();
    } catch (e) {
        console.error("Kategoriler yüklenemedi:", e);
    }
}

async function loadProducts() {
    try {
        const res = await fetch('/api/urunler');
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

    if (state.kategoriler.length > 0 && !state.activeKategoriId) {
        state.activeKategoriId = state.kategoriler[0].id;
    }

    let html = '';

    state.kategoriler.forEach(cat => {
        const icon = getCategoryIcon(cat.kategori_adi);
        const isActive = state.activeKategoriId === cat.id;
        const hasImg = cat.gorsel_url && cat.gorsel_url.trim().length > 0;
        html += `
            <div class="category-card-box ${isActive ? 'active' : ''}" onclick="selectCategory(${cat.id})">
                ${hasImg
                ? `<img src="${cat.gorsel_url}" class="category-card-img" alt="${cat.kategori_adi}" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-block';"><span class="category-card-icon" style="display:none;">${icon}</span>`
                : `<span class="category-card-icon">${icon}</span>`
            }
                <span class="category-card-title">${cat.kategori_adi}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

// ÜRÜN KARTLARI (KESİNTİSİZ TEK LİSTE, STICKY KATEGORİ BAŞLIKLI)
function renderProducts() {
    const grid = document.getElementById('productGrid');
    if (!grid) return;

    if (state.urunler.length === 0) {
        grid.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 40px; background: rgba(255,255,255,0.02); border-radius: 16px; border: 1px dashed var(--border-color);">Bu kategoride henüz ürün bulunmuyor.</div>`;
        return;
    }

    // Kategorilere göre ürünleri grupla
    const grouped = {};
    state.kategoriler.forEach(cat => {
        grouped[cat.id] = {
            category: cat,
            products: []
        };
    });

    const uncategorized = [];

    state.urunler.forEach(prod => {
        if (prod.kategori_id && grouped[prod.kategori_id]) {
            grouped[prod.kategori_id].products.push(prod);
        } else {
            uncategorized.push(prod);
        }
    });

    let html = '';

    state.kategoriler.forEach(cat => {
        const group = grouped[cat.id];
        if (!group || group.products.length === 0) return;

        const icon = getCategoryIcon(cat.kategori_adi);
        html += `
            <div class="category-section" id="cat-section-${cat.id}" data-cat-id="${cat.id}">
                <div class="category-section-title">
                    <h2>${icon} ${cat.kategori_adi}</h2>
                </div>
                <div class="category-products-list">
        `;

        group.products.forEach(prod => {
            html += renderProductCardHTML(prod);
        });

        html += `
                </div>
            </div>
        `;
    });

    if (uncategorized.length > 0) {
        html += `
            <div class="category-section" id="cat-section-other" data-cat-id="other">
                <div class="category-section-title">
                    <h2>🍴 Diğer Ürünler</h2>
                </div>
                <div class="category-products-list">
        `;
        uncategorized.forEach(prod => {
            html += renderProductCardHTML(prod);
        });
        html += `
                </div>
            </div>
        `;
    }

    grid.innerHTML = html;
    initCategoryIntersectionObserver();
}

function renderProductCardHTML(prod) {
    const catName = prod.kategori_adi ? prod.kategori_adi : '';
    const icon = getCategoryIcon(catName);
    const hasImage = prod.gorsel_url && prod.gorsel_url.trim().length > 0;

    const cartItems = state.cart.filter(item => item.urun_id === prod.id);
    const inCartQty = cartItems.reduce((sum, item) => sum + item.adet, 0);
    const isSelected = inCartQty > 0;

    return `
        <div class="product-card ${isSelected ? 'selected' : ''}" onclick="openProductNoteModal(${prod.id})">
            <div class="product-card-image-box">
                ${hasImage
            ? `<img src="${prod.gorsel_url}" alt="${prod.urun_adi}" class="product-card-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                       <div class="product-card-placeholder" style="display:none;"><span>${icon}</span></div>`
            : `<div class="product-card-placeholder"><span>${icon}</span></div>`
        }
            </div>

            <div class="product-card-content">
                <div class="product-title-row">
                    <div class="product-title" title="${prod.urun_adi}">${prod.urun_adi}</div>
                </div>

                <div class="product-bottom-row">
                    <div class="product-price-badge">${prod.fiyat.toFixed(0)} ₺</div>
                    <div class="product-actions-right">
                        ${isSelected ? `
                            <div class="quantity-counter-box" onclick="event.stopPropagation();">
                                <button class="btn-qty-step" title="Adet Azalt" onclick="quickAddToCart(event, ${prod.id}, -1)"><span>-</span></button>
                                <span class="product-cart-qty-badge">${inCartQty}</span>
                                <button class="btn-qty-step" title="Adet Artır" onclick="quickAddToCart(event, ${prod.id}, 1)"><span>+</span></button>
                            </div>
                        ` : `
                            <button class="btn-add-circle" title="Sepete Ekle" onclick="quickAddToCart(event, ${prod.id}, 1)">
                                <span>+</span>
                            </button>
                        `}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function quickAddToCart(event, productId, delta = 1) {
    if (event) event.stopPropagation();

    const prod = state.urunler.find(p => p.id === productId);
    if (!prod) return;

    const catName = (prod.kategori_adi || '').toLowerCase();
    const prodName = (prod.urun_adi || '').toLowerCase();
    const isPizza = prodName.includes('pizza') || catName.includes('pizza');

    const cartItems = state.cart.filter(item => item.urun_id === productId);

    if (delta > 0) {
        if (cartItems.length > 0) {
            const lastItem = cartItems[cartItems.length - 1];
            lastItem.adet += 1;
            lastItem.ara_toplam = lastItem.birim_fiyat * lastItem.adet;
            notifyCartUpdateToSocket();
            updateCartUI();
            playNotificationSound();
        } else if (isPizza) {
            openProductNoteModal(productId);
        } else {
            state.cart.push({
                id: Date.now(),
                urun_id: prod.id,
                urun_adi: prod.urun_adi,
                birim_fiyat: prod.fiyat,
                adet: 1,
                urun_notu: '',
                ara_toplam: prod.fiyat
            });
            notifyCartUpdateToSocket();
            updateCartUI();
            playNotificationSound();
        }
    } else if (delta < 0) {
        if (cartItems.length > 0) {
            const lastItem = cartItems[cartItems.length - 1];
            lastItem.adet -= 1;
            if (lastItem.adet <= 0) {
                const idx = state.cart.findIndex(i => i.id === lastItem.id);
                if (idx > -1) state.cart.splice(idx, 1);
            } else {
                lastItem.ara_toplam = lastItem.birim_fiyat * lastItem.adet;
            }
            notifyCartUpdateToSocket();
            updateCartUI();
        }
    }
}
window.quickAddToCart = quickAddToCart;

// ÜRÜN MODALİ
function openProductNoteModal(productId) {
    const prod = state.urunler.find(p => p.id === productId);
    if (!prod) return;

    state.currentProduct = prod;
    state.selectedSize = PIZZA_SIZES[0];
    state.selectedFreeDrink = null;
    state.selectedPortion = PORTION_OPTIONS[0];
    state.selectedExtras = [];
    state.activeNotes = [];

    document.getElementById('modalProductTitle').innerText = prod.urun_adi;

    // Açıklama alanı
    const descEl = document.getElementById('modalProductDesc');
    if (prod.aciklama) {
        descEl.innerText = prod.aciklama;
        descEl.style.display = 'block';
    } else {
        descEl.style.display = 'none';
    }

    // Görsel Alanı
    const imgEl = document.getElementById('modalProductImage');
    if (prod.gorsel_url) {
        imgEl.src = prod.gorsel_url;
        imgEl.style.display = 'block';
    } else {
        imgEl.style.display = 'none';
    }

    document.getElementById('modalProductNote').value = '';
    document.getElementById('modalQuantity').value = '1';

    const catName = (prod.kategori_adi || '').toLowerCase();
    const prodName = (prod.urun_adi || '').toLowerCase();

    const isPizza = prodName.includes('pizza') || catName.includes('pizza');
    const isDish = catName.includes('ana yemek') || catName.includes('izgara') || catName.includes('kebap') || catName.includes('yemek') || prodName.includes('kofte') || prodName.includes('köfte') || prodName.includes('döner') || prodName.includes('doner') || prodName.includes('tavuk') || prodName.includes('et') || prodName.includes('izgara');

    // Pizza Boyutları mi yoksa Yemek Porsiyonları mı?
    const pizzaSection = document.getElementById('pizzaSizeSection');
    const freeDrinkSection = document.getElementById('pizzaFreeDrinkSection');
    const portionSection = document.getElementById('portionSizeSection');

    if (freeDrinkSection) freeDrinkSection.style.display = 'none';

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

    const freeDrinkSection = document.getElementById('pizzaFreeDrinkSection');
    if (freeDrinkSection) {
        if (sizeId === 'medium' || sizeId === 'jumbo') {
            freeDrinkSection.style.display = 'block';
            const list = sizeId === 'medium' ? FREE_DRINKS_MEDIUM : FREE_DRINKS_JUMBO;
            if (!state.selectedFreeDrink || !list.some(d => d.id === state.selectedFreeDrink.id)) {
                state.selectedFreeDrink = list[0];
            }
            renderFreeDrinks(list, sizeId === 'medium' ? '🎁 Orta Boy Hediyesi (Ücretsiz İçecek Seçiniz)' : '🎁 En Büyük Boy Hediyesi (Ücretsiz İçecek Seçiniz)');
        } else {
            freeDrinkSection.style.display = 'none';
            state.selectedFreeDrink = null;
        }
    }

    updateModalCalculatedPrice();
}

function renderFreeDrinks(list, titleText) {
    const titleEl = document.getElementById('freeDrinkTitle');
    const container = document.getElementById('pizzaFreeDrinkGrid');
    if (titleEl) titleEl.innerText = titleText;
    if (!container) return;

    let html = '';
    list.forEach(drink => {
        const isSelected = state.selectedFreeDrink && state.selectedFreeDrink.id === drink.id;
        html += `
            <div class="size-option-card ${isSelected ? 'active' : ''}" onclick="selectFreeDrink('${drink.id}', '${drink.name.replace(/'/g, "\\'")}', '${drink.detail.replace(/'/g, "\\'")}')">
                <div class="size-name">${drink.name}</div>
                <div class="size-detail">${drink.detail}</div>
                <div class="size-price-diff" style="color: #10b981; font-weight:800;">ÜCRETSİZ</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function selectFreeDrink(id, name, detail) {
    state.selectedFreeDrink = { id, name, detail };
    const list = state.selectedSize.id === 'medium' ? FREE_DRINKS_MEDIUM : FREE_DRINKS_JUMBO;
    const title = state.selectedSize.id === 'medium' ? '🎁 Orta Boy Hediyesi (Ücretsiz İçecek Seçiniz)' : '🎁 En Büyük Boy Hediyesi (Ücretsiz İçecek Seçiniz)';
    renderFreeDrinks(list, title);
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

    if (catName === 'içecekler' || catName === 'icecekler') {
        chipsData = CUSTOM_CHIPS_MAP['icecek'];
    } else if (catName === 'pizzalar' || catName === 'pizza') {
        chipsData = CUSTOM_CHIPS_MAP['pizza'];
    } else if (catName === 'tatlılar' || catName === 'tatlilar') {
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
        if (state.selectedFreeDrink) {
            combinedNotes.push(`🎁 Hediye: ${state.selectedFreeDrink.name}`);
        }
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
        const isShowing = totalCount > 0;
        cartDock.style.display = isShowing ? 'flex' : 'none';

        if (isShowing) {
            cartDock.classList.remove('cart-dock-pop');
            void cartDock.offsetWidth; // Reflow tetikle
            cartDock.classList.add('cart-dock-pop');
        }
    }

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

    if (state.currentTotpToken) {
        payload.current_totp_token = state.currentTotpToken;
    }

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
            state.currentTotpToken = null; // Başarılı olunca temizle
            updateCartUI();

            await checkActiveOrder();
            playNotificationSound();

            if (odemeYontemi === 'pos') {
                showToast("💳 Ödemeniz onaylandı ve siparişiniz alındı!");
            } else {
                showToast("🛎️ Siparişiniz iletildi! Garsonumuz masanıza geliyor.");
            }
        } else if (res.status === 403 && data.detail && data.detail.includes("6 haneli")) {
            // İlk sipariş güvenlik onayı gerekiyor!
            openFirstOrderPINModal(odemeYontemi);
        } else {
            alert(data.detail || "Hata oluştu.");
        }
    } catch (e) {
        alert("Sunucuya ulaşılamadı.");
    }
}

// ==========================================
// İLK SİPARİŞ 6 HANELİ GÜVENLİK KODU (PIN)
// ==========================================
let pendingPaymentMethod = null;

function openFirstOrderPINModal(odemeYontemi) {
    pendingPaymentMethod = odemeYontemi;
    const modal = document.getElementById('firstOrderPINModal');
    if (modal) modal.classList.add('active');
    
    const input = document.getElementById('securityPinInput');
    if (input) {
        input.value = '';
        input.focus();
    }
}

function closeFirstOrderPINModal() {
    const modal = document.getElementById('firstOrderPINModal');
    if (modal) modal.classList.remove('active');
}

function submitFirstOrderPIN() {
    const input = document.getElementById('securityPinInput');
    if (!input || !input.value || input.value.length < 6) {
        alert("Lütfen 6 haneli güvenlik kodunu eksiksiz girin.");
        return;
    }
    
    state.currentTotpToken = input.value.trim();
    closeFirstOrderPINModal();
    
    // Modal kapanınca siparişi otomatik tekrar dene
    const actionBox = document.getElementById('checkoutActionBox');
    if (actionBox) {
        const originalHTML = actionBox.innerHTML;
        actionBox.innerHTML = `<div style="text-align:center; padding:14px; font-weight:800; color:var(--primary); font-size:1rem;">⏳ Güvenlik Sağlandı, Sipariş Gönderiliyor...</div>`;
        setTimeout(() => {
            executeOrderSubmit(pendingPaymentMethod).then(() => {
                closeModal('paymentCheckoutModal');
                actionBox.innerHTML = originalHTML;
            });
        }, 800);
    } else {
        executeOrderSubmit(pendingPaymentMethod);
    }
}

function formatOrderTime(val) {
    if (!val) return '';
    if (typeof val === 'string') {
        const trimmed = val.trim();
        if (trimmed.length <= 8 && trimmed.includes(':')) {
            const parts = trimmed.split(':');
            return `${parts[0]}:${parts[1]}`;
        }
        const d = new Date(trimmed.replace(' ', 'T'));
        if (!isNaN(d.getTime())) {
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return trimmed;
    }
    return '';
}

let expandedGroupDetailsMap = {};
window.toggleGroupDetails = function (key) {
    expandedGroupDetailsMap[key] = !expandedGroupDetailsMap[key];
    renderOrderTrackingUI();
};

// CANLI SİPARİŞ TAKİP EKRANI (F5 İLE KANANMAZ + SİPARİŞ VERİLEN ÜRÜNLERİN LİSTESİ)
function renderOrderTrackingUI() {
    const container = document.getElementById('orderTrackingContainer');
    if (!container) return;

    const orders = state.activeOrders && state.activeOrders.length > 0 ? state.activeOrders : (state.currentOrder ? [state.currentOrder] : []);
    if (orders.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    const latestOrder = orders[orders.length - 1];
    const status = latestOrder.siparis_durumu;
    const totalAdisyon = state.genelToplam || orders.reduce((acc, o) => acc + (o.toplam_tutar || 0), 0);

    const chevronDownSVG = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle;"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
    const chevronUpSVG = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle;"><polyline points="18 15 12 9 6 15"></polyline></svg>`;

    // KAPANABİLİR / AÇILABİLİR KART KONTROLÜ (KAPALI HALDE)
    if (isTrackingCollapsed) {
        container.innerHTML = `
            <div class="tracking-card" style="padding: 10px 14px; cursor: pointer; border-radius: 14px;" onclick="toggleTrackingUI()">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap: 8px;">
                        <span style="font-size: 1.1rem;">📋</span>
                        <span style="font-size: 0.92rem; font-weight: 700; color: var(--text-primary);">
                            Adisyon (${orders.length} Sipariş • ${totalAdisyon.toFixed(2)} ₺)
                        </span>
                    </div>
                    <span>${chevronDownSVG}</span>
                </div>
            </div>
        `;
        return;
    }

    // TEK BİR NET DURUM BAŞLIĞI
    let currentStatusHTML = '';

    if (status === 'garson_onayi_bekliyor') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-received" style="border-color: #3b82f6; background: rgba(59, 130, 246, 0.15); padding: 10px 14px; align-items: center; border-radius: 12px;">
                <div class="status-icon-large" style="font-size: 1.4rem;">🛎️</div>
                <div class="status-info">
                    <div class="status-title-main" style="color:#3b82f6; font-size: 1.05rem; font-weight: 700;">Garson Onayı Bekleniyor</div>
                </div>
            </div>
        `;
    } else if (status === 'odendi_mutfakta' || status === 'garson_onayladi_mutfakta') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-received" style="padding: 10px 14px; align-items: center; border-radius: 12px;">
                <div class="status-icon-large" style="font-size: 1.4rem;">✅</div>
                <div class="status-info">
                    <div class="status-title-main" style="font-size: 1.05rem; font-weight: 700;">Siparişiniz Alındı</div>
                </div>
            </div>
        `;
    } else if (status === 'hazirlaniyor') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-preparing" style="padding: 10px 14px; align-items: center; border-radius: 12px;">
                <div class="status-icon-large" style="font-size: 1.4rem;">👨‍🍳</div>
                <div class="status-info">
                    <div class="status-title-main" style="font-size: 1.05rem; font-weight: 700;">Mutfakta Hazırlanıyor</div>
                </div>
            </div>
        `;
    } else if (status === 'hazir') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-ready" style="padding: 10px 14px; align-items: center; border-radius: 12px;">
                <div class="status-icon-large" style="font-size: 1.4rem;">🔔</div>
                <div class="status-info">
                    <div class="status-title-main" style="font-size: 1.05rem; font-weight: 700;">Siparişiniz Hazır!</div>
                </div>
            </div>
        `;
    } else if (status === 'teslim_edildi') {
        currentStatusHTML = `
            <div class="single-status-banner active-step-ready" style="border-color: var(--success); background: rgba(16, 185, 129, 0.15); padding: 10px 14px; align-items: center; border-radius: 12px;">
                <div class="status-icon-large" style="font-size: 1.4rem;">🎉</div>
                <div class="status-info">
                    <div class="status-title-main" style="color: var(--success); font-size: 1.05rem; font-weight: 700;">Masanıza Teslim Edildi</div>
                </div>
            </div>
        `;
    }

    // MASANIN TÜM ÜRÜNLERİNİ GRUPLAMA (Option 1 - Grouped Adisyon)
    const groupedItemsMap = {};

    orders.forEach((ord, index) => {
        const orderTime = formatOrderTime(ord.olusturma_tarihi);
        const isPaid = ord.odeme_durumu === 'odendi';
        const detaylar = ord.detaylar || [];

        detaylar.forEach(item => {
            const key = item.urun_adi + '_' + (item.urun_notu || '');
            if (!groupedItemsMap[key]) {
                groupedItemsMap[key] = {
                    urun_adi: item.urun_adi,
                    total_adet: 0,
                    birim_fiyat: item.birim_fiyat,
                    total_tutar: 0,
                    urun_notu: item.urun_notu || '',
                    sublines: []
                };
            }
            const group = groupedItemsMap[key];
            group.total_adet += item.adet;
            group.total_tutar += (item.ara_toplam || (item.adet * item.birim_fiyat));
            group.sublines.push({
                orderIndex: index + 1,
                orderTime: orderTime,
                adet: item.adet,
                tutar: (item.ara_toplam || (item.adet * item.birim_fiyat)),
                isPaid: isPaid
            });
        });
    });

    let ordersListHTML = '';
    const groupKeys = Object.keys(groupedItemsMap);

    groupKeys.forEach((key, idx) => {
        const group = groupedItemsMap[key];
        const isExpanded = expandedGroupDetailsMap[key] || false;

        let sublinesHTML = '';
        group.sublines.forEach(sub => {
            sublinesHTML += `
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; padding: 3px 0; color:#cbd5e1; border-bottom: 1px dashed rgba(255,255,255,0.06);">
                    <span>Sipariş ${sub.orderIndex} ${sub.orderTime ? `• ${sub.orderTime}` : ''} (${sub.adet}x)</span>
                    <span>${sub.isPaid ? '<span style="color:#10b981; font-weight:700;">🟢 Ödendi</span>' : '<span style="color:#f59e0b; font-weight:700;">🟡 Kasada Ödenecek</span>'} • ${sub.tutar.toFixed(2)} ₺</span>
                </div>
            `;
        });

        ordersListHTML += `
            <div style="padding: 8px 0; ${idx > 0 ? 'border-top: 1px dashed rgba(255,255,255,0.1);' : ''}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-weight: 800; font-size: 0.95rem; color: #fff;">${group.total_adet}x ${group.urun_adi}</span>
                        ${group.urun_notu ? `<div style="font-size:0.75rem; color:#94a3b8;">Not: ${group.urun_notu}</div>` : ''}
                    </div>
                    <div style="display:flex; align-items:center; gap: 8px;">
                        <span style="font-weight: 800; font-size: 0.95rem; color: #fbbf24;">${group.total_tutar.toFixed(2)} ₺</span>
                        <button type="button" onclick="toggleGroupDetails('${key}')" style="background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.4); color: #a5b4fc; border-radius: 6px; padding: 2px 6px; font-size: 0.7rem; font-weight: 700; cursor: pointer;">
                            ${isExpanded ? '▲ Gizle' : '🔍 Ayrıntılar'}
                        </button>
                    </div>
                </div>

                <div id="groupDetails_${key}" style="display: ${isExpanded ? 'block' : 'none'}; margin-top: 6px; background: rgba(0,0,0,0.3); border-radius: 8px; padding: 6px 10px;">
                    ${sublinesHTML}
                </div>
            </div>
        `;
    });

    let html = `
        <div class="tracking-card" style="padding-bottom: 8px;">
            ${currentStatusHTML}

            <!-- MASANIN TÜM ADİSYON DÖKÜMÜ -->
            <div style="margin-top: 12px; background: rgba(0,0,0,0.25); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 12px;">
                <div class="tracking-scroll-list" style="max-height: 230px;">
                    ${ordersListHTML}
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.12); padding-top: 10px; font-weight: 800;">
                    <span style="font-size: 0.95rem;">Genel Adisyon Toplamı:</span>
                    <span style="color: #10b981; font-size: 1.15rem;">${totalAdisyon.toFixed(2)} ₺</span>
                </div>
            </div>

            <!-- KUTUCUKLARIN SAĞ ALTTAKİ KAPANIR OK BUTONU -->
            <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 6px; cursor: pointer;" onclick="toggleTrackingUI()">
                <span style="font-size: 0.78rem; color: #94a3b8; font-weight: 700;">💡 Adisyonu küçültmek için tıklayın</span>
                <span style="padding: 4px;" title="Adisyonu Gizle">
                    ${chevronUpSVG}
                </span>
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
