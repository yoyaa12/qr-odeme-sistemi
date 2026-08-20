/**
 * Kasa ekranının iki ayrı kusuru:
 *
 *  1. Adisyon aktarımı seçimi yok sayıyordu. İKİ giriş noktası var ve ikisi de
 *     bozuktu: görsel taşıma modundaki "Seçili Ürünleri Taşı" sekmesi
 *     kutucukları hiçbir yere göndermiyordu, F7 "MASA TAŞI" modalinde ise ürün
 *     seçimi diye bir şey hiç yoktu. Her ikisi de her zaman masanın tamamını
 *     taşıyordu.
 *  2. Adisyon tablosunda sayısal sütunlar dar ve bitişikti; "Ayrıntılar"
 *     düğmesi ürün adının uzunluğuna göre kayıyor, açıldığında da küçülüyordu.
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

const kasaSource = read('static/js/kasa.js');
const staffAuthSource = read('static/js/staff_auth.js');
const styleSource = read('static/css/style.css');

function extractBlock(source, signature, terminator = '\n}') {
    const start = source.indexOf(signature);
    assert.ok(start !== -1, `kaynakta bulunamadı: ${signature}`);
    const end = source.indexOf(terminator, start);
    assert.ok(end !== -1, `kapanış bulunamadı: ${signature}`);
    return source.slice(start, end + terminator.length);
}

// ---------------------------------------------------------------------------
// 1. Aktarım: iki giriş noktası da seçimi gerçekten gönderir
// ---------------------------------------------------------------------------

/**
 * Aktarım fonksiyonlarını sahte DOM ve sahte `authFetch` ile gerçekten
 * çalıştırır: "hangi uca, hangi gövdeyle gidiyor" sorusu kaynak taraması
 * yerine ölçülerek yanıtlanır.
 */
function transferSandbox({ checkedByContainer = {}, ticketItems = [] } = {}) {
    const calls = [];
    const toasts = [];

    const sandbox = {
        moveSourceTableId: 4,
        moveTargetTableId: 6,
        activeMasaId: 4,
        selectedTransferType: 'all',
        moveScope: 'all',
        currentTableItems: ticketItems,
        kasaTables: [
            { id: 4, masa_no: 'Masa 4' },
            { id: 6, masa_no: 'Masa 6' }
        ],
        getFormattedMasaNo: masaNo => masaNo,
        closeModal() { },
        cancelTableMoveMode() { },
        loadKasaData: async () => { },
        showKasaToast: message => toasts.push(message),
        appAlert() { },
        document: {
            querySelectorAll(selector) {
                const match = selector.match(/#(\w+) \.transfer-item-checkbox:checked/);
                assert.ok(match, `beklenmeyen seçici: ${selector}`);
                return (checkedByContainer[match[1]] || []).map(v => ({ value: String(v) }));
            },
            getElementById(id) {
                if (id === 'targetMasaSelect') return { value: '6' };
                return null;
            }
        },
        window: {},
        console: { error() { } }
    };
    sandbox.authFetch = async (url, options) => {
        calls.push({ url, body: JSON.parse(options.body) });
        return { ok: true, status: 200, json: async () => ({ message: 'ok' }) };
    };

    const code = [
        extractBlock(kasaSource, 'function getSelectedDetailIds() {'),
        extractBlock(kasaSource, 'function readCheckedTransferIds(containerId) {'),
        extractBlock(kasaSource, 'async function performTableTransfer(fromMasaId, toMasaId, detayIds) {'),
        extractBlock(kasaSource, 'window.confirmVisualTableTransfer = async function () {', '\n};'),
        extractBlock(kasaSource, 'window.confirmMoveTable = async function () {', '\n};')
    ].join('\n');

    vm.createContext(sandbox);
    new vm.Script(code).runInContext(sandbox);
    return { sandbox, calls, toasts };
}

test('the visual transfer posts exactly the checked rows', async () => {
    const box = transferSandbox({ checkedByContainer: { transferItemsContainer: [101, 103] } });
    box.sandbox.selectedTransferType = 'items';

    await box.sandbox.window.confirmVisualTableTransfer();

    assert.equal(box.calls.length, 1);
    assert.equal(box.calls[0].url, '/api/masalar/move-items');
    assert.deepEqual(box.calls[0].body, {
        from_masa_id: 4,
        to_masa_id: 6,
        detay_ids: [101, 103]
    });
});

test('the unchecked rows never reach the server', async () => {
    // Asıl kusur buydu: seçim ne olursa olsun masanın tamamı taşınıyordu.
    const box = transferSandbox({ checkedByContainer: { transferItemsContainer: [102] } });
    box.sandbox.selectedTransferType = 'items';

    await box.sandbox.window.confirmVisualTableTransfer();

    assert.deepEqual(box.calls[0].body.detay_ids, [102]);
    assert.ok(
        !box.calls.some(call => call.url === '/api/masalar/move'),
        'kalem aktarımı masa taşıma ucuna düşmemeli'
    );
});

test('an empty selection is refused before any request goes out', async () => {
    const box = transferSandbox({ checkedByContainer: { transferItemsContainer: [] } });
    box.sandbox.selectedTransferType = 'items';

    await box.sandbox.window.confirmVisualTableTransfer();

    assert.equal(box.calls.length, 0, 'hiçbir istek gönderilmemeli');
    assert.match(box.toasts.join(' '), /en az bir ürünü seçiniz/);
});

test('the whole-table tab still uses the table move endpoint', async () => {
    const box = transferSandbox();
    box.sandbox.selectedTransferType = 'all';

    await box.sandbox.window.confirmVisualTableTransfer();

    assert.equal(box.calls[0].url, '/api/masalar/move');
    assert.deepEqual(box.calls[0].body, { from_masa_id: 4, to_masa_id: 6 });
});

// --- F7 "MASA TAŞI" ---------------------------------------------------------

test('the F7 dialog can move only the selected items', async () => {
    // Bu modalde ürün seçimi diye bir şey yoktu: hedef masa sorup her zaman
    // masanın tamamını taşıyordu.
    const box = transferSandbox({ checkedByContainer: { moveTableItemsContainer: [201] } });
    box.sandbox.moveScope = 'items';

    await box.sandbox.window.confirmMoveTable();

    assert.equal(box.calls.length, 1);
    assert.equal(box.calls[0].url, '/api/masalar/move-items');
    assert.deepEqual(box.calls[0].body.detay_ids, [201]);
});

test('the F7 dialog still moves the whole table when that scope is chosen', async () => {
    const box = transferSandbox();
    box.sandbox.moveScope = 'all';

    await box.sandbox.window.confirmMoveTable();

    assert.equal(box.calls[0].url, '/api/masalar/move');
});

test('a partial transfer keeps the cashier on the source table', async () => {
    // Kaynak masada hâlâ hesap var; ekranı hedef masaya kaydırmak kasiyeri
    // kaybederdi. Tam taşımada ise hedef masaya geçilir.
    const partial = transferSandbox({ checkedByContainer: { moveTableItemsContainer: [201] } });
    partial.sandbox.moveScope = 'items';
    await partial.sandbox.window.confirmMoveTable();
    assert.equal(partial.sandbox.activeMasaId, 4);

    const full = transferSandbox();
    full.sandbox.moveScope = 'all';
    await full.sandbox.window.confirmMoveTable();
    assert.equal(full.sandbox.activeMasaId, 6);
});

test('the F7 dialog inherits the selection made in the ticket table', () => {
    const box = transferSandbox({
        ticketItems: [
            { selected: true, detay_ids: [11, 12] },
            { selected: false, detay_ids: [13] },
            { selected: true, detay_ids: [14] }
        ]
    });

    // vm realm'inden gelen dizi host Array prototipini taşımaz; deepStrictEqual
    // prototipi de karşılaştırdığı için içerik host tarafına kopyalanır.
    assert.deepEqual(Array.from(box.sandbox.getSelectedDetailIds()), [11, 12, 14]);
});

test('a rejected transfer surfaces the server reason instead of failing silently', async () => {
    const box = transferSandbox();
    box.sandbox.authFetch = async () => ({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Seçilen kalemlerden bazıları bu masaya ait değil.' })
    });

    await box.sandbox.window.confirmMoveTable();

    assert.match(box.toasts.join(' '), /Aktarım başarısız/);
    assert.match(box.toasts.join(' '), /bu masaya ait değil/);
});

test('both dialogs go through one transfer helper', () => {
    // Aynı davranışın iki kopyası, ikisinden birinin sessizce sapması demekti.
    const visual = extractBlock(kasaSource, 'window.confirmVisualTableTransfer = async function () {', '\n};');
    const f7 = extractBlock(kasaSource, 'window.confirmMoveTable = async function () {', '\n};');

    assert.match(visual, /performTableTransfer\(/);
    assert.match(f7, /performTableTransfer\(/);
    assert.ok(!/fetch\('\/api\/masalar\/move'/.test(f7), 'F7 artık kendi isteğini kurmamalı');
});

test('the checkbox value is the detail row id, not the list position', () => {
    const listBody = extractBlock(
        kasaSource,
        'function renderTransferItemsInto(containerId, masaId, preCheckedIds) {'
    );

    assert.match(listBody, /value="\$\{item\.id\}"/);
    assert.ok(
        !/item\.id \|\| idx/.test(listBody),
        'liste sırasını göndermek sunucuda hiçbir satıra karşılık gelmiyordu'
    );
    assert.match(
        listBody,
        /item\.id === undefined \|\| item\.id === null/,
        'kimlik gelmediyse seçim gönderilmeden uyarılmalı'
    );
});

test('the grouped ticket row carries the detail ids behind it', () => {
    const grouped = kasaSource.slice(
        kasaSource.indexOf('const itemObj = {'),
        kasaSource.indexOf('currentTableItems.push(itemObj);')
    );

    assert.match(grouped, /detay_ids: grp\.detay_ids\.slice\(\)/);
    assert.match(kasaSource, /groupedMap\[groupKey\]\.detay_ids\.push\(Number\(d\.id\)\)/);
});

test('the transfer list covers the same rows the server allows to move', () => {
    const body = extractBlock(kasaSource, 'function getTransferableItems(masaId) {');

    assert.match(body, /siparis_durumu !== 'iptal'/);
    assert.match(body, /siparis_durumu !== 'odendi_kapatildi'/);
});

test('the new endpoint is on the staff token allowlist', () => {
    // staff_auth.js window.fetch'i yalnızca listedeki yollar için token'lar.
    // Liste dışında kalan uç sessizce 401 alırdı.
    assert.match(
        staffAuthSource,
        /pathname === '\/api\/masalar\/move-items' && method === 'POST'/
    );
});

// ---------------------------------------------------------------------------
// 2. Adisyon tablosu hizalaması
// ---------------------------------------------------------------------------

test('the numeric columns are wide enough for a four-digit amount', () => {
    const head = kasaSource.slice(
        kasaSource.indexOf('<th>Ürün Adı & Ayrıntılar</th>'),
        kasaSource.indexOf('<th>Ürün Adı & Ayrıntılar</th>') + 700
    );

    const widths = [...head.matchAll(/width:(\d+)px/g)].map(m => Number(m[1]));
    assert.equal(widths.length, 4, 'Adet / Fiyat / Durum / Toplam');

    const [adet, fiyat, durum, toplam] = widths;
    // "9999.99 ₺" 900 ağırlıkta 1.05rem ile ~95px; hücre dolgusu 12+16px.
    assert.ok(toplam >= 135, `Toplam sütunu dar: ${toplam}px`);
    assert.ok(fiyat >= 110, `Fiyat sütunu dar: ${fiyat}px`);
    assert.ok(durum >= 140, `Durum sütunu dar: ${durum}px`);
    assert.ok(adet >= 60, `Adet sütunu dar: ${adet}px`);
});

test('the partial-payment badge is short enough to be readable', () => {
    // Uzun rozet ("✅ 1 ÖDENDİ · ⏳ 5 AÇIK") sütuna sığmıyor, "1 ÖD..." diye
    // kırpılıyordu. Kısa biçim aynı bilgiyi tek bakışta veriyor.
    assert.match(kasaSource, /◐ \$\{grp\.paid_adet\}\/\$\{grp\.toplam_adet\} ÖDENDİ/);
    assert.ok(
        !/\$\{grp\.unpaid_adet\} AÇIK<\/span>/.test(kasaSource),
        'kırpılan uzun rozet geri gelmemeli'
    );
    // Ayrıntı kaybolmuyor: açık tutar Toplam sütununun altında duruyor.
    assert.match(kasaSource, /Kasada: \$\{openLineTotal\.toFixed\(2\)\}/);
});

test('every numeric cell uses the shared right-aligned class', () => {
    const rowBlock = kasaSource.slice(
        kasaSource.indexOf('rowsHtml += `'),
        kasaSource.indexOf('itemIndex++;')
    );

    const numericCells = (rowBlock.match(/<td class="ticket-num-cell"/g) || []).length;
    assert.equal(numericCells, 4, 'Adet, Fiyat, Durum ve Toplam hücreleri');
    assert.ok(
        !/<td style="text-align:right/.test(rowBlock),
        'satır içi hizalama kalmamalı; genişlik ve dolgu tek yerden yönetilir'
    );
});

test('the numeric columns are visually separated from each other', () => {
    const rule = styleSource.slice(
        styleSource.indexOf('.vega-ticket-table td.ticket-num-cell,'),
        styleSource.indexOf('.vega-ticket-table td.ticket-num-cell:last-child,')
    );

    assert.match(rule, /border-left:\s*1px solid/, 'sütun ayırıcı çizgi');
    assert.match(rule, /padding-left:\s*12px/);
    assert.match(rule, /padding-right:\s*12px/);
});

test('the last numeric column keeps a gap so the amount is not clipped', () => {
    assert.match(
        styleSource,
        /\.vega-ticket-table td\.ticket-num-cell:last-child[\s\S]{0,160}padding-right:\s*16px/
    );
});

test('the details button sits at a fixed spot instead of trailing the name', () => {
    const rowBlock = kasaSource.slice(
        kasaSource.indexOf('rowsHtml += `'),
        kasaSource.indexOf('itemIndex++;')
    );

    // Düğme artık ürün adıyla aynı kutunun içinde değil; hücrenin doğrudan
    // çocuğu olarak sağ uca yerleşiyor, yani her satırda aynı x konumunda.
    const mainStart = rowBlock.indexOf('<div class="ticket-item-main">');
    const mainEnd = rowBlock.indexOf('btnAyrintilar_');
    assert.ok(mainStart !== -1 && mainEnd !== -1);
    assert.ok(
        rowBlock.slice(mainStart, mainEnd).includes('</div>'),
        'düğme ürün adı kutusunun dışında olmalı'
    );
    assert.match(rowBlock, /<div class="ticket-item-cell">/);
});

test('open and closed states of the details button are the same size', () => {
    const chipRule = styleSource.slice(
        styleSource.indexOf('.btn-ayrintilar-chip {'),
        styleSource.indexOf('.btn-ayrintilar-chip:hover')
    );

    // Yalnızca genişliği sabitlemek yetmiyordu: "▲ Gizle" tek satır, düğme
    // küçülüyor ve aynı noktaya ikinci tıklama ıskalıyordu.
    assert.match(chipRule, /width:\s*112px/);
    assert.match(chipRule, /height:\s*26px/);
    assert.match(chipRule, /box-sizing:\s*border-box/);
    assert.match(chipRule, /flex-shrink:\s*0/);
    assert.ok(!/margin-left:\s*8px/.test(chipRule), 'akış içi kaydırma kalmamalı');
});

test('a long product name is ellipsised instead of pushing the button out', () => {
    const mainRule = styleSource.slice(
        styleSource.indexOf('.ticket-item-main {'),
        styleSource.indexOf('.btn-ayrintilar-chip {')
    );

    assert.match(mainRule, /min-width:\s*0/);
    assert.match(mainRule, /text-overflow:\s*ellipsis/);
});

test('kasa.js got a fresh cache version for this batch', () => {
    const kasa = read('templates/kasa.html');
    assert.ok(Number((kasa.match(/kasa\.js\?v=(\d+)/) || [])[1]) >= 65);
    assert.ok(Number((kasa.match(/style\.css\?v=(\d+)/) || [])[1]) >= 25);
    assert.ok(Number((kasa.match(/staff_auth\.js\?v=(\d+)/) || [])[1]) >= 4);
});

test('kasa.js and staff_auth.js still parse', () => {
    assert.doesNotThrow(() => new vm.Script(kasaSource, { filename: 'kasa.js' }));
    assert.doesNotThrow(() => new vm.Script(staffAuthSource, { filename: 'staff_auth.js' }));
});
