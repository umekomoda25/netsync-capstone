/* NetSync device adapter. Runs in <head> on every page, before first paint.
   Sets classes on <html> so CSS can react to the REAL device and not only to the window width:
     ns-touch         finger is the main pointer (phone / tablet / touch tablet)
     ns-handheld      small physical screen (phone or small tablet)
     ns-desktop-site  a handheld that is showing the "Desktop site" (window much wider than the screen)
   Also: fixes broken photos. */
(function () {
    'use strict';
    var d = document.documentElement;
    function mq(q) { try { return !!(window.matchMedia && window.matchMedia(q).matches); } catch (e) { return false; } }

    function classify() {
        var sw = Math.min(screen.width || 0, screen.height || 0);          // real device size, unaffected by "Desktop site"
        var swLong = Math.max(screen.width || 0, screen.height || 0);
        var touch = (navigator.maxTouchPoints || 0) > 0 && (mq('(pointer: coarse)') || mq('(hover: none)'));
        var handheld = touch && sw > 0 && sw <= 900;
        var wide = window.innerWidth > (screen.width || window.innerWidth) * 1.25 && window.innerWidth > 900;
        d.classList.toggle('ns-touch', touch);
        d.classList.toggle('ns-handheld', handheld);
        d.classList.toggle('ns-desktop-site', handheld && wide);
    }
    classify();
    window.addEventListener('resize', classify);
    window.addEventListener('orientationchange', classify);

    function ready(fn) { if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

    ready(function () {
    });

    /* Photos that fail to load (deleted file, bad upload): show a tidy note instead of a broken-image icon. */
    document.addEventListener('error', function (e) {
        var img = e.target;
        if (!img || img.tagName !== 'IMG') return;
        var thumb = img.closest && img.closest('.log-thumb');
        if (thumb) { thumb.classList.add('is-broken'); thumb.disabled = true; return; }
        if (img.classList.contains('log-photo')) {
            img.classList.add('is-broken');
            if (!img.nextElementSibling || !img.nextElementSibling.classList.contains('log-note-broken')) {
                var n = document.createElement('div');
                n.className = 'log-note-broken'; n.textContent = 'Photo unavailable';
                img.parentNode.insertBefore(n, img.nextSibling);
            }
        }
    }, true);
})();
