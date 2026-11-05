/* NetSync camera-only capture.
   - Phones/tablets: the <input capture="environment"> opens the device camera app.
   - Laptops/desktops: browsers ignore `capture` and show a file picker, so we open
     a live webcam (getUserMedia) instead. No file picker is ever shown for
     camera-only buttons. If the webcam is blocked or missing, the user sees a
     message - there is no fallback to choosing a file. */
(function () {
    'use strict';
    var ua = navigator.userAgent || '';

    /* Is this a phone / tablet?  The user-agent alone is not enough: when a phone browser is set to
       "Desktop site" (Chrome, Samsung Internet, Xiaomi, Oppo, Vivo, Huawei, Opera, Firefox ...) it
       reports a desktop user-agent (X11 Linux / Windows / Macintosh), and without this check NetSync
       would open the laptop webcam window, which fails on http:// and never reaches the camera app.
       So we also look at the hardware: a touch screen whose main pointer is a finger, on a small
       physical screen. screen.width is the real device size and does not change with "Desktop site". */
    function mq(q) { try { return !!(window.matchMedia && window.matchMedia(q).matches); } catch (e) { return false; } }
    var shortSide = Math.min(screen.width || 0, screen.height || 0);
    var touchOnly = (navigator.maxTouchPoints || 0) > 0 && (mq('(pointer: coarse)') || mq('(hover: none)'));
    var isMobile = /Android|iPhone|iPad|iPod|Mobile|Silk|Tablet|HarmonyOS|MIUI|OPPO|vivo|SM-[A-Z]\d/i.test(ua) ||
        (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1) ||     // iPadOS reports as a Mac
        (touchOnly && shortSide > 0 && shortSide <= 1100);               // phone / tablet in "Desktop site" mode

    var css = '' +
        '.nsc-back{position:fixed;inset:0;z-index:10000;background:rgba(8,14,24,.82);display:flex;align-items:center;justify-content:center;padding:16px}' +
        '.nsc-back[hidden]{display:none}' +
        '.nsc-box{width:min(720px,100%);background:#fff;color:#14202e;border-radius:16px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.45);font-family:inherit}' +
        '.nsc-head{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #e3e9f0;font-weight:700}' +
        '.nsc-x{border:0;background:transparent;font-size:18px;cursor:pointer;color:inherit}' +
        '.nsc-stage{position:relative;background:#000;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center}' +
        '.nsc-stage video{width:100%;height:100%;object-fit:cover}' +
        '.nsc-msg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;color:#fff;font-size:14px;line-height:1.5}' +
        '.nsc-msg[hidden]{display:none}' +
        '.nsc-actions{display:flex;gap:10px;justify-content:flex-end;padding:12px 16px}' +
        '.nsc-btn{border:0;border-radius:10px;padding:10px 18px;font:inherit;font-weight:700;cursor:pointer}' +
        '.nsc-cancel{background:#eef2f6;color:#14202e}' +
        '.nsc-snap{background:#1c7ed6;color:#fff}' +
        '.nsc-snap:disabled{opacity:.5;cursor:not-allowed}';
    var styleEl = document.createElement('style');
    styleEl.textContent = css;
    document.head.appendChild(styleEl);

    var modal, video, msg, snapBtn, stream = null, target = null;

    function build() {
        if (modal) return;
        modal = document.createElement('div');
        modal.className = 'nsc-back';
        modal.hidden = true;
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Take a photo');
        modal.innerHTML =
            '<div class="nsc-box">' +
            '<div class="nsc-head"><span><i class="fas fa-camera"></i> Take a photo</span>' +
            '<button type="button" class="nsc-x" aria-label="Close">&times;</button></div>' +
            '<div class="nsc-stage"><video autoplay playsinline muted></video>' +
            '<div class="nsc-msg" hidden></div></div>' +
            '<div class="nsc-actions">' +
            '<button type="button" class="nsc-btn nsc-cancel">Cancel</button>' +
            '<button type="button" class="nsc-btn nsc-snap" disabled><i class="fas fa-camera"></i> Capture</button>' +
            '</div></div>';
        document.body.appendChild(modal);
        video = modal.querySelector('video');
        msg = modal.querySelector('.nsc-msg');
        snapBtn = modal.querySelector('.nsc-snap');
        modal.querySelector('.nsc-x').addEventListener('click', close);
        modal.querySelector('.nsc-cancel').addEventListener('click', close);
        snapBtn.addEventListener('click', snap);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal && !modal.hidden) close();
        });
    }

    function stop() {
        if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
        if (video) video.srcObject = null;
    }

    function close() {
        stop();
        if (modal) modal.hidden = true;
        document.body.style.overflow = '';
        target = null;
    }

    function showMsg(text) { msg.textContent = text; msg.hidden = false; snapBtn.disabled = true; }

    function snap() {
        if (!video || !video.videoWidth || !target) return;
        var c = document.createElement('canvas');
        c.width = video.videoWidth;
        c.height = video.videoHeight;
        c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
        var input = target;
        c.toBlob(function (blob) {
            if (!blob) { showMsg('Could not capture the photo. Please try again.'); return; }
            var file = new File([blob], 'camera_' + Date.now() + '.jpg', { type: 'image/jpeg' });
            var dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            close();
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }, 'image/jpeg', 0.92);
    }

    /* Open the camera for a file input. On phones this opens the camera app;
       on laptops it opens the live webcam window. Never a file picker. */
    function open(input) {
        if (!input) return;
        if (isMobile) {
            input.setAttribute('capture', 'environment');
            input.click();
            return;
        }
        build();
        target = input;
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        msg.hidden = true;
        snapBtn.disabled = true;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showMsg('Camera access is not available in this browser. Open NetSync over HTTPS (or localhost) in a browser with camera support, or use your phone.');
            return;
        }
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
            .then(function (s) {
                if (modal.hidden) { s.getTracks().forEach(function (t) { t.stop(); }); return; }
                stream = s;
                video.srcObject = s;
                video.onloadedmetadata = function () { snapBtn.disabled = false; };
            })
            .catch(function (err) {
                var denied = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
                showMsg(denied
                    ? 'Camera permission was blocked. Allow camera access for this site in your browser, then try again.'
                    : 'No camera was found on this device. Photos must be taken with a camera.');
            });
    }

    window.NetSyncCamera = { open: open, isMobile: isMobile };
})();
