const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repositoryRoot = path.resolve(__dirname, '..', '..');

function read(relativePath) {
    return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8');
}

function assertAuthLoadsBefore(templatePath, pageScript, expectedRole) {
    const source = read(templatePath);
    const authIndex = source.indexOf('/static/js/staff_auth.js');
    const pageIndex = source.indexOf(`/static/js/${pageScript}`);

    assert.match(source, new RegExp(`data-staff-roles="${expectedRole}"`));
    assert.notEqual(authIndex, -1, `${templatePath} must load staff_auth.js`);
    assert.notEqual(pageIndex, -1, `${templatePath} must load ${pageScript}`);
    assert.ok(authIndex < pageIndex, 'staff auth must wrap fetch before page code runs');
}

test('every staff panel loads the bearer-token helper with its real role', () => {
    assertAuthLoadsBefore('templates/admin.html', 'admin.js', 'admin');
    assertAuthLoadsBefore('templates/garson.html', 'waiter.js', 'garson');
    assertAuthLoadsBefore('templates/mutfak.html', 'kitchen.js', 'mutfak');
    assertAuthLoadsBefore('templates/kasa.html', 'kasa.js', 'kasa');
});

test('staff helper validates restored tokens and sends bearer authorization', () => {
    const source = read('static/js/staff_auth.js');

    assert.match(source, /sessionStorage\.setItem\(STORAGE_KEY/);
    assert.match(source, /nativeFetch\('\/api\/auth\/me'/);
    assert.match(source, /headers\.set\('Authorization', `Bearer \$\{session\.accessToken\}`\)/);
    assert.match(source, /response\.status === 401/);
    assert.match(source, /clearSession\(\)/);
    assert.doesNotMatch(source, /localStorage\.(?:getItem|setItem)/);
});

test('staff helper covers every route protected in the current HTTP batch', () => {
    const source = read('static/js/staff_auth.js');

    for (const route of [
        '/api/admin/',
        '/api/garsonlar',
        '/api/garson/ban-device',
        '/api/siparisler',
        '/api/masalar/move',
        '/api/masalar/all-dynamic-qrs'
    ]) {
        assert.ok(source.includes(route), `missing protected route contract: ${route}`);
    }
    assert.match(source, /siparisler\\\/\\d\+\\\/durum/);
    assert.match(source, /masalar\\\/\\d\+\\\/clear/);
    assert.match(source, /masalar\\\/\\d\+\\\/dynamic-qr/);
});

test('public landing page cannot mint a physical-presence token', () => {
    const source = read('templates/index.html');

    assert.doesNotMatch(source, /fetch\(`\/api\/masalar\/\$\{masaId\}\/dynamic-qr`\)/);
    assert.match(source, /window\.location\.href = `\/menu\?masa=\$\{masaId\}`/);
});

test('waiter identity is restored from StaffAuth, not browser-trusted local data', () => {
    const source = read('static/js/waiter.js');

    assert.match(source, /StaffAuth\.getSession\(\)/);
    assert.match(source, /StaffAuth\.setSessionFromLogin\(data, person\)/);
    assert.doesNotMatch(source, /localStorage\.getItem\('activeGarsonSession'\)/);
    assert.doesNotMatch(source, /localStorage\.setItem\('activeGarsonSession'/);
});

test('waiter preserves a pending action before login dispatches authenticated events', () => {
    const source = read('static/js/waiter.js');
    const captureIndex = source.indexOf('const actionToExecute = pendingActionCallback;');
    const loginIndex = source.indexOf('window.StaffAuth.setSessionFromLogin(data, person);');

    assert.notEqual(captureIndex, -1, 'pending action callback must be captured');
    assert.notEqual(loginIndex, -1, 'staff login must install the signed session');
    assert.ok(captureIndex < loginIndex, 'authenticated event dispatch must not clear the pending action first');
});

test('stale authentication responses cannot clear or replace a newer session', () => {
    const source = read('static/js/staff_auth.js');
    const generationGuards = source.match(/sessionGeneration !== validationGeneration/g) || [];
    const generationAdvances = source.match(/sessionGeneration \+= 1/g) || [];

    assert.match(source, /let sessionGeneration = 0;/);
    assert.match(
        source,
        /response\.status === 401\s*&&\s*currentSession\s*&&\s*currentSession\.accessToken === session\.accessToken/
    );
    assert.ok(generationAdvances.length >= 2, 'login and clear operations must advance the session generation');
    assert.ok(generationGuards.length >= 2, 'stored-session success and failure paths both need generation guards');
});

test('staff login UI uses an in-app modal and avoids prohibited heavy effects', () => {
    const source = read('static/js/staff_auth.js');

    assert.doesNotMatch(source, /\b(?:alert|confirm|prompt)\s*\(/);
    assert.doesNotMatch(source, /backdrop-filter\s*:/);
    assert.doesNotMatch(source, /transition\s*:\s*all\b/);
    assert.match(source, /id = 'staffAuthModal'/);
    assert.match(source, /textContent = error\.message/);
});
