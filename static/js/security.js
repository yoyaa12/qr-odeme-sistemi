(function (root, factory) {
    const api = factory();

    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }

    if (root) {
        root.SecurityText = api;
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    const htmlEntities = Object.freeze({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    });

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, character => htmlEntities[character]);
    }

    return Object.freeze({ escapeHtml });
}));
