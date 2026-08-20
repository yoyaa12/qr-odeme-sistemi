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

// Bir masanın adisyonu kapanınca sunucu o masanın müşteri oturumlarını iptal
// eder. Bundan sonra sipariş isteği, gövdedeki 6 haneli koda hiç bakılmadan 401
// ile döner: kimlik dependency'si controller'dan önce çalışır. Dolayısıyla
// istemcinin kurtarma yolu "kodu tekrar gönder" değil, "kodla yeni oturum al,
// sonra siparişi tekrarla" olmak zorundadır.

test('an order rejected with 401 opens the security-code screen', () => {
    const submitBody = appSource.slice(
        appSource.indexOf('async function executeOrderSubmit'),
        appSource.indexOf('function openFirstOrderPINModal')
    );

    assert.match(
        submitBody,
        /res\.status === 401/,
        'a revoked session must be recognised, not shown as a generic error'
    );
    assert.match(
        submitBody,
        /openFirstOrderPINModal/,
        '401 must lead to the 6-digit code screen'
    );
});

test('the code screen mints a new session before retrying the order', () => {
    const pinBody = appSource.slice(
        appSource.indexOf('async function submitFirstOrderPIN'),
        appSource.length
    );

    const refreshIndex = pinBody.indexOf('refreshCustomerSession');
    const retryIndex = pinBody.indexOf('executeOrderSubmit');

    assert.ok(refreshIndex !== -1, 'the code must be exchanged for a session');
    assert.ok(retryIndex !== -1, 'the order must be retried afterwards');
    assert.ok(
        refreshIndex < retryIndex,
        'retrying before refreshing the session would just produce another 401'
    );
});

test('a failed code entry does not retry the order', () => {
    const pinBody = appSource.slice(
        appSource.indexOf('async function submitFirstOrderPIN')
    );

    assert.match(
        pinBody,
        /if\s*\(!sessionReady\)\s*\{[\s\S]*?return;/,
        'an unverified code must stop the flow instead of falling through'
    );
});

test('session refresh stores the new token and rebinds the live socket', () => {
    const refreshBody = appSource.slice(
        appSource.indexOf('async function refreshCustomerSession'),
        appSource.indexOf('async function submitFirstOrderPIN')
    );

    assert.match(refreshBody, /\/verify-qr/, 'the code goes to the verification endpoint');
    assert.match(
        refreshBody,
        /localStorage\.setItem\('qr_session_token_'/,
        'the fresh session token must replace the revoked one'
    );
    assert.match(
        refreshBody,
        /socket\.auth\s*=/,
        'the realtime connection must carry the new session'
    );
    assert.match(
        refreshBody,
        /data\.valid/,
        'a rejected code must not be treated as success'
    );
});

test('a revoked session is dropped from storage instead of being resent', () => {
    const start = appSource.indexOf('async function checkActiveOrder');
    assert.ok(start !== -1, 'checkActiveOrder must exist');
    const checkBody = appSource.slice(start, start + 2000);

    assert.match(
        checkBody,
        /localStorage\.removeItem\('qr_session_token_'/,
        'a dead token must not linger in storage'
    );
});

test('the customer page loads a bumped app.js so the recovery flow reaches phones', () => {
    const menu = read('templates/menu.html');
    const match = menu.match(/\/static\/js\/app\.js\?v=(\d+)/);
    assert.ok(match, 'menu.html must load a versioned app.js');
    assert.ok(Number(match[1]) >= 84, 'the asset version must be bumped for the recovery flow');
});

// QR'daki kod istemcide saklanıp ilk siparişte otomatik gönderiliyor. Bu, "kod
// bazen soruluyor bazen sorulmuyor" davranışının tek sebebi: kod hâlâ
// geçerliyse ekran hiç çıkmıyor, eskimişse 403 gelip çıkıyor. Tesadüfen böyle
// çalışmasın diye sözleşme burada sabitleniyor.

test('the code from the QR link is kept for the first order', () => {
    const initBody = appSource.slice(0, appSource.indexOf('async function loadMenuData'));

    assert.match(
        initBody,
        /state\.currentTotpToken\s*=\s*tokenParam/,
        'the code in the QR URL must be retained for the first order'
    );
});

test('the retained code is attached to the order automatically', () => {
    const submitBody = appSource.slice(
        appSource.indexOf('async function executeOrderSubmit'),
        appSource.indexOf('function openFirstOrderPINModal')
    );

    assert.match(
        submitBody,
        /payload\.current_totp_token\s*=\s*state\.currentTotpToken/,
        'a customer who orders straight after scanning must not be asked to retype the code'
    );
});

test('the code is discarded once it has been spent', () => {
    const submitBody = appSource.slice(
        appSource.indexOf('async function executeOrderSubmit'),
        appSource.indexOf('function openFirstOrderPINModal')
    );

    assert.match(
        submitBody,
        /state\.currentTotpToken\s*=\s*null/,
        'the server marks the code used; keeping it client-side would resend a dead code'
    );
});

test('app.js parses as a script', () => {
    assert.doesNotThrow(() => new vm.Script(appSource, { filename: 'app.js' }));
});
