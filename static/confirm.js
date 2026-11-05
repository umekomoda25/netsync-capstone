/* NetSync confirmation dialogs.
   One shared, theme-aware dialog used for every save / delete / archive / restore /
   cancel / logout action, replacing the browser's plain confirm() and alert() boxes.

   Declarative use (no extra JavaScript needed):
     <form data-confirm="Message" data-confirm-title="Title" data-confirm-ok="Button text"
           data-confirm-tone="primary|danger|warn|success" data-confirm-icon="fa-save">
         The message can contain {fieldName} placeholders, filled from the form's fields.
         The dialog opens AFTER the page's own validation passes.
     <a href="..." data-confirm-leave="#formId">   Cancel link: asks "Discard changes?" only
         if the form was edited (leave the value empty to use the closest form).

   Script use:
     NetSyncConfirm.ask({title, message, ok, cancel, tone, icon}) -> Promise<boolean>
     NetSyncConfirm.notice(message, {title, tone, icon})          -> Promise (one OK button)
     NetSyncConfirm.guard('#formId', fn)                           -> runs fn, asking to discard first if the form is dirty
*/
(function () {
    'use strict';

    var css = '' +
        '.nsd-back{position:fixed;inset:0;z-index:10050;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(5,8,12,.68);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);opacity:0;transition:opacity .18s ease}' +
        '.nsd-back[hidden]{display:none}' +
        '.nsd-back.show{opacity:1}' +
        '.nsd{--nsd-c:var(--accent,#4d8cf5);--nsd-solid:var(--accent-solid,#2a64d4);--nsd-solid-h:var(--accent-solid-hover,#3470e4);width:min(440px,100%);box-sizing:border-box;background:var(--surface,#151b22);color:var(--text,#eef2f5);border:1px solid var(--line-strong,#364452);border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.5);padding:26px 26px 20px;font-family:"Figtree","Segoe UI",system-ui,sans-serif;line-height:1.45;transform:translateY(14px) scale(.96);transition:transform .24s var(--ease,cubic-bezier(.22,1,.36,1))}' +
        '.nsd-back.show .nsd{transform:none}' +
        '.nsd[data-tone="danger"]{--nsd-c:var(--danger,#ff8272);--nsd-solid:#c9382a;--nsd-solid-h:#b02f23}' +
        '.nsd[data-tone="warn"]{--nsd-c:var(--warn,#f2b134);--nsd-solid:#b9770e;--nsd-solid-h:#a2670b}' +
        '.nsd[data-tone="success"]{--nsd-c:var(--ok,#3ddc84);--nsd-solid:#1f8a52;--nsd-solid-h:#1a7545}' +
        '.nsd-ico{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:21px;margin-bottom:16px;color:var(--nsd-c);background:color-mix(in srgb,var(--nsd-c) 16%,transparent);box-shadow:0 0 0 7px color-mix(in srgb,var(--nsd-c) 8%,transparent)}' +
        '.nsd h3{margin:0 0 7px;font-family:"Sora","Figtree",sans-serif;font-size:20px;font-weight:600;letter-spacing:-.02em}' +
        '.nsd p{margin:0;color:var(--muted,#9aabb9);font-size:15px;white-space:pre-line;overflow-wrap:anywhere}' +
        '.nsd-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:24px}' +
        '.nsd-btn{height:44px;min-width:104px;padding:0 20px;border-radius:10px;border:1px solid var(--line-strong,#364452);background:var(--surface-2,#1b232b);color:var(--text,#eef2f5);font:600 15px "Sora","Figtree",sans-serif;cursor:pointer;transition:background .15s,border-color .15s,transform .15s,box-shadow .15s}' +
        '.nsd-btn:hover{border-color:var(--muted,#9aabb9);transform:translateY(-1px)}' +
        '.nsd-btn:focus-visible{outline:2px solid var(--nsd-c);outline-offset:2px}' +
        '.nsd-btn.nsd-ok{border-color:transparent;background:var(--nsd-solid);color:#fff}' +
        '.nsd-btn.nsd-ok:hover{background:var(--nsd-solid-h);box-shadow:0 10px 22px -10px var(--nsd-solid)}' +
        '@media (max-width:560px){.nsd{padding:22px 18px 16px}.nsd-actions{flex-direction:column-reverse}.nsd-btn{width:100%}}' +
        '@media (min-width:1700px) and (min-height:900px){.nsd{zoom:1.25}}' +
        '@media (min-width:2300px) and (min-height:1200px){.nsd{zoom:1.6}}' +
        '@media (prefers-reduced-motion:reduce){.nsd-back,.nsd{transition:none}}';
    var styleEl = document.createElement('style');
    styleEl.textContent = css;
    document.head.appendChild(styleEl);

    var TONE_ICON = { primary: 'fa-question-circle', danger: 'fa-trash', warn: 'fa-exclamation-triangle', success: 'fa-check-circle' };
    var back, box, icoEl, titleEl, msgEl, okBtn, cancelBtn, resolver = null, lastFocus = null, hideTimer = null;

    function build() {
        if (back) return;
        back = document.createElement('div');
        back.className = 'nsd-back';
        back.hidden = true;
        back.innerHTML =
            '<div class="nsd" role="alertdialog" aria-modal="true" aria-labelledby="nsdTitle" aria-describedby="nsdMsg">' +
            '<div class="nsd-ico"><i class="fas"></i></div>' +
            '<h3 id="nsdTitle"></h3><p id="nsdMsg"></p>' +
            '<div class="nsd-actions">' +
            '<button type="button" class="nsd-btn nsd-cancel"></button>' +
            '<button type="button" class="nsd-btn nsd-ok"></button>' +
            '</div></div>';
        document.body.appendChild(back);
        box = back.firstChild;
        icoEl = box.querySelector('.nsd-ico i');
        titleEl = box.querySelector('h3');
        msgEl = box.querySelector('p');
        cancelBtn = box.querySelector('.nsd-cancel');
        okBtn = box.querySelector('.nsd-ok');
        okBtn.addEventListener('click', function () { finish(true); });
        cancelBtn.addEventListener('click', function () { finish(false); });
        back.addEventListener('mousedown', function (e) { if (e.target === back) finish(false); });
        document.addEventListener('keydown', function (e) {
            if (back.hidden) return;
            if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(false); }
            else if (e.key === 'Tab') {
                var btns = cancelBtn.hidden ? [okBtn] : [cancelBtn, okBtn];
                var i = btns.indexOf(document.activeElement);
                e.preventDefault();
                btns[(i + (e.shiftKey ? btns.length - 1 : 1)) % btns.length].focus();
            }
        }, true);
    }

    function finish(result) {
        if (!resolver) return;
        var r = resolver; resolver = null;
        back.classList.remove('show');
        document.body.style.overflow = '';
        clearTimeout(hideTimer);
        hideTimer = setTimeout(function () { back.hidden = true; }, 190);
        if (lastFocus && lastFocus.focus) { try { lastFocus.focus({ preventScroll: true }); } catch (e) {} }
        r(result);
    }

    function ask(o) {
        o = o || {};
        build();
        if (resolver) finish(false);
        clearTimeout(hideTimer);
        var tone = o.tone || 'primary';
        box.setAttribute('data-tone', tone);
        icoEl.className = 'fas ' + (o.icon || TONE_ICON[tone] || TONE_ICON.primary);
        titleEl.textContent = o.title || 'Are you sure?';
        msgEl.textContent = o.message || '';
        msgEl.hidden = !o.message;
        okBtn.textContent = o.ok || 'Confirm';
        cancelBtn.textContent = o.cancel || 'Cancel';
        cancelBtn.hidden = !!o.hideCancel;
        lastFocus = document.activeElement;
        back.hidden = false;
        document.body.style.overflow = 'hidden';
        void back.offsetWidth;                       // let the browser paint before animating in
        back.classList.add('show');
        // Risky actions focus "Cancel" first so a stray Enter never deletes anything.
        (tone === 'danger' && !o.hideCancel ? cancelBtn : okBtn).focus();
        return new Promise(function (res) { resolver = res; });
    }

    function notice(message, o) {
        o = o || {};
        return ask({ title: o.title || 'Notice', message: message, ok: o.ok || 'OK', tone: o.tone || 'warn', icon: o.icon || 'fa-info-circle', hideCancel: true });
    }

    /* ---------- {fieldName} placeholders ---------- */
    function fill(text, form) {
        return String(text || '').replace(/\{(\w+)\}/g, function (m, name) {
            var el = form.elements && form.elements[name];
            if (!el || el.value === undefined || el.value === '') return m;
            return el.value;
        });
    }

    /* ---------- Forms with data-confirm ---------- */
    var snaps = new WeakMap();
    // 1) Before the page's own handlers run: remember the submit button, so "Cancel" can undo
    //    any "Saving..." spinner / disabled state those handlers apply.
    document.addEventListener('submit', function (e) {
        var f = e.target, b = e.submitter;
        if (!f || !f.hasAttribute || !f.hasAttribute('data-confirm') || !b) return;
        snaps.set(f, { b: b, d: b.disabled, h: b.innerHTML });
    }, true);
    // 2) After the page's own validation passed (nobody called preventDefault): ask.
    document.addEventListener('submit', function (e) {
        var f = e.target;
        if (!f || !f.hasAttribute || !f.hasAttribute('data-confirm') || e.defaultPrevented) return;
        e.preventDefault();
        var s = snaps.get(f), sub = e.submitter;
        ask({
            title: fill(f.getAttribute('data-confirm-title') || 'Please confirm', f),
            message: fill(f.getAttribute('data-confirm'), f),
            ok: f.getAttribute('data-confirm-ok') || 'Confirm',
            tone: f.getAttribute('data-confirm-tone') || 'primary',
            icon: f.getAttribute('data-confirm-icon') || ''
        }).then(function (yes) {
            if (!yes) {
                if (s) { s.b.disabled = s.d; s.b.innerHTML = s.h; }
                return;
            }
            if (sub && sub.name) {                   // keep the clicked button's name/value, like a normal submit
                var h = document.createElement('input');
                h.type = 'hidden'; h.name = sub.name; h.value = sub.value;
                f.appendChild(h);
            }
            f.__nsDirty = false;
            HTMLFormElement.prototype.submit.call(f);
        });
    }, false);

    /* ---------- Unsaved-change tracking + Cancel guards ---------- */
    function trackDirty(e) {
        var t = e.target, f = t && (t.form || (t.closest && t.closest('form')));
        if (f) f.__nsDirty = true;
    }
    document.addEventListener('input', trackDirty, true);
    document.addEventListener('change', trackDirty, true);
    document.addEventListener('reset', function (e) { if (e.target) e.target.__nsDirty = false; }, true);

    function resolveForm(sel, from) {
        if (sel && typeof sel !== 'string') return sel;
        if (sel) return document.querySelector(sel);
        return from && from.closest ? from.closest('form') : null;
    }

    function guard(sel, fn, from) {
        var f = resolveForm(sel, from);
        if (!(f && f.__nsDirty)) { fn(); return; }
        ask({
            title: 'Discard your changes?',
            message: 'You have unsaved changes. If you leave now, they will be lost.',
            ok: 'Discard', cancel: 'Keep editing', tone: 'warn', icon: 'fa-undo'
        }).then(function (yes) { if (yes) { f.__nsDirty = false; fn(); } });
    }

    document.addEventListener('click', function (e) {
        var a = e.target.closest && e.target.closest('[data-confirm-leave]');
        if (a) {
            var f = resolveForm(a.getAttribute('data-confirm-leave'), a);
            if (f && f.__nsDirty) {
                e.preventDefault(); e.stopPropagation();
                var href = a.href;
                guard(f, function () { window.location.href = href; });
            }
            return;
        }
        // Log out
        var lo = e.target.closest && e.target.closest('a[href="/logout"], a[href$="/logout"]');
        if (lo) {
            e.preventDefault(); e.stopPropagation();
            ask({
                title: 'Log out of NetSync?',
                message: 'You will need to sign in again to continue.',
                ok: 'Log Out', tone: 'warn', icon: 'fa-sign-out-alt'
            }).then(function (yes) { if (yes) window.location.href = lo.href; });
        }
    }, true);

    window.NetSyncConfirm = { ask: ask, notice: notice, guard: guard };
})();
