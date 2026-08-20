/**
 * Üç ayrı ekranda görülen, hepsi "gösterilen sayı gerçeği yansıtmıyor"
 * ailesinden davranışları sabitler:
 *
 *  1. Müşteri menüsü: stok canlı güncellenir ve seçilebilen adet stoğu aşamaz.
 *  2. Garson paneli: masanın tüm adisyonunu değil, taşınacak fişi gösterir.
 *  3. Kasa: kalem seçimi yalnızca AÇIK adetleri tahsil eder.
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
const waiterSource = read('static/js/waiter.js');
const kasaSource = read('static/js/kasa.js');
const styleSource = read('static/css/style.css');

/**
 * Kaynaktan tek bir fonksiyonu, gövdesiyle birlikte söker. Böylece testler
 * "kaynakta şu ifade geçiyor mu" yerine fonksiyonun gerçek aritmetiğini
 * çalıştırabilir.
 */
function extractBlock(source, signature, terminator = '\n}') {
    const start = source.indexOf(signature);
    assert.ok(start !== -1, `kaynakta bulunamadı: ${signature}`);
    const end = source.indexOf(terminator, start);
    assert.ok(end !== -1, `kapanış bulunamadı: ${signature}`);
    return source.slice(start, end + terminator.length);
}

// ---------------------------------------------------------------------------
// 1. Müşteri menüsü: canlı stok
// ---------------------------------------------------------------------------

test('the customer menu listens for live stock broadcasts', () => {
    assert.match(
        appSource,
        /socket\.on\('stok_guncellendi',\s*\(data\)\s*=>\s*\{\s*applyStockSnapshot\(data\);/,
        'yan masanın siparişi bu ekrana anında yansımalı'
    );
});

test('a stock broadcast redraws the card so the "Son X Adet" badge follows', () => {
    const applyBody = extractBlock(appSource, 'function applyStockSnapshot(payload) {');

    assert.match(applyBody, /prod\.stok_miktari = yeniStok/, 'yerel stok güncellenmeli');
    assert.match(
        applyBody,
        /rerenderProductCard\(urunId\)/,
        'rozet, kart yeniden çizilmeden güncellenmez'
    );

    // Kart, rozeti üreten fonksiyonun kendisiyle çizilmeli; ayrı bir kopya
    // yazılırsa "Tükendi" ile "Son X Adet" zamanla birbirinden ayrışır.
    const rerenderBody = extractBlock(appSource, 'function rerenderProductCard(prodId) {');
    assert.match(rerenderBody, /renderProductCardHTML\(prod\)/);
});

test('the stock badge threshold still fires at five and below', () => {
    assert.match(
        appSource,
        /const isLowStock = stock >= 1 && stock <= 5;/,
        'düşük stok uyarısının eşiği korunmalı'
    );
});

// ---------------------------------------------------------------------------
// 2. Müşteri menüsü: adet stoğu aşamaz
// ---------------------------------------------------------------------------

function quantitySandbox({ stock, cart }) {
    const sandbox = {
        state: {
            currentProduct: { id: 3, urun_adi: 'Yayla Çorbası', stok_miktari: stock },
            cart: cart,
            urunler: [{ id: 3, urun_adi: 'Yayla Çorbası', stok_miktari: stock }]
        },
        toasts: [],
        input: { value: '1', max: '20' },
        updateModalCalculatedPrice() { },
        document: {
            getElementById(id) {
                return id === 'modalQuantity' ? sandbox.input : null;
            }
        },
        window: {}
    };
    sandbox.showToast = message => sandbox.toasts.push(message);

    const code = [
        extractBlock(appSource, 'const MAX_ITEM_QUANTITY_PER_ADD = 20;', ';'),
        extractBlock(appSource, 'function getProductStock(prod) {'),
        extractBlock(appSource, 'function getCartQuantityFor(prodId) {'),
        extractBlock(appSource, 'function getModalMaxQuantity() {'),
        extractBlock(appSource, 'window.changeModalQuantity = function (delta) {', '\n};')
    ].join('\n');

    vm.createContext(sandbox);
    new vm.Script(code).runInContext(sandbox);
    return sandbox;
}

test('the plus button stops at the stock level instead of overshooting it', () => {
    const box = quantitySandbox({ stock: 8, cart: [] });
    box.input.value = '8';

    box.window.changeModalQuantity(1);

    assert.equal(box.input.value, '8', '9 hiç gösterilmemeli');
    assert.deepEqual(box.toasts, ['⚠️ Stokta 8 adet kalmıştır.']);
});

test('quantities below the stock level are unaffected', () => {
    const box = quantitySandbox({ stock: 8, cart: [] });
    box.input.value = '3';

    box.window.changeModalQuantity(1);

    assert.equal(box.input.value, '4');
    assert.deepEqual(box.toasts, []);
});

test('what is already in the cart is subtracted from the selectable maximum', () => {
    // 8 stoklu üründen sepette 3 varsa modal en fazla 5 verdirmeli; aksi halde
    // sipariş 11 adetle sunucuya gider ve orada reddedilir.
    const box = quantitySandbox({ stock: 8, cart: [{ urun_id: 3, adet: 3 }] });
    box.input.value = '5';

    box.window.changeModalQuantity(1);

    assert.equal(box.input.value, '5');
    assert.deepEqual(box.toasts, ['⚠️ Stokta 8 adet kalmıştır.']);
});

test('a typed quantity above the stock level snaps down to it', () => {
    const clampBody = extractBlock(appSource, 'window.clampModalQuantity = function () {', '\n};');

    assert.match(
        clampBody,
        /input\.value = String\(maxAllowed\)/,
        'aşan giriş en yüksek geçerli değere eşitlenmeli'
    );
    assert.match(clampBody, /adet kalmıştır/, 'kalan stok müşteriye söylenmeli');
});

test('the quantity field is typeable and clamps what was typed', () => {
    const menu = read('templates/menu.html');
    const field = menu
        .split('\n')
        .find(line => line.includes('id="modalQuantity"'));

    assert.ok(field, 'adet alanı bulunmalı');
    assert.ok(!field.includes('readonly'), 'elle giriş mümkün olmalı');

    const fieldBlock = menu.slice(menu.indexOf('id="modalQuantity"'));
    assert.match(
        fieldBlock.slice(0, 400),
        /clampModalQuantity\(\)/,
        'yazılan değer sınırlanmadan fiyatlandırılmamalı'
    );
});

test('the cart screen cannot push a line past the stock level either', () => {
    const cartBody = extractBlock(
        appSource,
        'window.updateCartItemQuantity = async function (index, delta) {',
        '\n};'
    );

    assert.match(cartBody, /getCartQuantityFor\(urunId\) \+ delta > stock/);
    assert.match(cartBody, /adet kalmıştır/);
});

// ---------------------------------------------------------------------------
// 3. Toast bildirimi uzun metinde taşmamalı
// ---------------------------------------------------------------------------

test('the toast wraps long messages instead of spilling past its border', () => {
    const toastRule = styleSource.slice(
        styleSource.lastIndexOf('.toast-notification {'),
        styleSource.lastIndexOf('.toast-notification {') + 900
    );

    assert.ok(
        !/white-space:\s*nowrap/.test(toastRule),
        'nowrap uzun metni kapsülün dışına taşırıyordu'
    );
    assert.match(toastRule, /white-space:\s*normal/);
    assert.match(toastRule, /overflow-wrap:\s*anywhere/);
});

// ---------------------------------------------------------------------------
// 4. Garson paneli: taşınacak fiş, masanın adisyonu değil
// ---------------------------------------------------------------------------

test('the waiter detail leaves delivered orders out of the carry list', () => {
    const detailBody = waiterSource.slice(
        waiterSource.indexOf('function openMasaDetail(masaId) {'),
        waiterSource.indexOf('window.approveTableOrdersWithPin')
    );

    assert.match(
        detailBody,
        /const serviceOrders = activeOrders\.filter\(o => o\.siparis_durumu !== 'teslim_edildi'\)/,
        'teslim edilmiş sipariş yeniden taşınacakmış gibi listelenmemeli'
    );
    assert.ok(
        !detailBody.includes('combinedItems'),
        'masanın tüm kalemlerini tek listede toplayan birleştirme kaldırılmalı'
    );
    assert.match(
        detailBody,
        /serviceOrders\.forEach\(order => \{/,
        'kalemler fiş bazında listelenmeli'
    );
    assert.match(detailBody, /Fiş #\$\{escapeHtml\(order\.id\)\}/, 'her blok fiş numarasını taşımalı');
});

test('delivered items are acknowledged but not counted as work to do', () => {
    const detailBody = waiterSource.slice(
        waiterSource.indexOf('function openMasaDetail(masaId) {'),
        waiterSource.indexOf('window.approveTableOrdersWithPin')
    );

    assert.match(detailBody, /deliveredItemCount/);
    assert.match(detailBody, /daha önce \$\{deliveredItemCount\} ürün teslim edildi/);
});

test('each pending receipt carries the status the waiter must act on', () => {
    const sandbox = {};
    vm.createContext(sandbox);
    new vm.Script(
        extractBlock(waiterSource, 'function getWaiterOrderStatusLabel(durum) {') +
        '\nthis.label = getWaiterOrderStatusLabel;'
    ).runInContext(sandbox);

    assert.match(sandbox.label('garson_onayi_bekliyor').text, /Onay Bekliyor/);
    assert.match(sandbox.label('hazir').text, /Servise Hazır/);
    assert.match(sandbox.label('nakit_bekliyor').text, /Nakit/);
    assert.equal(typeof sandbox.label('bilinmeyen_durum').text, 'string');
});

// ---------------------------------------------------------------------------
// 5. Kasa: seçim yalnızca açık adetleri tahsil eder
// ---------------------------------------------------------------------------

function selectionTotal(items) {
    const sandbox = { currentTableItems: items };
    vm.createContext(sandbox);
    new vm.Script(
        extractBlock(kasaSource, 'function getSelectedItemsTotal() {') +
        '\nthis.total = getSelectedItemsTotal();'
    ).runInContext(sandbox);
    return sandbox.total;
}

test('selecting a partly paid line charges only the open quantities', () => {
    // Bildirilen senaryo: 85 TL'lik çorbadan 2 adet kartla ödendi, 4 adet
    // garson onaylı gönderildi. Satır 6 adet gösterir; seçim 510 TL değil
    // 340 TL getirmelidir.
    const total = selectionTotal([
        {
            selected: true,
            isIkram: false,
            adet: 6,
            birim_fiyat: 85,
            ara_toplam: 510,
            paid_adet: 2,
            unpaid_adet: 4,
            acik_tutar: 340
        }
    ]);

    assert.equal(total, 340);
});

test('an unpaid line is charged in full', () => {
    const total = selectionTotal([
        {
            selected: true, isIkram: false, adet: 4, birim_fiyat: 85,
            ara_toplam: 340, paid_adet: 0, unpaid_adet: 4, acik_tutar: 340
        }
    ]);

    assert.equal(total, 340);
});

test('unselected and ikram lines contribute nothing', () => {
    const total = selectionTotal([
        { selected: false, isIkram: false, acik_tutar: 340 },
        { selected: true, isIkram: true, acik_tutar: 170 }
    ]);

    assert.equal(total, 0);
});

test('the open amount is derived from the unpaid quantity, not the line total', () => {
    const groupedBlock = kasaSource.slice(
        kasaSource.indexOf('const itemObj = {'),
        kasaSource.indexOf('currentTableItems.push(itemObj);')
    );

    assert.match(
        groupedBlock,
        /acik_tutar: \(grp\.unpaid_adet \|\| 0\) \* \(parseFloat\(grp\.birim_fiyat\) \|\| 0\)/
    );
});

test('no payment path sums the full line total of selected items any more', () => {
    // Beş ayrı yerde aynı toplama kopyalanmıştı; hepsi tek yardımcıya
    // indirildi. Kopyanın geri gelmesi bu testi düşürür.
    assert.ok(
        !/i\.selected[\s\S]{0,120}parseFloat\(i\.ara_toplam\)/.test(kasaSource),
        'seçim toplamı ara_toplam üzerinden hesaplanmamalı'
    );

    const callers = kasaSource.match(/getSelectedItemsTotal\(\)/g) || [];
    assert.ok(callers.length >= 4, `beklenen çağrı sayısı bulunamadı: ${callers.length}`);
});

test('the remaining balance subtracts what was already paid at order time', () => {
    const remainingBody = extractBlock(kasaSource, 'function getActiveMasaRemaining() {');
    const paidBody = extractBlock(kasaSource, 'function getActiveMasaPaidBefore() {');

    assert.match(remainingBody, /getActiveMasaPaidBefore\(\)/);
    assert.match(
        paidBody,
        /activeMasaPaidFromOrders \+ \(parseFloat\(partialPaymentsMap\[activeMasaId\]\) \|\| 0\)/,
        'kartla sipariş anında ödenen tutar da düşülmeli'
    );
});

test('a partly paid row tells the cashier how much of it is still open', () => {
    // Rozet kısa tutuluyor (sütuna sığması için); tahsil edilecek tutar Toplam
    // sütununun altında ayrı satır olarak duruyor.
    assert.match(kasaSource, /isPartiallyPaid = \(grp\.paid_adet > 0 && grp\.unpaid_adet > 0\)/);
    assert.match(kasaSource, /\$\{grp\.paid_adet\}\/\$\{grp\.toplam_adet\} ÖDENDİ/);
    assert.match(kasaSource, /Kasada: \$\{openLineTotal\.toFixed\(2\)\}/);
});

test('the printed receipt breaks payments down instead of lumping them', () => {
    // Tek satırda toplanan "Önceden Ödenen" yanlış okunuyordu: sipariş anında
    // kartla ödenen 180 TL ile kasada henüz alınan 85 TL aynı satırda 265 TL
    // görünüyordu. İkisi ayrı olaydır.
    const receiptBody = kasaSource.slice(
        kasaSource.indexOf('window.printReceiptPreview'),
        kasaSource.indexOf('window.closeModal')
    );

    assert.match(receiptBody, /ÖDEME BİLGİLERİ/);
    assert.match(receiptBody, /Sipariş anında ödenen/);
    assert.match(receiptBody, /Kasada tahsil edilen/);
    assert.match(receiptBody, /KALAN ÖDENECEK/);
    assert.match(receiptBody, /const paidAtOrderTime = activeMasaPaidFromOrders/);
    assert.ok(
        !/<span>Önceden Ödenen:<\/span>/.test(receiptBody),
        'iki ödemeyi tek satırda toplayan etiket fişe geri basılmamalı'
    );
});

// ---------------------------------------------------------------------------
// 6. Değişen dosyalar önbellekten servis edilmemeli
// ---------------------------------------------------------------------------

test('every changed asset got a fresh cache version', () => {
    const menu = read('templates/menu.html');
    const garson = read('templates/garson.html');
    const kasa = read('templates/kasa.html');

    assert.ok(Number((menu.match(/app\.js\?v=(\d+)/) || [])[1]) >= 86, 'app.js');
    assert.ok(Number((menu.match(/style\.css\?v=(\d+)/) || [])[1]) >= 73, 'menu style.css');
    assert.ok(Number((garson.match(/waiter\.js\?v=(\d+)/) || [])[1]) >= 80, 'waiter.js');
    assert.ok(Number((kasa.match(/kasa\.js\?v=(\d+)/) || [])[1]) >= 63, 'kasa.js');
});

test('all three panel scripts still parse', () => {
    assert.doesNotThrow(() => new vm.Script(appSource, { filename: 'app.js' }));
    assert.doesNotThrow(() => new vm.Script(waiterSource, { filename: 'waiter.js' }));
    assert.doesNotThrow(() => new vm.Script(kasaSource, { filename: 'kasa.js' }));
});
