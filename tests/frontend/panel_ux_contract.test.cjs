const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const repositoryRoot = path.resolve(__dirname, '..', '..');

function read(relativePath) {
    return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8');
}

const waiterSource = read('static/js/waiter.js');
const appSource = read('static/js/app.js');

// "Değişiklikleri Kaydet" her seferinde sessizce hiçbir şey yapmıyordu: masa
// detayını kapatan çağrı garson kimliğini (`activeGarson`) siliyor, düzenleme
// ekranı ondan sonra açılıyor ve kaydetme fonksiyonu `if (!activeGarson) return`
// ile çıkıyordu. Ne hata, ne mesaj.

test('opening the order editor does not wipe the waiter identity', () => {
    const editButton = waiterSource
        .split('\n')
        .find(line => line.includes('openEditOrderModalForTable(${masaId})'));

    assert.ok(editButton, 'the edit button must exist');
    assert.ok(
        !editButton.includes('closeMasaDetailModal()'),
        'closeMasaDetailModal clears activeGarson; the edit flow must not call it'
    );
    assert.match(
        editButton,
        /hideMasaDetailModal\(\)/,
        'the edit flow must hide the detail modal without clearing identity'
    );
});

test('hideMasaDetailModal only hides, closeMasaDetailModal also clears identity', () => {
    const hideBody = waiterSource.slice(
        waiterSource.indexOf('window.hideMasaDetailModal'),
        waiterSource.indexOf('window.closeMasaDetailModal')
    );
    const closeBody = waiterSource.slice(
        waiterSource.indexOf('window.closeMasaDetailModal'),
        waiterSource.indexOf('window.closeMasaDetailModal') + 400
    );

    assert.ok(
        !hideBody.includes('activeGarson = null'),
        'hideMasaDetailModal must preserve the waiter identity'
    );
    assert.match(
        closeBody,
        /activeGarson = null/,
        'closeMasaDetailModal keeps its original meaning'
    );
});

test('saving an edited order never returns without telling the user', () => {
    const saveBody = waiterSource.slice(
        waiterSource.indexOf('window.saveEditedOrder'),
        waiterSource.indexOf('function updateActiveGarsonBadge')
    );

    assert.ok(saveBody.length > 0, 'saveEditedOrder must exist');
    assert.ok(
        !/if\s*\(!activeGarson\)\s*return;/.test(saveBody),
        'a missing waiter identity must not silently abort the save'
    );

    // Her erken çıkıştan önce kullanıcıya bir şey söylenmeli.
    const earlyReturns = saveBody.match(/^\s*return;\s*$/gm) || [];
    const toasts = saveBody.match(/showWaiterToast\(/g) || [];
    assert.ok(
        toasts.length >= earlyReturns.length,
        `every early return needs a message (returns=${earlyReturns.length}, toasts=${toasts.length})`
    );
});

test('the edit payload no longer carries a forgeable waiter name', () => {
    const saveBody = waiterSource.slice(
        waiterSource.indexOf('window.saveEditedOrder'),
        waiterSource.indexOf('function updateActiveGarsonBadge')
    );
    const payloadBody = saveBody.slice(
        saveBody.indexOf('const payload'),
        saveBody.indexOf('try {')
    );

    assert.ok(
        !payloadBody.includes('garson_adi'),
        'the server takes the audit name from the token; sending one is misleading'
    );
});

// Müşteri menüsündeki stok sayfa açılışında bir kez yükleniyordu, bu yüzden
// "stokta 16 adet kalmıştır" derken gerçek stok 10 olabiliyordu.

test('the customer menu refreshes stock without re-rendering the menu', () => {
    const refreshBody = appSource.slice(
        appSource.indexOf('async function refreshStockQuietly'),
        appSource.indexOf('setInterval(refreshStockQuietly')
    );

    assert.ok(refreshBody.length > 0, 'refreshStockQuietly must exist');
    assert.match(refreshBody, /\/api\/urunler/, 'it must re-read the product list');
    assert.match(refreshBody, /stok_miktari/, 'it must update the stock field');
    assert.ok(
        !refreshBody.includes('renderProducts()'),
        're-rendering would move the menu under the customer while scrolling'
    );
});

test('stock is refreshed after an order and on a timer', () => {
    assert.match(
        appSource,
        /setInterval\(refreshStockQuietly,\s*\d+\)/,
        'other tables also consume stock, so a periodic refresh is required'
    );

    const submitBody = appSource.slice(
        appSource.indexOf('async function executeOrderSubmit'),
        appSource.indexOf('function openFirstOrderPINModal')
    );
    assert.match(
        submitBody,
        /refreshStockQuietly\(\)/,
        'the order we just placed changed stock too'
    );
});

test('both panel scripts still parse', () => {
    assert.doesNotThrow(() => new vm.Script(waiterSource, { filename: 'waiter.js' }));
    assert.doesNotThrow(() => new vm.Script(appSource, { filename: 'app.js' }));
});

test('changed panel scripts got a fresh cache version', () => {
    const menu = read('templates/menu.html');
    const garson = read('templates/garson.html');

    const appVersion = Number((menu.match(/app\.js\?v=(\d+)/) || [])[1]);
    const waiterVersion = Number((garson.match(/waiter\.js\?v=(\d+)/) || [])[1]);

    assert.ok(appVersion >= 85, 'app.js version must be bumped');
    assert.ok(waiterVersion >= 79, 'waiter.js version must be bumped');
});
