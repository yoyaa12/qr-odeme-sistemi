/**
 * "Benim Siparişlerim" görünümü.
 *
 * Masadaki her telefon bugüne kadar masanın tamamını görüyordu. Ayrım artık
 * mümkün, çünkü sunucu her siparişi doğrulanmış müşteri oturumuna göre
 * `is_mine` ile işaretliyor (`Siparisler.customer_session_id`).
 *
 * Bu testler render fonksiyonunu sahte DOM ile gerçekten çalıştırır: hangi
 * siparişin listelendiği ve hangi toplamın yazıldığı ölçülür.
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const repositoryRoot = path.resolve(__dirname, '..', '..');

function read(relativePath) {
    return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8');
}

const appSource = read('static/js/app.js');

function extractBlock(source, signature, terminator = '\n}') {
    const start = source.indexOf(signature);
    assert.ok(start !== -1, `kaynakta bulunamadı: ${signature}`);
    const end = source.indexOf(terminator, start);
    assert.ok(end !== -1, `kapanış bulunamadı: ${signature}`);
    return source.slice(start, end + terminator.length);
}

function order(id, tutar, isMine, urunAdi) {
    return {
        id,
        toplam_tutar: tutar,
        odeme_durumu: 'bekliyor',
        siparis_durumu: 'garson_onayi_bekliyor',
        olusturma_tarihi: '12:00:00',
        is_mine: isMine,
        detaylar: [
            { urun_adi: urunAdi, adet: 1, birim_fiyat: tutar, ara_toplam: tutar, urun_notu: '' }
        ]
    };
}

/**
 * `renderOrderTrackingUI` fonksiyonunu sahte DOM ile çalıştırır ve ürettiği
 * HTML'i döner.
 */
function renderTracking({ orders, genelToplam, benimToplamim, mode = 'table' }) {
    // `applyTrackingHTML` kaydırma konumunu korumak için `.tracking-scroll-list`
    // arıyor; sahte DOM'da böyle bir düğüm yok.
    const container = { style: {}, innerHTML: '', querySelector: () => null };
    const store = {};

    const sandbox = {
        state: {
            activeOrders: orders,
            currentOrder: orders.length ? orders[orders.length - 1] : null,
            genelToplam,
            benimToplamim
        },
        isTrackingCollapsed: false,
        // `applyTrackingHTML` bunu okur ve yazar; app.js'te modül düzeyinde
        // tanımlı olduğu için sandbox'a ayrıca verilmesi gerekiyor.
        lastTrackingHTML: '',
        expandedGroupDetailsMap: {},
        renderedGroupKeys: [],
        escapeHtml: value => String(value),
        formatOrderTime: value => value || '',
        localStorage: {
            getItem: key => (key in store ? store[key] : null),
            setItem: (key, value) => { store[key] = value; }
        },
        document: {
            getElementById: id => (id === 'orderTrackingContainer' ? container : null)
        },
        window: {},
        console: { error() { } }
    };

    const code = [
        // IIFE'nin kapanisi sutun 0'da '}' ile basladigi icin varsayilan
        // sonlandirici blogu yarida keserdi.
        extractBlock(appSource, '// "Benim Siparişlerim" / "Masanın Tümü" görünümü.', '\n})();'),
        extractBlock(appSource, 'window.setOrderViewMode = function (mode) {', '\n};'),
        extractBlock(appSource, 'function applyTrackingHTML(container, html) {'),
        extractBlock(appSource, 'function renderOrderTrackingUI() {')
    ].join('\n');

    vm.createContext(sandbox);
    new vm.Script(code).runInContext(sandbox);

    if (mode === 'mine') {
        sandbox.window.setOrderViewMode('mine');
    } else {
        sandbox.renderOrderTrackingUI();
    }

    return { html: container.innerHTML, container, sandbox, store };
}

const THREE_ORDERS = [
    order(1, 100, true, 'Yayla Çorbası'),
    order(2, 250, false, 'Karışık Pizza'),
    order(3, 50, true, 'Ayran')
];

// ---------------------------------------------------------------------------
// Filtreleme
// ---------------------------------------------------------------------------

test('the table view lists every order at the table', () => {
    const { html } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'table'
    });

    assert.match(html, /Yayla Çorbası/);
    assert.match(html, /Karışık Pizza/);
    assert.match(html, /Ayran/);
});

test('the personal view hides the orders placed from other devices', () => {
    const { html } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'mine'
    });

    assert.match(html, /Yayla Çorbası/);
    assert.match(html, /Ayran/);
    assert.ok(!/Karışık Pizza/.test(html), 'başkasının siparişi listelenmemeli');
});

test('the bill total stays the whole table in both views', () => {
    // Kişisel görünümde toplamı da filtrelemek, hesap geldiğinde sürprize yol
    // açar ve kasadaki rakamla uyuşmaz.
    const table = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'table'
    });
    const mine = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'mine'
    });

    assert.match(table.html, /Genel Adisyon Toplamı:[\s\S]{0,200}400 ₺/);
    assert.match(mine.html, /Genel Adisyon Toplamı:[\s\S]{0,200}400 ₺/);
});

test('the personal subtotal is shown separately', () => {
    const { html } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'mine'
    });

    assert.match(html, /Bu cihazdan verilen:[\s\S]{0,200}150 ₺/);
});

test('an order the server did not mark as mine is never shown as mine', () => {
    // Sunucu `is_mine` alanını kendisi hesaplar. `null` (oturumu bilinmeyen
    // eski kayıt) "benim" sayılmamalı.
    const legacy = [order(1, 100, null, 'Eski Sipariş'), order(2, 60, true, 'Kola')];
    const { html } = renderTracking({
        orders: legacy, genelToplam: 160, benimToplamim: 60, mode: 'mine'
    });

    assert.match(html, /Kola/);
    assert.ok(!/Eski Sipariş/.test(html));
});

test('the personal view explains itself when the device has ordered nothing', () => {
    const others = [order(2, 250, false, 'Karışık Pizza')];
    const { html } = renderTracking({
        orders: others, genelToplam: 250, benimToplamim: 0, mode: 'mine'
    });

    assert.match(html, /Bu cihazdan henüz sipariş verilmedi/);
    assert.match(html, /Masanın Tümü/, 'geri dönüş yolu gösterilmeli');
});

// ---------------------------------------------------------------------------
// Sekmeler
// ---------------------------------------------------------------------------

test('the tabs appear only when the server knows who ordered what', () => {
    const known = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150
    });
    assert.match(known.html, /Benim Siparişlerim/);

    // Oturum bilgisi yoksa (personel/oturumsuz okuma) olmayan bir ayrımı
    // varmış gibi sunmak yanıltıcı olur.
    const unknown = renderTracking({
        orders: [order(1, 100, null, 'Çorba')], genelToplam: 100, benimToplamim: null
    });
    assert.ok(!/Benim Siparişlerim/.test(unknown.html));
});

test('the chosen view survives a reload', () => {
    const { store } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'mine'
    });

    assert.equal(store['qr_order_view_mode'], 'mine');
});

test('the collapsed header still counts the whole table', () => {
    const { sandbox, container } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150, mode: 'mine'
    });

    sandbox.isTrackingCollapsed = true;
    sandbox.renderOrderTrackingUI();

    // Kapalı başlık masanın özeti; kişisel filtre onu küçültmemeli.
    assert.match(container.innerHTML, /Adisyon \(3 Sipariş • 400 ₺\)/);
});

// ---------------------------------------------------------------------------
// Sözleşme
// ---------------------------------------------------------------------------

test('ownership comes from the server field, not from a local device id', () => {
    const body = extractBlock(appSource, 'function renderOrderTrackingUI() {');

    assert.match(body, /o\.is_mine === true/);
    assert.ok(
        !/is_mine[\s\S]{0,40}state\.deviceId/.test(body),
        'sahiplik istemcideki cihaz kimliğinden türetilmemeli'
    );
});

test('the customer client stores the personal total the server sent', () => {
    const body = extractBlock(appSource, 'async function checkActiveOrder() {');

    assert.match(body, /state\.benimToplamim = \(typeof data\.benim_toplamim === 'number'\)/);
});

test('app.js got a fresh cache version', () => {
    const menu = read('templates/menu.html');
    assert.ok(Number((menu.match(/app\.js\?v=(\d+)/) || [])[1]) >= 88);
});

test('app.js still parses', () => {
    assert.doesNotThrow(() => new vm.Script(appSource, { filename: 'app.js' }));
});

// ---------------------------------------------------------------------------
// Adisyon kartında donma / takılma
//
// Müşteri "Adisyonu küçültmek için tıklayın" satırına her bastığında anlık bir
// donma yaşanıyordu; adisyonu genişletirken de aynısı oluyordu. Ölçüm, çizimin
// suçlu olmadığını gösterdi (JS ~1 ms, layout ~1 ms). İki gerçek neden vardı.
// ---------------------------------------------------------------------------

test('both bill toggles are registered as tappable targets', () => {
    const source = read('static/js/app.js');
    const css = read('static/css/style.css');

    // Neden: `touch-action: manipulation` taşımayan bir öğede mobil tarayıcı,
    // çift dokunuşla yakınlaştırma ihtimali için dokunuştan sonra ~300 ms
    // bekler. Kullanıcının "anlık donma" dediği gecikme buydu ve her iki yönde
    // de yaşanıyordu. `user-select` olmadan ise metne dokunmak seçim başlatıyor.
    const toggleSatirlari = source.split('\n').filter(line => line.includes('onclick="toggleTrackingUI()"'));
    assert.equal(toggleSatirlari.length, 2, 'kapalı ve açık kart olmak üzere iki toggle hedefi');
    for (const line of toggleSatirlari) {
        assert.match(line, /class="[^"]*tracking-toggle/, 'her toggle hedefi tracking-toggle sınıfını taşımalı');
    }

    // Sınıf, projenin dokunulabilir öğe listesine eklenmiş olmalı.
    const kural = css.split('\n').find(line => line.includes('touch-action: manipulation') === false && line.includes('.size-option-card'));
    assert.ok(kural && kural.includes('.tracking-toggle'), 'tracking-toggle dokunulabilir seçici listesinde olmalı');
});

test('an unchanged bill is never rewritten into the DOM', () => {
    // `checkActiveOrder` 3 saniyede bir çalışıp kartı baştan kuruyordu. Bunun
    // ölçülen sonucu: `.tracking-scroll-list` içindeki kaydırma her seferinde
    // başa dönüyordu (scrollTop 120 -> 0), yani adisyonu açıp listeyi okumaya
    // çalışan müşteri sürekli yukarı atılıyordu.
    const { container, sandbox } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150
    });

    const ilkGovde = container.innerHTML;
    assert.ok(ilkGovde.length > 0, 'ilk çizim gövdeyi yazmalı');

    let yazmaSayisi = 0;
    let saklanan = ilkGovde;
    Object.defineProperty(container, 'innerHTML', {
        get: () => saklanan,
        set: value => { yazmaSayisi += 1; saklanan = value; }
    });

    for (let i = 0; i < 5; i++) sandbox.renderOrderTrackingUI();

    assert.equal(yazmaSayisi, 0, 'veri değişmediyse DOM’a hiç yazılmamalı');
});

test('a changed bill is written into the DOM', () => {
    // Atlama yalnızca gövde birebir aynıysa geçerli olmalı; yeni bir sipariş
    // düştüğünde kart mutlaka güncellenmeli.
    const { container, sandbox } = renderTracking({
        orders: THREE_ORDERS, genelToplam: 400, benimToplamim: 150
    });

    let yazmaSayisi = 0;
    let saklanan = container.innerHTML;
    Object.defineProperty(container, 'innerHTML', {
        get: () => saklanan,
        set: value => { yazmaSayisi += 1; saklanan = value; }
    });

    sandbox.state.activeOrders = THREE_ORDERS.concat([order(4, 75, true, 'Künefe')]);
    sandbox.state.genelToplam = 475;
    sandbox.renderOrderTrackingUI();

    assert.equal(yazmaSayisi, 1, 'gerçek değişiklik bir kez yazılmalı');
    assert.match(saklanan, /Künefe/);
});
