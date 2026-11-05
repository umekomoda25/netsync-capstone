// Immediately apply saved theme to avoid flash of wrong colors
(function() {
    var m = localStorage.getItem('ns_mode') || 'dark';
    var c = localStorage.getItem('ns_color') || 'purple';
    if (m === 'light') document.documentElement.classList.add('light-mode');
    if (c === 'red')   document.documentElement.classList.add('theme-red');
    document.addEventListener('DOMContentLoaded', function() {
        document.body.classList.toggle('light-mode', m === 'light');
        document.body.classList.toggle('theme-red', c === 'red');
    });
})();

// ====== UI Enhancements ======
document.addEventListener('DOMContentLoaded', function() {

    /* ---------- Mobile sidebar toggle ---------- */
    (function() {
        const sidebar = document.querySelector('.sidebar');
        const header = document.querySelector('.top-header');
        if (!sidebar || !header) return;

        const ham = document.createElement('button');
        ham.className = 'hamburger-btn';
        ham.setAttribute('aria-label', 'Toggle menu');
        ham.innerHTML = '<i class="fas fa-bars"></i>';
        header.insertBefore(ham, header.firstChild);

        /* ---------- Mobile logo: centered in the top bar, tap to go back to the dashboard ---------- */
        const logoLink = document.createElement('a');
        logoLink.className = 'mobile-logo';
        logoLink.href = '/dashboard';
        logoLink.setAttribute('aria-label', 'NetSync - go to Dashboard');
        logoLink.innerHTML = '<img src="/static/netsync-logo-mobile.png" alt="NetSync" width="179" height="84">';
        header.insertBefore(logoLink, ham.nextSibling);

        const mobileCss = document.createElement('style');
        mobileCss.textContent =
            '.mobile-logo { display: none; }' +
            '@media print { .top-header, .mobile-logo, .hamburger-btn, .notif-wrap { display: none !important; } }' +
            '@media screen and (max-width: 900px) {' +
            '  .top-header { display: grid !important; grid-template-columns: 1fr auto 1fr; grid-template-areas: "menu logo user";' +
            '    align-items: center; row-gap: 2px; height: auto !important; min-height: 62px; padding: 8px 16px 6px !important; }' +
            '  .top-header .hamburger-btn { grid-area: menu; justify-self: start; margin-right: 0 !important; }' +
            '  .top-header .mobile-logo { grid-area: logo; display: flex; align-items: center; justify-content: center;' +
            '    min-width: 48px; min-height: 44px; padding: 4px 10px; border-radius: 10px; background: #0e1318;' +
            '    -webkit-tap-highlight-color: transparent; transition: transform .15s, box-shadow .15s; }' +
            '  .top-header .mobile-logo:active { transform: scale(.96); }' +
            '  .top-header .mobile-logo:focus-visible { outline: 2px solid var(--accent, #4d8cf5); outline-offset: 2px; }' +
            '  .top-header .mobile-logo img { display: block; height: 34px; width: auto; max-width: 100%; }' +
            '  .top-header .user-profile, .top-header .header-actions { grid-area: user; justify-self: end; min-width: 0; }' +
            '  .top-header .page-title { display: none !important; }' +
            '}' +
            '@media screen and (max-width: 560px) {' +
            '  .top-header .btn-add-user { font-size: 0 !important; gap: 0 !important; min-width: 40px; padding: 0 12px !important; }' +
            '  .top-header .btn-add-user i { font-size: 15px; margin: 0; }' +
            '}';
        document.head.appendChild(mobileCss);

        const backdrop = document.createElement('div');
        backdrop.className = 'sidebar-backdrop';
        document.body.appendChild(backdrop);

        function openSidebar() {
            sidebar.classList.add('open');
            backdrop.classList.add('visible');
        }
        function closeSidebar() {
            sidebar.classList.remove('open');
            backdrop.classList.remove('visible');
        }

        ham.addEventListener('click', function() {
            sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
        });
        backdrop.addEventListener('click', closeSidebar);

        sidebar.querySelectorAll('.nav-link').forEach(function(link) {
            link.addEventListener('click', function() {
                if (window.innerWidth <= 900) closeSidebar();
            });
        });

        window.addEventListener('resize', function() {
            if (window.innerWidth > 900) closeSidebar();
        });

        let touchStartX = 0;
        sidebar.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
        }, { passive: true });
        sidebar.addEventListener('touchend', function(e) {
            const dx = e.changedTouches[0].clientX - touchStartX;
            if (dx < -60) closeSidebar();
        });
    })();

    /* ---------- Notification bell (all roles) ---------- */
    (function() {
        const header = document.querySelector('.top-header');
        if (!header) return;
        const host = header.querySelector('.user-profile, .header-actions');
        if (!host) return;

        const css = document.createElement('style');
        css.textContent =
            '.notif-wrap { position: relative; flex: none; }' +
            '.notif-btn { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; padding: 0; cursor: pointer;' +
            '  font-size: 17px; color: var(--text, #eef2f5); background: var(--surface, #151b22); border: 1px solid var(--line-strong, #364452); border-radius: 50%; }' +
            '.notif-btn:hover { border-color: var(--accent, #4d8cf5); }' +
            '.notif-btn.ring i { animation: notifRing .8s ease-in-out 2; transform-origin: 50% 0; }' +
            '@keyframes notifRing { 0%,100% { transform: rotate(0); } 20% { transform: rotate(14deg); } 40% { transform: rotate(-12deg); } 60% { transform: rotate(8deg); } 80% { transform: rotate(-6deg); } }' +
            '.notif-badge { position: absolute; top: -4px; right: -4px; min-width: 19px; height: 19px; padding: 0 5px; display: none; align-items: center; justify-content: center;' +
            '  font: 700 11px/1 "Sora", sans-serif; color: #fff; background: #d64533; border-radius: 999px; border: 2px solid var(--bg, #0e1318); }' +
            '.notif-panel { display: none; position: absolute; top: calc(100% + 10px); right: 0; z-index: 1300; width: 360px; max-width: calc(100vw - 24px); max-height: 70vh; overflow: hidden;' +
            '  flex-direction: column; color: var(--text, #eef2f5); background: var(--surface, #151b22); border: 1px solid var(--line-strong, #364452); border-radius: 10px; box-shadow: 0 18px 44px rgba(0,0,0,.45); }' +
            '.notif-panel.open { display: flex; }' +
            '.notif-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--line, #26313b); font-weight: 600; font-size: 15px; }' +
            '.notif-head button { font: inherit; font-size: 13px; font-weight: 500; color: var(--accent, #4d8cf5); background: none; border: 0; cursor: pointer; }' +
            '.notif-list { overflow-y: auto; }' +
            '.notif-item { display: flex; gap: 10px; width: 100%; padding: 12px 16px; text-align: left; font: inherit; color: inherit; background: none; border: 0; border-bottom: 1px solid var(--line, #26313b); cursor: pointer; }' +
            '.notif-item:hover { background: var(--surface-2, #1b232b); }' +
            '.notif-item .dot { flex: none; width: 9px; height: 9px; margin-top: 6px; border-radius: 50%; background: transparent; }' +
            '.notif-item.unread .dot { background: var(--accent, #4d8cf5); }' +
            '.notif-item .msg { font-size: 14px; line-height: 1.4; }' +
            '.notif-item.unread .msg { font-weight: 600; }' +
            '.notif-item .when { display: block; margin-top: 3px; font-size: 12px; color: var(--muted, #9aabb9); font-weight: 400; }' +
            '.notif-empty { padding: 26px 16px; text-align: center; font-size: 14px; color: var(--muted, #9aabb9); }' +
            '@media (max-width: 900px) { .notif-panel { position: fixed; top: 70px; right: 12px; left: 12px; width: auto; max-width: none; } }';
        document.head.appendChild(css);

        const wrap = document.createElement('div');
        wrap.className = 'notif-wrap';
        wrap.hidden = true;                                   // shown only if the server says this user gets notifications
        wrap.innerHTML =
            '<button type="button" class="notif-btn" aria-label="Notifications" aria-haspopup="true" aria-expanded="false"><i class="fas fa-bell"></i><span class="notif-badge"></span></button>' +
            '<div class="notif-panel" role="dialog" aria-label="Notifications"><div class="notif-head"><span>Notifications</span><button type="button" class="notif-readall">Mark all as read</button></div><div class="notif-list"></div></div>';
        host.insertBefore(wrap, host.firstChild);

        const btn = wrap.querySelector('.notif-btn'), badge = wrap.querySelector('.notif-badge');
        const panel = wrap.querySelector('.notif-panel'), list = wrap.querySelector('.notif-list');
        let lastUnread = null;
        let maxSeenId = null;        // highest notification id already shown, so only genuinely new ones pop up as toasts

        // pick an icon + colour class from the wording of the message
        function kind(msg) {
            const m = (msg || '').toLowerCase();
            if (m.indexOf('stock') !== -1) return { c: 'ni-stock', i: 'fa-boxes-stacked', t: 'stock' };
            if (m.indexOf('survey') !== -1) return { c: 'ni-survey', i: 'fa-clipboard-check', t: 'info' };
            if (m.indexOf('completed') !== -1) return { c: 'ni-done', i: 'fa-circle-check', t: 'success' };
            if (m.indexOf('archived') !== -1 || m.indexOf('restored') !== -1) return { c: 'ni-archive', i: 'fa-box-archive', t: 'info' };
            if (m.indexOf('assigned') !== -1) return { c: 'ni-assign', i: 'fa-user-plus', t: 'info' };
            if (m.indexOf('reopened') !== -1) return { c: 'ni-assign', i: 'fa-rotate-left', t: 'info' };
            return { c: 'ni-log', i: 'fa-camera', t: 'info' };
        }

        function ago(it) {
            const s = it.age_seconds;
            if (s < 60) return 'Just now';
            if (s < 3600) return Math.floor(s / 60) + ' min ago';
            if (s < 86400) return Math.floor(s / 3600) + ' hr ago';
            return it.when;
        }
        function render(data) {
            wrap.hidden = false;
            badge.textContent = data.unread > 99 ? '99+' : data.unread;
            badge.style.display = data.unread ? 'inline-flex' : 'none';
            btn.classList.toggle('has-unread', data.unread > 0);
            if (lastUnread !== null && data.unread > lastUnread) {
                btn.classList.add('ring');
                badge.classList.remove('pop'); void badge.offsetWidth; badge.classList.add('pop');
                setTimeout(function() { btn.classList.remove('ring'); }, 1800);
            }
            lastUnread = data.unread;

            // live toast for notifications that arrived since the last check (not on first page load)
            const ids = data.items.map(function(it) { return it.id; });
            const newest = ids.length ? Math.max.apply(null, ids) : 0;
            if (maxSeenId !== null && window.NSToast) {
                data.items.filter(function(it) { return it.id > maxSeenId && !it.is_read; })
                    .slice(0, 3).reverse().forEach(function(it) {
                        const k = kind(it.message);
                        window.NSToast(it.message, { type: k.t, title: k.t === 'stock' ? 'Stock alert' : 'New notification', icon: k.i, link: it.link || null });
                    });
            }
            maxSeenId = maxSeenId === null ? newest : Math.max(maxSeenId, newest);

            list.innerHTML = '';
            if (!data.items.length) {
                list.innerHTML = '<div class="notif-empty"><i class="fas fa-bell-slash"></i>You\'re all caught up.</div>';
                return;
            }
            data.items.forEach(function(it, idx) {
                const k = kind(it.message);
                const b = document.createElement('button');
                b.type = 'button';
                b.className = 'notif-item' + (it.is_read ? '' : ' unread');
                b.style.setProperty('--i', Math.min(idx, 8));
                b.innerHTML = '<span class="dot"></span><span class="ni-ico ' + k.c + '"><i class="fas ' + k.i + '"></i></span><span class="msg"></span>';
                const msg = b.querySelector('.msg');
                msg.textContent = it.message;
                const w = document.createElement('span');
                w.className = 'when'; w.textContent = ago(it);
                msg.appendChild(w);
                b.addEventListener('click', function() {
                    fetch('/api/notifications/' + it.id + '/read', { method: 'POST', credentials: 'same-origin' })
                        .finally(function() { if (it.link) window.location.href = it.link; else load(); });
                });
                list.appendChild(b);
            });
        }
        function load() {
            fetch('/api/notifications', { credentials: 'same-origin' })
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(d) { if (d && d.enabled) render(d); })
                .catch(function() {});
        }
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const open = panel.classList.toggle('open');
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open) { document.dispatchEvent(new CustomEvent('ns:popover-open', { detail: 'bell' })); load(); }
        });
        document.addEventListener('ns:popover-open', function(e) {      // only one popover open at a time
            if (e.detail !== 'bell') { panel.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
        });
        panel.addEventListener('click', function(e) { e.stopPropagation(); });
        document.addEventListener('click', function() { panel.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); });
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape') panel.classList.remove('open'); });
        wrap.querySelector('.notif-readall').addEventListener('click', function() {
            fetch('/api/notifications/read-all', { method: 'POST', credentials: 'same-origin' }).then(load);
        });
        load();
        setInterval(function() { if (!document.hidden) load(); }, 30000);
        document.addEventListener('visibilitychange', function() { if (!document.hidden) load(); });
    })();

    /* ---------- Profile popover: click the avatar / name / role to see your own details ---------- */
    (function() {
        const header = document.querySelector('.top-header');
        if (!header) return;
        const triggers = Array.prototype.slice.call(header.querySelectorAll('.avatar, .user-name, .role-chip'));
        if (!triggers.length) return;

        const css = document.createElement('style');
        css.textContent =
            '.ns-profile-trigger { cursor: pointer; transition: transform .2s, opacity .2s; }' +
            '.ns-profile-trigger:hover { opacity: .85; }' +
            '.avatar.ns-profile-trigger:hover { transform: scale(1.06); }' +
            '.ns-profile { position: fixed; z-index: 1400; width: 320px; max-width: calc(100vw - 24px); padding: 20px; display: none;' +
            '  color: var(--text, #eef2f5); background: var(--surface, #151b22); border: 1px solid var(--line-strong, #364452); border-radius: 18px;' +
            '  box-shadow: 0 22px 48px -14px rgba(0,0,0,.6); }' +
            '.ns-profile.open { display: block; animation: nsProfileIn .3s cubic-bezier(.22,1,.36,1); transform-origin: top right; }' +
            '@keyframes nsProfileIn { from { opacity: 0; transform: translateY(-8px) scale(.95); } to { opacity: 1; transform: none; } }' +
            '.ns-profile .pp-top { display: flex; align-items: center; gap: 14px; padding-bottom: 16px; margin-bottom: 8px; border-bottom: 1px solid var(--line, #26313b); }' +
            '.ns-profile .pp-av { flex: none; width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center; overflow: hidden; font: 700 22px "Sora", sans-serif; color: #fff;' +
            '  background: linear-gradient(135deg, var(--accent, #4d8cf5), color-mix(in srgb, var(--accent, #4d8cf5) 45%, #7a4dff)); }' +
            '.ns-profile .pp-name { font: 600 17px/1.25 "Sora", sans-serif; overflow-wrap: anywhere; }' +
            '.ns-profile .pp-role { display: inline-block; margin-top: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 600;' +
            '  color: var(--accent, #4d8cf5); border: 1px solid color-mix(in srgb, var(--accent, #4d8cf5) 40%, transparent); background: color-mix(in srgb, var(--accent, #4d8cf5) 10%, transparent); }' +
            '.ns-profile .pp-row { padding: 10px 0; border-bottom: 1px solid var(--line, #26313b); }' +
            '.ns-profile .pp-row:last-child { border-bottom: 0; padding-bottom: 0; }' +
            '.ns-profile .pp-row label { display: block; margin-bottom: 3px; font-size: 13px; color: var(--muted, #9aabb9); }' +
            '.ns-profile .pp-row span { font-size: 16px; font-weight: 500; overflow-wrap: anywhere; }' +
            '.ns-profile .pp-manage { display: flex; align-items: center; justify-content: center; gap: 9px; margin-top: 16px; padding: 11px 14px; border-radius: 10px; font: 600 15px "Figtree", sans-serif; text-decoration: none;' +
            '  color: var(--accent, #4d8cf5); border: 1px solid color-mix(in srgb, var(--accent, #4d8cf5) 40%, transparent); background: color-mix(in srgb, var(--accent, #4d8cf5) 10%, transparent); transition: background .15s, border-color .15s; }' +
            '.ns-profile .pp-manage:hover, .ns-profile .pp-manage:focus-visible { background: color-mix(in srgb, var(--accent, #4d8cf5) 20%, transparent); border-color: var(--accent, #4d8cf5); outline: none; }' +
            '.ns-profile .pp-manage svg { width: 15px; height: 15px; flex: none; }' +
            '.ns-profile .pp-state { padding: 18px 0 6px; text-align: center; font-size: 14px; color: var(--muted, #9aabb9); }';
        document.head.appendChild(css);

        const pop = document.createElement('div');
        pop.className = 'ns-profile';
        pop.setAttribute('role', 'dialog');
        pop.setAttribute('aria-label', 'Your profile');
        document.body.appendChild(pop);

        let loaded = false;
        function esc(t) { const d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
        function row(label, value) { return value ? '<div class="pp-row"><label>' + label + '</label><span>' + esc(value) + '</span></div>' : ''; }
        function fill(d) {
            pop.innerHTML =
                '<div class="pp-top"><div class="pp-av">' + (d.photo_url ? '<img src="' + esc(d.photo_url) + '" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;">' : esc((d.full_name || d.username || '?').charAt(0).toUpperCase())) + '</div>' +
                '<div><div class="pp-name">' + esc(d.full_name) + '</div><span class="pp-role">' + esc(d.role) + '</span></div></div>' +
                row('Username', d.username) + row('Email', d.email) + row('Contact number', d.contact_number) +
                '<a class="pp-manage" href="/settings#account" aria-label="Manage profile">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>Manage profile</a>';
            loaded = true;
        }
        function place() {
            const av = header.querySelector('.avatar') || triggers[0];
            const r = av.getBoundingClientRect();
            pop.style.top = Math.round(r.bottom + 12) + 'px';
            pop.style.right = Math.max(12, Math.round(window.innerWidth - r.right)) + 'px';
        }
        function open() {
            document.dispatchEvent(new CustomEvent('ns:popover-open', { detail: 'profile' }));
            place();
            pop.classList.add('open');
            triggers.forEach(function(t) { t.setAttribute('aria-expanded', 'true'); });
            if (!loaded) {
                pop.innerHTML = '<div class="pp-state">Loading your details…</div>';
                fetch('/api/me', { credentials: 'same-origin' })
                    .then(function(r) { if (!r.ok) throw new Error(); return r.json(); })
                    .then(fill)
                    .catch(function() { pop.innerHTML = '<div class="pp-state">Could not load your details. Please try again.</div>'; });
            }
        }
        function close() {
            pop.classList.remove('open');
            triggers.forEach(function(t) { t.setAttribute('aria-expanded', 'false'); });
        }
        triggers.forEach(function(t) {
            t.classList.add('ns-profile-trigger');
            t.setAttribute('role', 'button');
            t.setAttribute('tabindex', '0');
            t.setAttribute('aria-haspopup', 'dialog');
            t.setAttribute('aria-expanded', 'false');
            t.addEventListener('click', function(e) { e.stopPropagation(); pop.classList.contains('open') ? close() : open(); });
            t.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pop.classList.contains('open') ? close() : open(); }
            });
        });
        pop.addEventListener('click', function(e) { e.stopPropagation(); });
        document.addEventListener('ns:popover-open', function(e) { if (e.detail !== 'profile') close(); });
        document.addEventListener('click', close);
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape') close(); });
        window.addEventListener('resize', function() { if (pop.classList.contains('open')) place(); });
    })();

    /* ---------- User card: click any name marked data-user-card="<id>" to see that person's photo, name and role ---------- */
    (function() {
        const css = document.createElement('style');
        css.textContent =
            '.user-link { all: unset; box-sizing: border-box; cursor: pointer; color: var(--accent, #4d8cf5); font-weight: 600; border-bottom: 1px dashed color-mix(in srgb, var(--accent, #4d8cf5) 55%, transparent); transition: opacity .15s, border-color .15s; }' +
            '.user-link:hover { opacity: .85; border-bottom-style: solid; }' +
            '.user-link:focus-visible { outline: 2px solid var(--accent, #4d8cf5); outline-offset: 3px; border-radius: 4px; }' +
            '.ns-ucard-back { position: fixed; inset: 0; z-index: 1500; display: none; align-items: center; justify-content: center; padding: 16px; background: rgba(5,8,12,.62); backdrop-filter: blur(3px); }' +
            '.ns-ucard-back.open { display: flex; animation: nsUcFade .2s ease; }' +
            '@keyframes nsUcFade { from { opacity: 0; } to { opacity: 1; } }' +
            '@keyframes nsUcPop { from { opacity: 0; transform: translateY(10px) scale(.96); } to { opacity: 1; transform: none; } }' +
            '.ns-ucard { position: relative; width: 340px; max-width: 100%; padding: 32px 24px 26px; text-align: center; color: var(--text, #eef2f5); background: var(--surface, #151b22);' +
            '  border: 1px solid var(--line-strong, #364452); border-radius: 18px; box-shadow: 0 22px 48px -14px rgba(0,0,0,.6); animation: nsUcPop .28s cubic-bezier(.22,1,.36,1); }' +
            '.ns-ucard .uc-close { position: absolute; top: 10px; right: 10px; width: 34px; height: 34px; border-radius: 50%; border: 0; cursor: pointer; font-size: 18px; line-height: 1; color: var(--muted, #9aabb9); background: transparent; }' +
            '.ns-ucard .uc-close:hover, .ns-ucard .uc-close:focus-visible { background: color-mix(in srgb, var(--muted, #9aabb9) 18%, transparent); color: var(--text, #eef2f5); outline: none; }' +
            '.ns-ucard .uc-av { width: 110px; height: 110px; margin: 0 auto 16px; border-radius: 50%; display: grid; place-items: center; overflow: hidden; font: 700 44px "Sora", sans-serif; color: #fff;' +
            '  background: linear-gradient(135deg, var(--accent, #4d8cf5), color-mix(in srgb, var(--accent, #4d8cf5) 45%, #7a4dff)); box-shadow: 0 8px 22px color-mix(in srgb, var(--accent, #4d8cf5) 35%, transparent); }' +
            '.ns-ucard .uc-av img { width: 100%; height: 100%; object-fit: cover; display: block; }' +
            '.ns-ucard .uc-name { font: 600 20px/1.25 "Sora", sans-serif; overflow-wrap: anywhere; }' +
            '.ns-ucard .uc-role { display: inline-block; margin-top: 10px; padding: 4px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; color: var(--accent, #4d8cf5);' +
            '  border: 1px solid color-mix(in srgb, var(--accent, #4d8cf5) 40%, transparent); background: color-mix(in srgb, var(--accent, #4d8cf5) 10%, transparent); }' +
            '.ns-ucard .uc-state { padding: 34px 0 20px; font-size: 14px; color: var(--muted, #9aabb9); }';
        document.head.appendChild(css);

        const back = document.createElement('div');
        back.className = 'ns-ucard-back';
        back.innerHTML = '<div class="ns-ucard" role="dialog" aria-modal="true" aria-label="Profile"><button type="button" class="uc-close" aria-label="Close">&times;</button><div class="uc-body"></div></div>';
        document.body.appendChild(back);
        const body = back.querySelector('.uc-body');
        const closeBtn = back.querySelector('.uc-close');
        let lastFocus = null, token = 0;

        function esc(t) { const d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
        function close() { back.classList.remove('open'); token++; if (lastFocus && lastFocus.focus) lastFocus.focus(); lastFocus = null; }
        function show(trigger) {
            const id = trigger.getAttribute('data-user-card');
            if (!id) return;
            document.dispatchEvent(new CustomEvent('ns:popover-open', { detail: 'user-card' }));
            lastFocus = trigger;
            body.innerHTML = '<div class="uc-state">Loading…</div>';
            back.classList.add('open');
            closeBtn.focus();
            const mine = ++token;
            fetch('/api/users/' + encodeURIComponent(id) + '/card', { credentials: 'same-origin' })
                .then(function(r) { if (!r.ok) throw new Error(); return r.json(); })
                .then(function(d) {
                    if (mine !== token) return;
                    body.innerHTML =
                        '<div class="uc-av">' + (d.photo_url ? '<img src="' + esc(d.photo_url) + '" alt="Profile photo of ' + esc(d.full_name) + '">' : esc((d.full_name || '?').charAt(0).toUpperCase())) + '</div>' +
                        '<div class="uc-name">' + esc(d.full_name) + '</div><span class="uc-role">' + esc(d.role) + '</span>';
                })
                .catch(function() { if (mine === token) body.innerHTML = '<div class="uc-state">Could not load this profile. It may no longer be active.</div>'; });
        }
        document.addEventListener('click', function(e) {
            const t = e.target.closest ? e.target.closest('[data-user-card]') : null;
            if (t) { e.preventDefault(); e.stopPropagation(); show(t); }
        }, true);
        back.addEventListener('click', function(e) { if (e.target === back) close(); });
        closeBtn.addEventListener('click', close);
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && back.classList.contains('open')) close(); });
        document.addEventListener('ns:popover-open', function(e) { if (e.detail !== 'user-card') back.classList.remove('open'); });
    })();

    /* ---------- Convert flash messages to toasts ---------- */
    var flashEls = document.querySelectorAll('.flash-error, .flash-success, .flash-msg');
    flashEls.forEach(function(el) {
        if (el.classList.contains('flash-error')) {
            el.classList.add('shake');
        } else {
            el.classList.add('bounce-in');
        }
        setTimeout(function() {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.5s';
            setTimeout(function() { el.remove(); }, 500);
        }, 5000);
    });

    /* ---------- Animate dashboard counters ---------- */
    var counters = document.querySelectorAll('.stat-details h3');
    counters.forEach(function(el) {
        var target = parseInt(el.textContent.trim());
        if (isNaN(target)) return;
        el.textContent = '0';
        var duration = 1000;
        var startTime = null;
        function step(timestamp) {
            if (!startTime) startTime = timestamp;
            var progress = Math.min((timestamp - startTime) / duration, 1);
            el.textContent = Math.floor(progress * target);
            if (progress < 1) requestAnimationFrame(step);
            else el.textContent = target;
        }
        requestAnimationFrame(step);
    });

    /* ---------- Animate progress bars ---------- */
    document.querySelectorAll('.progress-bar-fill').forEach(function(bar) {
        var targetWidth = bar.style.width;
        bar.style.width = '0%';
        setTimeout(function() { bar.style.width = targetWidth; }, 100);
    });

    /* ---------- Ripple effect on buttons ---------- */
    document.querySelectorAll('.btn, .btn-icon, .btn-add-user').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            var ripple = document.createElement('span');
            ripple.className = 'ripple';
            var rect = btn.getBoundingClientRect();
            var size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size/2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size/2) + 'px';
            btn.appendChild(ripple);
            setTimeout(function() { ripple.remove(); }, 600);
        });
    });

    /* ---------- Card entrance animations ---------- */
    document.querySelectorAll('.card').forEach(function(card, index) {
        card.style.opacity = '0';
        setTimeout(function() {
            card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 80);
        card.addEventListener('mouseenter', function() { card.style.transform = 'translateY(-2px)'; });
        card.addEventListener('mouseleave', function() { card.style.transform = 'translateY(0)'; });
    });

    /* ---------- Remember dashboard filter ---------- */
    var activeFilter = localStorage.getItem('dashboardFilter');
    if (activeFilter) {
        var tab = document.querySelector('.btn-filter[onclick*="' + activeFilter + '"]');
        if (tab) {
            document.querySelectorAll('.btn-filter').forEach(function(b) { b.classList.remove('active-filter'); });
            tab.classList.add('active-filter');
            if (typeof filterProjects === 'function') filterProjects(activeFilter, tab);
        }
    }
    document.querySelectorAll('.btn-filter').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var match = btn.getAttribute('onclick').match(/'([^']+)'/);
            if (match) localStorage.setItem('dashboardFilter', match[1]);
        });
    });

    /* ---------- Focus first input ONCE when a modal opens ----------
       Previously this used a setInterval that fired every 500ms and
       stole focus from inputs and closed dropdowns inside modals.
       Now it uses MutationObserver so it only fires the moment the
       modal gains the 'open' class, and never again. */
    document.querySelectorAll('.modal-overlay').forEach(function(modal) {
        var hasFocusedOnce = false;
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName !== 'class') return;
                if (modal.classList.contains('open') && !hasFocusedOnce) {
                    hasFocusedOnce = true;
                    setTimeout(function() {
                        var input = modal.querySelector(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'
                        );
                        if (input) input.focus();
                    }, 60);
                }
                if (!modal.classList.contains('open')) {
                    hasFocusedOnce = false;
                }
            });
        });
        observer.observe(modal, { attributes: true, attributeFilter: ['class'] });
    });

    /* ---------- Low stock highlighting ---------- */
    document.querySelectorAll('.stock-cell').forEach(function(cell) {
        var value = parseFloat(cell.textContent);
        if (!isNaN(value) && value <= 5) cell.classList.add('low-stock');
    });

    /* Export CSV is handled in inventory.html (single handler, avoids duplicate downloads). */
});

/* ---- Number fields never accept negative values (typing, pasting, spinner, scroll) ---- */
(function () {
    function fix(el) {
        if (!el || el.type !== 'number') return;
        if (el.min === '' || parseFloat(el.min) < 0) el.min = '0';
    }
    document.addEventListener('focusin', function (e) { fix(e.target); });
    document.addEventListener('keydown', function (e) {
        var el = e.target;
        if (!el || el.type !== 'number') return;
        if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
    });
    document.addEventListener('input', function (e) {
        var el = e.target;
        if (!el || el.type !== 'number') return;
        var v = el.value;
        if (v !== '' && (v.indexOf('-') !== -1 || parseFloat(v) < 0)) {
            el.value = v.replace(/-/g, '');
            if (parseFloat(el.value) < 0) el.value = '';
        }
    });
    document.querySelectorAll('input[type="number"]').forEach(fix);
})();
