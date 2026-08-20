/**
 * AGENTS.md 27-29 arayuz kurallarinin sozlesme testleri.
 *
 * Bu kurallar daha once yalnizca dokumanda yaziliydi ve kodda ihlal ediliyordu.
 * Testler ihlallerin sessizce geri gelmesini engeller.
 *
 * Not: Tarama yapmadan once yorum satirlari cikarilir; aksi halde "bu kural
 * neden var" diye yazilmis bir aciklama kuralin kendisini ihlal ediyormus gibi
 * gorunurdu.
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

/** /* ... *\/ ve // ... yorumlarini kaldirir (string icerigi korunmaz, tarama icin yeterli). */
function stripComments(source) {
    return source
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/^\s*\/\/.*$/gm, ' ');
}

const STYLE_FILES = [
    'static/css/style.css',
    'static/js/rulet.js',
    'templates/kasa.html',
    'templates/menu.html',
    'templates/garson.html',
    'templates/mutfak.html',
    'templates/admin.html',
    'templates/index.html'
];

const PANEL_SCRIPTS = [
    'static/js/app.js',
    'static/js/waiter.js',
    'static/js/kitchen.js',
    'static/js/kasa.js',
    'static/js/admin.js',
    'static/js/rulet.js',
    'static/js/staff_auth.js'
];

test('no stylesheet or template uses the forbidden `transition: all`', () => {
    for (const file of STYLE_FILES) {
        const source = stripComments(read(file));
        assert.doesNotMatch(
            source,
            /transition\s*:\s*all\b/,
            `${file} icinde 'transition: all' var (AGENTS.md 27)`
        );
        assert.doesNotMatch(
            source,
            /transition\s*:\s*var\(--transition-all/,
            `${file} yasakli kisayolu degisken uzerinden kullaniyor`
        );
    }
});

test('no stylesheet or template uses backdrop-filter blur', () => {
    for (const file of STYLE_FILES) {
        const source = stripComments(read(file));
        assert.doesNotMatch(
            source,
            /backdrop-filter/,
            `${file} icinde backdrop-filter var (AGENTS.md 27)`
        );
    }
});

test('no stylesheet or template uses background-attachment: fixed', () => {
    for (const file of STYLE_FILES) {
        const source = stripComments(read(file));
        assert.doesNotMatch(
            source,
            /background-attachment\s*:\s*fixed/,
            `${file} icinde background-attachment: fixed var (AGENTS.md 27)`
        );
    }
});

test('the shared --transition variable names concrete properties', () => {
    const css = read('static/css/style.css');
    const match = css.match(/--transition:\s*([^;]+);/);
    assert.ok(match, '--transition degiskeni bulunamadi');
    assert.doesNotMatch(match[1], /\ball\b/, '--transition hala "all" kullaniyor');
    assert.match(match[1], /transform/);
    assert.match(match[1], /opacity/);
});

test('panel scripts never call the native alert/confirm/prompt dialogs', () => {
    for (const file of PANEL_SCRIPTS) {
        const source = stripComments(read(file));
        // appAlert / appConfirm / playKitchenAlertSound gibi adlar haric tutulur.
        assert.doesNotMatch(
            source,
            /(?<![\w.$])alert\s*\(/,
            `${file} native alert() cagiriyor (AGENTS.md 29)`
        );
        assert.doesNotMatch(
            source,
            /(?<![\w.$])confirm\s*\(/,
            `${file} native confirm() cagiriyor (AGENTS.md 29)`
        );
        assert.doesNotMatch(
            source,
            /(?<![\w.$])prompt\s*\(/,
            `${file} native prompt() cagiriyor (AGENTS.md 29)`
        );
    }
});

test('every page whose script uses appAlert/appConfirm loads the dialog module first', () => {
    const pages = {
        'templates/menu.html': 'static/js/app.js',
        'templates/garson.html': 'static/js/waiter.js',
        'templates/mutfak.html': 'static/js/kitchen.js',
        'templates/kasa.html': 'static/js/kasa.js',
        'templates/admin.html': 'static/js/admin.js'
    };

    for (const [templatePath, scriptPath] of Object.entries(pages)) {
        const scriptSource = read(scriptPath);
        if (!/\bapp(Alert|Confirm)\s*\(/.test(scriptSource)) continue;

        const template = read(templatePath);
        const helperIndex = template.indexOf('/static/js/ui_confirm.js');
        const scriptIndex = template.indexOf(`/static/js/${path.basename(scriptPath)}`);

        assert.notEqual(helperIndex, -1, `${templatePath} ui_confirm.js yuklemiyor`);
        assert.notEqual(scriptIndex, -1, `${templatePath} ${scriptPath} yuklemiyor`);
        assert.ok(
            helperIndex < scriptIndex,
            `${templatePath}: ui_confirm.js panel scriptinden once yuklenmeli`
        );
    }
});

test('the in-app dialogs write their message as text, not HTML', () => {
    const source = read('static/js/ui_confirm.js');
    assert.match(source, /#appConfirmMsg'\)\.innerText = message/);
    assert.match(source, /#appAlertMsg'\)\.innerText = message/);
    assert.doesNotMatch(source, /appAlertMsg'\)\.innerHTML = message/);
    assert.doesNotMatch(source, /appConfirmMsg'\)\.innerHTML = message/);
});

test('appAlert is exported for panel scripts', () => {
    const source = read('static/js/ui_confirm.js');
    assert.match(source, /window\.appAlert\s*=\s*appAlert/);
});

test('waiting for a staff session cannot hang forever', () => {
    const source = read('static/js/staff_auth.js');
    assert.match(
        source,
        /SESSION_WAIT_TIMEOUT_MS/,
        'waitForSession bir zaman asimi tanimlamali'
    );
    assert.match(
        source,
        /reject\(new Error\(/,
        'zaman asiminda bekleyen istek gorunur bir hata ile reddedilmeli'
    );
});

test('no server-supplied free text reaches an HTML sink unencoded', () => {
    // Yalnizca HTML uretilen satirlar denetlenir. appConfirm/appAlert mesajlari
    // innerText ile yazildigi icin duz metin baglamidir ve XSS sink'i degildir.
    //
    // Bu test onceden yalnizca `item|d|grp|group.urun_adi` kalibini ariyordu.
    // Musteri menusundeki kartlar degiskeni `prod` ve `cat` olarak adlandirdigi
    // icin sekiz sink denetimin disinda kalmisti; `gorsel_url` de hic kapsanmiyordu.
    // Sonuc: yoneticinin girdigi bir urun adi, QR okutan her musterinin
    // tarayicisinda calisabilen bir `onerror` niteligine donusebiliyordu.
    // Kalip artik degisken adina bakmiyor, alan adina bakiyor.
    const alanlar = 'urun_adi|kategori_adi|gorsel_url|aciklama|urun_notu|masa_no|garson_adi';
    const pattern = new RegExp(`\\$\\{\\s*([A-Za-z_$][\\w$]*)\\.(${alanlar})\\s*(\\|\\|[^}]*)?\\}`, 'g');

    for (const file of ['static/js/app.js', 'static/js/waiter.js',
                        'static/js/kitchen.js', 'static/js/kasa.js', 'static/js/admin.js']) {
        const offenders = [];

        stripComments(read(file)).split('\n').forEach((line, index) => {
            if (!/<[a-zA-Z/]/.test(line)) return;
            pattern.lastIndex = 0;
            let match;
            while ((match = pattern.exec(line)) !== null) {
                const alan = `${match[1]}.${match[2]}`;
                const oncesi = line.slice(0, match.index);
                // `escapeHtml(...)` metin baglami icin, `safeImageUrl(...)` ise
                // `src` gibi URL baglamlari icin kabul edilir.
                if (oncesi.includes(`escapeHtml(${alan}`)) continue;
                if (oncesi.includes(`safeImageUrl(${alan}`)) continue;
                offenders.push(`${index + 1}: ${alan}`);
            }
        });

        assert.deepEqual(
            offenders,
            [],
            `${file}: HTML icine escape edilmemis sunucu metni girmis`
        );
    }
});

test('image urls from the admin panel are restricted to safe schemes', () => {
    // `src` bir URL baglami: kacis, oznitelikten kacmayi engeller ama
    // `javascript:` veya protokol-goreli `//evil.com` gibi degerleri engellemez.
    const source = read('static/js/app.js');
    assert.match(source, /function safeImageUrl\(/);

    const sandbox = {
        escapeHtml: value => String(value ?? '').replace(/[&<>"']/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[character]))
    };
    const govde = source.slice(source.indexOf('function safeImageUrl('));
    vm.createContext(sandbox);
    new vm.Script(govde.slice(0, govde.indexOf('\n}') + 2)).runInContext(sandbox);

    // İzin verilenler
    assert.equal(sandbox.safeImageUrl('/static/img/a.png'), '/static/img/a.png');
    assert.equal(sandbox.safeImageUrl('https://cdn.example/a.png'), 'https://cdn.example/a.png');

    // Reddedilenler
    for (const kotu of ['javascript:alert(1)', 'data:text/html,<script>',
                        '//evil.com/a.png', '/\\evil.com/a.png', 'x" onerror="kotu']) {
        assert.equal(sandbox.safeImageUrl(kotu), '', `reddedilmeli: ${kotu}`);
    }
});

test('staff panels send their token when reading the table list', () => {
    // /api/masalar artik goz atma bilgisini yalnizca personele donuyor;
    // panellerin istegi token ile gitmezse gosterge sessizce bosalir.
    const source = read('static/js/staff_auth.js');
    assert.match(
        source,
        /pathname === '\/api\/masalar' && method === 'GET'/,
        'staff_auth.js GET /api/masalar icin token eklemiyor'
    );
});
