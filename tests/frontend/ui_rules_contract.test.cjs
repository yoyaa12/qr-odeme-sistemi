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

test('no product name reaches an HTML sink unencoded', () => {
    // Yalnizca HTML uretilen satirlar denetlenir. appConfirm/appAlert mesajlari
    // innerText ile yazildigi icin duz metin baglamidir ve XSS sink'i degildir.
    const pattern = /\$\{\s*(?:item|d|grp|group)\.urun_adi\s*\}/;

    for (const file of ['static/js/app.js', 'static/js/waiter.js',
                        'static/js/kitchen.js', 'static/js/kasa.js']) {
        const offenders = stripComments(read(file))
            .split('\n')
            .map((line, index) => ({ line, lineNo: index + 1 }))
            .filter(({ line }) => pattern.test(line) && /<[a-zA-Z/]/.test(line));

        assert.deepEqual(
            offenders.map(o => o.lineNo),
            [],
            `${file}: HTML icine escape edilmemis urun_adi girmis`
        );
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
