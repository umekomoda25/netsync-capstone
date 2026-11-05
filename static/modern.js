/* NetSync modern layer: toasts, entrance sequence, spotlight, progress animation */
(function () {
    'use strict';
    var root = document.documentElement;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---------- Toasts ---------- */
    var stack = null;
    var ICONS = { success: 'fa-circle-check', error: 'fa-triangle-exclamation', info: 'fa-bell', stock: 'fa-boxes-stacked' };
    var TITLES = { success: 'Done', error: 'Something went wrong', info: 'Notification', stock: 'Stock alert' };

    function getStack() {
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'ns-toasts';
            stack.setAttribute('aria-live', 'polite');
            document.body.appendChild(stack);
        }
        return stack;
    }
    function dismiss(el) {
        if (!el || el.classList.contains('out')) return;
        el.classList.add('out');
        setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
    }
    /* NSToast(message, { type: 'success'|'error'|'info'|'stock', title, link, icon, duration }) */
    window.NSToast = function (message, opts) {
        opts = opts || {};
        var type = opts.type || 'info';
        var dur = opts.duration || (type === 'error' ? 7000 : 5000);
        var el = document.createElement('div');
        el.className = 'ns-toast ' + type + (opts.link ? ' link' : '');
        el.setAttribute('role', type === 'error' ? 'alert' : 'status');
        el.style.setProperty('--dur', dur + 'ms');
        el.innerHTML =
            '<span class="ns-ico"><i class="fas ' + (opts.icon || ICONS[type] || ICONS.info) + '"></i></span>' +
            '<span class="ns-body"><span class="ns-title"></span><span class="ns-msg"></span></span>' +
            '<button type="button" class="ns-x" aria-label="Dismiss"><i class="fas fa-xmark"></i></button>' +
            '<span class="ns-timer"></span>';
        el.querySelector('.ns-title').textContent = opts.title || TITLES[type] || '';
        el.querySelector('.ns-msg').textContent = message;
        el.querySelector('.ns-x').addEventListener('click', function (e) { e.stopPropagation(); dismiss(el); });
        if (opts.link) el.addEventListener('click', function () { window.location.href = opts.link; });
        var s = getStack();
        s.appendChild(el);
        while (s.children.length > 4) dismiss(s.firstChild);
        var timer = setTimeout(function () { dismiss(el); }, dur);
        el.addEventListener('mouseenter', function () { clearTimeout(timer); });
        el.addEventListener('mouseleave', function () { timer = setTimeout(function () { dismiss(el); }, 1800); });
        return el;
    };

    function ready(fn) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn();
    }

    ready(function () {
        /* Flash messages become toasts */
        document.querySelectorAll('.flash-success, .flash-error, .flash-msg').forEach(function (el) {
            var type = el.classList.contains('flash-error') ? 'error' : 'success';
            var text = (el.textContent || '').trim();
            el.classList.add('ns-hidden');
            if (text) window.NSToast(text, { type: type });
        });

        /* One entrance sequence per page load */
        if (!reduce) {
            root.classList.add('ns-ready');
            setTimeout(function () { root.classList.remove('ns-ready'); }, 1400);
        }

        /* Cursor spotlight on project rows */
        if (window.matchMedia && window.matchMedia('(hover: hover)').matches) {
            document.addEventListener('pointermove', function (e) {
                var card = e.target.closest && e.target.closest('.project-card');
                if (!card) return;
                var r = card.getBoundingClientRect();
                card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
                card.style.setProperty('--my', (e.clientY - r.top) + 'px');
            }, { passive: true });
        }
    });
})();
