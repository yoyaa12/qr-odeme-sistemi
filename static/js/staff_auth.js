(function () {
    'use strict';

    const STORAGE_KEY = 'qrStaffAuthSessionV1';
    const nativeFetch = window.fetch.bind(window);
    const allowedRoles = new Set(
        String(document.body.dataset.staffRoles || '')
            .split(',')
            .map(role => role.trim())
            .filter(Boolean)
    );
    const uiMode = document.body.dataset.staffAuthUi || 'generic';

    let currentSession = null;
    let sessionWaiters = [];
    let loginRequested = false;
    let initialValidation = null;
    let sessionGeneration = 0;

    function roleIsAllowed(role) {
        return allowedRoles.size === 0 || allowedRoles.has(role);
    }

    function isUsableSession(value) {
        return Boolean(
            value &&
            typeof value.accessToken === 'string' &&
            value.accessToken.length > 20 &&
            Number.isFinite(value.expiresAt) &&
            value.expiresAt > Date.now() &&
            value.user &&
            typeof value.user === 'object' &&
            roleIsAllowed(value.user.rol)
        );
    }

    function readStoredSession() {
        try {
            const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
            return isUsableSession(parsed) ? parsed : null;
        } catch (error) {
            return null;
        }
    }

    function persistSession(session) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
        } catch (error) {
            // The in-memory token remains usable when storage is unavailable.
        }
    }

    function resolveSessionWaiters() {
        const waiters = sessionWaiters;
        sessionWaiters = [];
        waiters.forEach(waiter => {
            if (waiter.timerId) clearTimeout(waiter.timerId);
            waiter.resolve(currentSession);
        });
    }

    function emit(name, detail) {
        window.dispatchEvent(new CustomEvent(name, { detail }));
    }

    function hideGenericLogin() {
        const modal = document.getElementById('staffAuthModal');
        if (modal) modal.style.display = 'none';
    }

    function clearSession(options = {}) {
        sessionGeneration += 1;
        currentSession = null;
        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch (error) { }
        if (options.notify !== false) {
            emit('staff-auth-cleared', {});
            requestAuthentication();
        }
    }

    function normalizeLoginResponse(response, explicitUser) {
        const user = explicitUser || response.user || response.garson;
        const expiresIn = Number(response.expires_in);
        const token = response.access_token;
        if (
            !user ||
            typeof token !== 'string' ||
            token.length <= 20 ||
            !Number.isFinite(expiresIn) ||
            expiresIn < 60
        ) {
            throw new Error('Sunucudan gecersiz yanit alindi.');
        }
        if (!roleIsAllowed(user.rol)) {
            throw new Error(`Bu sayfaya erisim yetkiniz bulunmamaktadir (Rolunuz: ${user.rol}).`);
        }
        return {
            accessToken: token,
            expiresAt: Date.now() + (expiresIn * 1000),
            user: user
        };
    }

    function setSessionFromLogin(response, explicitUser) {
        const session = normalizeLoginResponse(response, explicitUser);
        sessionGeneration += 1;
        currentSession = session;
        loginRequested = false;
        persistSession(session);
        hideGenericLogin();
        resolveSessionWaiters();
        emit('staff-authenticated', { user: session.user });
        return session;
    }

    function ensureGenericLoginModal() {
        let modal = document.getElementById('staffAuthModal');
        if (modal) return modal;

        const style = document.createElement('style');
        style.textContent = `
            .staff-auth-overlay { position: fixed; inset: 0; z-index: 20000; display: none; align-items: center; justify-content: center; padding: 18px; background: rgba(2, 6, 23, 0.98); }
            .staff-auth-card { width: min(420px, 100%); padding: 24px; border-radius: 14px; border: 1px solid #334155; background: #0f172a; color: #f8fafc; box-shadow: 0 8px 20px rgba(0,0,0,0.28); }
            .staff-auth-card h2 { margin: 0 0 8px; font-size: 1.35rem; }
            .staff-auth-card p { margin: 0 0 18px; color: #94a3b8; font-size: 0.9rem; }
            .staff-auth-card label { display: block; margin: 12px 0 6px; font-size: 0.85rem; font-weight: 700; }
            .staff-auth-card input { width: 100%; box-sizing: border-box; padding: 12px; border-radius: 9px; border: 1px solid #475569; background: #111827; color: #fff; }
            .staff-auth-submit { width: 100%; margin-top: 18px; padding: 12px; border: 0; border-radius: 9px; background: #f59e0b; color: #111827; font-weight: 800; cursor: pointer; transition: opacity 0.15s ease; }
            .staff-auth-submit:disabled { opacity: 0.55; cursor: wait; }
            .staff-auth-error { display: none; margin-top: 12px; padding: 10px; border: 1px solid #7f1d1d; border-radius: 8px; background: #450a0a; color: #fecaca; font-size: 0.85rem; }
            .staff-auth-home { display: block; margin-top: 14px; text-align: center; color: #93c5fd; font-size: 0.85rem; }
        `;
        document.head.appendChild(style);

        modal = document.createElement('div');
        modal.id = 'staffAuthModal';
        modal.className = 'staff-auth-overlay';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML = `
            <div class="staff-auth-card">
                <h2>🔐 Personel Girişi</h2>
                <p>Bu operasyon panelini kullanmak için personel hesabınızla giriş yapın.</p>
                <form id="staffAuthForm">
                    <label for="staffAuthUsername">Kullanıcı adı</label>
                    <input id="staffAuthUsername" name="username" type="text" autocomplete="username" maxlength="50" required>
                    <label for="staffAuthPin">PIN</label>
                    <input id="staffAuthPin" name="pin" type="password" inputmode="numeric" autocomplete="current-password" pattern="[0-9]{6}" maxlength="6" required>
                    <button id="staffAuthSubmit" class="staff-auth-submit" type="submit">Giriş Yap</button>
                    <div id="staffAuthError" class="staff-auth-error" role="alert"></div>
                    <a class="staff-auth-home" href="/">Ana ekrana dön</a>
                </form>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector('#staffAuthForm').addEventListener('submit', async event => {
            event.preventDefault();
            const usernameInput = modal.querySelector('#staffAuthUsername');
            const pinInput = modal.querySelector('#staffAuthPin');
            const button = modal.querySelector('#staffAuthSubmit');
            const errorBox = modal.querySelector('#staffAuthError');
            errorBox.style.display = 'none';
            button.disabled = true;
            try {
                const response = await nativeFetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        kullanici_adi: usernameInput.value.trim(),
                        sifre: pinInput.value
                    })
                });
                let payload = {};
                try {
                    payload = await response.json();
                } catch (error) { }
                if (!response.ok) {
                    throw new Error(payload.detail || 'Personel girişi başarısız.');
                }
                setSessionFromLogin(payload, payload.user);
                pinInput.value = '';
            } catch (error) {
                pinInput.value = '';
                errorBox.textContent = error.message || 'Personel girişi başarısız.';
                errorBox.style.display = 'block';
            } finally {
                button.disabled = false;
            }
        });
        return modal;
    }

    function showAuthenticationUi() {
        if (uiMode === 'external') {
            emit('staff-auth-required', {});
            return;
        }
        const modal = ensureGenericLoginModal();
        modal.style.display = 'flex';
        const username = modal.querySelector('#staffAuthUsername');
        if (username) username.focus();
    }

    function requestAuthentication() {
        if (loginRequested) return;
        loginRequested = true;
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', showAuthenticationUi, { once: true });
        } else {
            showAuthenticationUi();
        }
    }

    // Oturum beklerken sinirsiz askida kalinmaz. Personel giris yapmazsa bekleyen
    // istek bu sure sonunda gorunur bir hata ile reddedilir; aksi halde cagiran
    // kod (ornegin bir fetch) sessizce sonsuza kadar bekler ve kullaniciya
    // "hicbir sey olmuyor" gibi gorunur.
    const SESSION_WAIT_TIMEOUT_MS = 120000;

    async function waitForSession() {
        if (initialValidation) await initialValidation;
        if (isUsableSession(currentSession)) return currentSession;
        clearSession({ notify: false });
        requestAuthentication();
        return new Promise((resolve, reject) => {
            const waiter = { resolve, reject, timerId: null };
            waiter.timerId = setTimeout(() => {
                const index = sessionWaiters.indexOf(waiter);
                if (index !== -1) sessionWaiters.splice(index, 1);
                reject(new Error('Personel oturumu açılmadığı için istek gönderilemedi.'));
            }, SESSION_WAIT_TIMEOUT_MS);
            sessionWaiters.push(waiter);
        });
    }

    function requestDetails(input, init) {
        try {
            const rawUrl = input instanceof Request ? input.url : String(input);
            const url = new URL(rawUrl, window.location.origin);
            const method = String(
                (init && init.method) ||
                (input instanceof Request ? input.method : 'GET')
            ).toUpperCase();
            return { url, method };
        } catch (error) {
            return null;
        }
    }

    function requiresStaffToken(pathname, method) {
        if (pathname === '/api/auth/me' && method === 'GET') return true;
        if (pathname.startsWith('/api/admin/')) return true;
        if (pathname === '/api/garsonlar' && method === 'GET') return true;
        if (pathname === '/api/garson/ban-device' && method === 'POST') return true;
        if (pathname === '/api/siparisler' && method === 'GET') return true;
        if (/^\/api\/siparisler\/\d+\/durum$/.test(pathname) && method === 'PATCH') return true;
        if (/^\/api\/siparisler\/\d+$/.test(pathname) && method === 'PUT') return true;
        // Masa listesi public'tir, ancak "hangi masa menuye bakiyor" bilgisi
        // yalnizca kimligi dogrulanmis personele doner. Panellerin bu bilgiyi
        // gorebilmesi icin istek token ile gonderilir.
        if (pathname === '/api/masalar' && method === 'GET') return true;
        if (pathname === '/api/masalar/move' && method === 'POST') return true;
        if (/^\/api\/masalar\/\d+\/clear$/.test(pathname) && method === 'POST') return true;
        if (pathname === '/api/masalar/all-dynamic-qrs' && method === 'GET') return true;
        if (pathname === '/api/masalar/all-tahsilatlar' && method === 'GET') return true;
        if (/^\/api\/masalar\/\d+\/tahsilat$/.test(pathname) && method === 'POST') return true;
        if (/^\/api\/masalar\/\d+\/dynamic-qr$/.test(pathname) && method === 'GET') return true;
        return false;
    }

    window.fetch = async function staffAuthenticatedFetch(input, init = {}) {
        const details = requestDetails(input, init);
        const isSameOrigin = details && details.url.origin === window.location.origin;
        if (!isSameOrigin || !requiresStaffToken(details.url.pathname, details.method)) {
            return nativeFetch(input, init);
        }

        const session = await waitForSession();
        const headers = new Headers(
            init.headers || (input instanceof Request ? input.headers : undefined)
        );
        headers.set('Authorization', `Bearer ${session.accessToken}`);
        const response = await nativeFetch(input, { ...init, headers });
        if (
            response.status === 401 &&
            currentSession &&
            currentSession.accessToken === session.accessToken
        ) {
            clearSession();
        }
        return response;
    };

    async function validateStoredSession(candidate) {
        const validationGeneration = sessionGeneration;
        if (!candidate) {
            requestAuthentication();
            return;
        }
        try {
            const response = await nativeFetch('/api/auth/me', {
                headers: { Authorization: `Bearer ${candidate.accessToken}` }
            });
            if (!response.ok) throw new Error('Stored token is invalid');
            const serverUser = await response.json();
            if (!roleIsAllowed(serverUser.rol)) throw new Error('Role is not allowed');
            if (sessionGeneration !== validationGeneration) return;
            currentSession = { ...candidate, user: serverUser };
            persistSession(currentSession);
            resolveSessionWaiters();
            emit('staff-authenticated', { user: serverUser });
        } catch (error) {
            if (sessionGeneration !== validationGeneration) return;
            clearSession({ notify: false });
            requestAuthentication();
        }
    }

    window.StaffAuth = Object.freeze({
        clearSession,
        getSession: () => currentSession,
        getToken: () => currentSession ? currentSession.accessToken : (readStoredSession() ? readStoredSession().accessToken : null),
        setSessionFromLogin,
        waitForSession
    });

    const storedCandidate = readStoredSession();
    initialValidation = validateStoredSession(storedCandidate).finally(() => {
        initialValidation = null;
    });
})();
