const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const helperPath = path.resolve(__dirname, '..', '..', 'static', 'js', 'security.js');
const securityText = require(helperPath);

test('escapeHtml encodes HTML-significant characters', () => {
    assert.equal(
        securityText.escapeHtml('&<>"\''),
        '&amp;&lt;&gt;&quot;&#39;'
    );
});

test('escapeHtml handles empty and non-string values', () => {
    assert.equal(securityText.escapeHtml(null), '');
    assert.equal(securityText.escapeHtml(undefined), '');
    assert.equal(securityText.escapeHtml(42), '42');
    assert.equal(securityText.escapeHtml(false), 'false');
});

test('security helper exposes the same API in a browser-like context', () => {
    const source = fs.readFileSync(helperPath, 'utf8');
    const browserContext = {};

    vm.runInNewContext(source, browserContext, { filename: helperPath });

    assert.equal(typeof browserContext.SecurityText.escapeHtml, 'function');
    assert.equal(browserContext.SecurityText.escapeHtml('<script>'), '&lt;script&gt;');
    assert.equal(
        browserContext.SecurityText.escapeHtml('<img src=x onerror="globalThis.pwned=true">'),
        '&lt;img src=x onerror=&quot;globalThis.pwned=true&quot;&gt;'
    );
});
