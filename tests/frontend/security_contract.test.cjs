const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repositoryRoot = path.resolve(__dirname, '..', '..');

function read(relativePath) {
    return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8');
}

function assertHelperLoadsBefore(templateSource, mainScriptName) {
    const helperIndex = templateSource.indexOf('/static/js/security.js');
    const mainIndex = templateSource.indexOf(`/static/js/${mainScriptName}`);

    assert.notEqual(helperIndex, -1, 'security helper script must be present');
    assert.notEqual(mainIndex, -1, `${mainScriptName} must be present`);
    assert.ok(helperIndex < mainIndex, 'security helper must load before the page script');
}

test('staff and table verification templates do not publish credential examples', () => {
    const waiterTemplate = read('templates/garson.html');
    const menuTemplate = read('templates/menu.html');

    assert.doesNotMatch(waiterTemplate, /\b\d{6}\b/);
    assert.doesNotMatch(waiterTemplate, /Tanımlı Garson PIN/i);
    assert.match(waiterTemplate, /PIN bilginizi yöneticinizden alınız\./);
    assert.match(menuTemplate, /placeholder="6 haneli kod"/);
});

test('security helper loads before every hardened page script', () => {
    assertHelperLoadsBefore(read('templates/menu.html'), 'app.js');
    assertHelperLoadsBefore(read('templates/garson.html'), 'waiter.js');
    assertHelperLoadsBefore(read('templates/mutfak.html'), 'kitchen.js');
    assertHelperLoadsBefore(read('templates/kasa.html'), 'kasa.js');
    // Yönetici paneli uzun süre bu listenin dışındaydı: security.js'i hiç
    // yüklemiyor, admin.js de escapeHtml kullanmıyordu.
    assertHelperLoadsBefore(read('templates/admin.html'), 'admin.js');
});

test('admin panel encodes every free-text name it renders', () => {
    const adminSource = read('static/js/admin.js');

    // Kategori ve ürün adları yöneticinin serbest metin girdisidir ve tablolar
    // `innerHTML` ile basılır. Kaçış olmadan, adın içine konan bir etiket
    // panelde çalışırdı.
    assert.match(adminSource, /const escapeHtml = window\.SecurityText\.escapeHtml;/);
    assert.match(adminSource, /\$\{escapeHtml\(cat\.kategori_adi\)\}/);
    assert.match(adminSource, /\$\{escapeHtml\(p\.urun_adi\)\}/);
    assert.match(adminSource, /\$\{escapeHtml\(p\.kategori_adi \|\| ''\)\}/);
    assert.match(adminSource, /\$\{escapeHtml\(u\.urun_adi\)\}/);
    assert.match(adminSource, /\$\{escapeHtml\(u\.kategori_adi \|\| '-'\)\}/);

    // Kaçışsız hiçbir ad kalmamalı.
    assert.doesNotMatch(adminSource, /\$\{(cat|p|u)\.(kategori_adi|urun_adi)\}/);

    // Düzenleme satırındaki input `value` özniteliği de bir HTML sink'idir:
    // kaçışsız bir ad özniteliği kapatıp kendi etiketini açabilirdi.
    assert.match(adminSource, /value="\$\{escapeHtml\(p\.urun_adi\)\}"/);
    assert.match(adminSource, /value="\$\{escapeHtml\(p\.aciklama \|\| ''\)\}"/);
});

test('admin product edit form sends every editable field', () => {
    const adminSource = read('static/js/admin.js');

    // Panelde uzun süre yalnızca stok kutusu vardı; ad, kategori ve fiyatı
    // düzeltmenin tek yolu veritabanına gitmekti.
    assert.match(adminSource, /function startEditProduct\(/);
    assert.match(adminSource, /function saveEditProduct\(/);
    assert.match(adminSource, /function cancelEditProduct\(/);

    const saveBlock = adminSource.slice(adminSource.indexOf('async function saveEditProduct('));
    for (const field of ['urun_adi', 'kategori_id', 'fiyat', 'stok_miktari', 'aciklama']) {
        assert.ok(saveBlock.includes(field), `saveEditProduct must send ${field}`);
    }

    // Yanıt durumu kontrol edilmeden başarı mesajı gösterilmemeli; silme
    // düğmelerindeki eski hata tam olarak buydu.
    assert.match(saveBlock, /if \(!res\.ok\)/);
});

test('admin panel never embeds a product name inside an onclick attribute', () => {
    const adminSource = read('static/js/admin.js');

    // Ad eskiden çift tırnaklı bir HTML özniteliğinin içindeki tek tırnaklı bir
    // JS string literaline gömülüyordu; içindeki bir çift tırnak özniteliği
    // kapatabiliyordu ve kaçış yalnızca tek tırnağı ele alıyordu. Ad artık
    // `data-` özniteliğinde taşınıyor ve handler onu oradan okuyor.
    assert.doesNotMatch(adminSource, /onclick="updateProductStock\(\$\{p\.id\},/);
    assert.match(adminSource, /data-urun-adi="\$\{escapeHtml\(p\.urun_adi\)\}"/);
    assert.match(adminSource, /onclick="updateProductStock\(\$\{p\.id\}\)"/);
    assert.match(adminSource, /const urunAdi = input\.dataset\.urunAdi \|\| "";/);

    // Hiçbir onclick özniteliğinin içinde JS string literali kalmamalı.
    assert.doesNotMatch(adminSource, /onclick="[^"]*'/);
});

test('order notes and associated names are encoded at every targeted sink', () => {
    const appSource = read('static/js/app.js');
    const waiterSource = read('static/js/waiter.js');
    const kitchenSource = read('static/js/kitchen.js');
    const cashierSource = read('static/js/kasa.js');

    assert.doesNotMatch(appSource, /\$\{\s*(?:item|group)\.urun_notu\s*\}/);
    assert.doesNotMatch(waiterSource, /\$\{\s*item\.urun_notu\s*\}/);
    assert.doesNotMatch(kitchenSource, /\$\{\s*item\.urun_notu\s*\}/);
    assert.doesNotMatch(cashierSource, /\$\{\s*(?:d|grp)\.urun_notu\s*\}/);
    assert.match(appSource, /Not: \$\{escapeHtml\(item\.urun_notu\)\}/);
    assert.match(appSource, /• \$\{escapeHtml\(item\.urun_notu\)\}/);
    assert.match(appSource, /Not: \$\{escapeHtml\(group\.urun_notu\)\}/);
    assert.match(waiterSource, /Not: \$\{escapeHtml\(item\.urun_notu\)\}/);
    assert.match(waiterSource, /\$\{escapeHtml\(item\.urun_notu\)\}<\/div>/);
    assert.match(kitchenSource, /MÜŞTERİ NOTU: \$\{escapeHtml\(item\.urun_notu\)\}/);
    assert.match(cashierSource, /📝 \$\{escapeHtml\(grp\.urun_notu\)\}/);
    assert.match(cashierSource, /Not: \$\{escapeHtml\(d\.urun_notu\)\}/);
    assert.match(appSource, /\$\{escapeHtml\(group\.urun_adi\)\}/);
    assert.match(waiterSource, /\$\{escapeHtml\(item\.urun_adi\)\}/);
    assert.match(kitchenSource, /\$\{escapeHtml\(item\.urun_adi\)\}/);
    assert.match(cashierSource, /\$\{escapeHtml\(grp\.urun_adi\)\}/);
});

test('attacker-controlled keys and device ids are not interpolated into executable HTML', () => {
    const appSource = read('static/js/app.js');
    const waiterSource = read('static/js/waiter.js');
    const cashierSource = read('static/js/kasa.js');

    assert.doesNotMatch(appSource, /toggleGroupDetails\('\$\{key\}'\)/);
    assert.doesNotMatch(appSource, /groupDetails_\$\{key\}/);
    assert.doesNotMatch(cashierSource, /toggleGroupDetails\('\$\{key\}'/);
    assert.doesNotMatch(cashierSource, /(?:groupDetails|btnAyrintilar)_\$\{key\}/);
    assert.doesNotMatch(waiterSource, /banDeviceDirect\('\$\{did\}'/);
    assert.match(appSource, /renderedGroupKeys\[groupIndex\]/);
    assert.match(cashierSource, /renderedGroupKeys\[groupIndex\]/);
    assert.match(appSource, /onclick="toggleGroupDetails\(\$\{idx\}\)"/);
    assert.match(appSource, /id="groupDetails_\$\{idx\}"/);
    assert.match(cashierSource, /onclick="toggleGroupDetails\(\$\{itemIndex\}, event\)"/);
    assert.match(cashierSource, /id="groupDetails_\$\{itemIndex\}"/);
    assert.match(waiterSource, /class="js-ban-device"/);
    assert.match(waiterSource, /button\.addEventListener\('click'/);
    assert.match(waiterSource, /const deviceId = detailDeviceIds\[deviceIndex\]/);
    assert.match(waiterSource, /window\.banDeviceDirect\(deviceId, masaId\)/);
});

test('socket-provided table text is encoded and table ids are normalized', () => {
    const waiterSource = read('static/js/waiter.js');

    assert.doesNotMatch(waiterSource, />\$\{formattedMasaNo\}</);
    assert.doesNotMatch(waiterSource, /openMasaDetailWithPin\(\$\{id\}\)/);
    assert.match(waiterSource, /escapeHtml\(formattedMasaNo\)/);
    assert.match(waiterSource, /escapeHtml\(getFormattedMasaNo\(group\.masa_no\)\)/);
    assert.match(waiterSource, /toPositiveInteger\(data\.masa_id\)/);
});
