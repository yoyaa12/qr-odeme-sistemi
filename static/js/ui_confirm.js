/**
 * Uygulama geneli onay kutusu (native confirm() yerine).
 *
 * Neden: Chrome, bir sayfa art arda diyalog acinca kullaniciya "bu sayfanin ek
 * iletisim kutulari olusturmasini engelle" secenegi sunar. Isaretlenirse
 * confirm() hicbir sey gostermeden aninda false doner ve islem sessizce iptal
 * olur -- kullaniciya butona bastigi halde "hicbir sey olmuyor" gibi gorunur.
 * Masa kapatma, tahsilat, cihaz banlama, urun silme gibi islemler tarayicinin
 * diyalog politikasina bagli olmamali.
 *
 * Kullanim:  if (!await appConfirm('Emin misiniz?')) return;
 */
(function () {
    'use strict';

    const MODAL_ID = 'appConfirmModal';

    function appConfirm(message, options = {}) {
        return new Promise(resolve => {
            const existing = document.getElementById(MODAL_ID);
            if (existing) existing.remove();

            const overlay = document.createElement('div');
            overlay.id = MODAL_ID;
            overlay.className = 'modal-overlay active';
            overlay.style.zIndex = '15000';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.innerHTML = `
                <div class="modal-content" style="max-width: 460px;">
                    <div class="modal-header"><h3 id="appConfirmTitle"></h3></div>
                    <div id="appConfirmMsg" style="padding:16px 4px; font-size:0.95rem; line-height:1.55; color:#e2e8f0;"></div>
                    <div style="display:flex; gap:10px; margin-top:6px;">
                        <button type="button" id="appConfirmCancel" class="btn-add"
                            style="flex:1; justify-content:center; background:#334155;"></button>
                        <button type="button" id="appConfirmOk" class="btn-add"
                            style="flex:1; justify-content:center; background:linear-gradient(135deg,#ef4444,#b91c1c);"></button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);

            // Metin olarak yazilir: mesaj icindeki masa/urun adi HTML olarak yorumlanmaz.
            overlay.querySelector('#appConfirmTitle').innerText = options.title || '⚠️ Onay Gerekiyor';
            overlay.querySelector('#appConfirmMsg').innerText = message;
            overlay.querySelector('#appConfirmOk').innerText = options.okText || 'Evet, onaylıyorum';
            overlay.querySelector('#appConfirmCancel').innerText = options.cancelText || 'Vazgeç';

            const finish = (result) => {
                document.removeEventListener('keydown', onKey, true);
                overlay.remove();
                resolve(result);
            };

            // Capture asamasinda dinlenir: panellerin genel Escape / F-tusu
            // kisayollari bu modal acikken devreye girmemeli.
            const onKey = (e) => {
                if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(false); return; }
                if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); finish(true); return; }
                if (/^F\d+$/.test(e.key)) { e.preventDefault(); e.stopPropagation(); }
            };

            overlay.querySelector('#appConfirmOk').addEventListener('click', () => finish(true));
            overlay.querySelector('#appConfirmCancel').addEventListener('click', () => finish(false));
            overlay.addEventListener('click', (e) => { if (e.target === overlay) finish(false); });
            document.addEventListener('keydown', onKey, true);

            setTimeout(() => {
                const ok = overlay.querySelector('#appConfirmOk');
                if (ok) ok.focus();
            }, 0);
        });
    }

    const ALERT_ID = 'appAlertModal';

    /**
     * Uygulama geneli bilgi/hata kutusu (native alert() yerine).
     *
     * alert() de confirm() ile ayni tarayici diyalog politikasina tabidir:
     * kullanici "ek diyalog gosterme" derse hata mesaji hic gorunmez ve islem
     * sessizce basarisiz olmus gibi durur. Para ve sipariş akislarinda hatanin
     * gorunur olmasi zorunlu oldugu icin uygulama ici modal kullanilir.
     *
     * Kullanim:  await appAlert('Tahsilat yapilamadi.');
     */
    function appAlert(message, options = {}) {
        return new Promise(resolve => {
            const existing = document.getElementById(ALERT_ID);
            if (existing) existing.remove();

            const overlay = document.createElement('div');
            overlay.id = ALERT_ID;
            overlay.className = 'modal-overlay active';
            overlay.style.zIndex = '15001';
            overlay.setAttribute('role', 'alertdialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.innerHTML = `
                <div class="modal-content" style="max-width: 460px;">
                    <div class="modal-header"><h3 id="appAlertTitle"></h3></div>
                    <div id="appAlertMsg" style="padding:16px 4px; font-size:0.95rem; line-height:1.55; color:#e2e8f0;"></div>
                    <div style="display:flex; gap:10px; margin-top:6px;">
                        <button type="button" id="appAlertOk" class="btn-add"
                            style="flex:1; justify-content:center;"></button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);

            // Metin olarak yazilir: sunucudan gelen hata metni HTML olarak yorumlanmaz.
            overlay.querySelector('#appAlertTitle').innerText = options.title || 'Bilgi';
            overlay.querySelector('#appAlertMsg').innerText = message;
            overlay.querySelector('#appAlertOk').innerText = options.okText || 'Tamam';

            const finish = () => {
                document.removeEventListener('keydown', onKey, true);
                overlay.remove();
                resolve();
            };

            const onKey = (e) => {
                if (e.key === 'Escape' || e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    finish();
                    return;
                }
                if (/^F\d+$/.test(e.key)) { e.preventDefault(); e.stopPropagation(); }
            };

            overlay.querySelector('#appAlertOk').addEventListener('click', finish);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) finish(); });
            document.addEventListener('keydown', onKey, true);

            setTimeout(() => {
                const ok = overlay.querySelector('#appAlertOk');
                if (ok) ok.focus();
            }, 0);
        });
    }

    window.appConfirm = appConfirm;
    window.appAlert = appAlert;
}());
