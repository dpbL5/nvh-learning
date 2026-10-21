/**
 * notifications.js — Full notifications page logic
 * Handles paginated list, mark-one-read on click, and mark-all-read button.
 */

const API = '/api/notifications/';

function authHeaders() {
    return {};
}

let currentPage = 1;

function escapeHtml(value) {
    return (value ?? '').toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ── Helpers ────────────────────────────────────────────────────────────────

function relativeTime(isoStr) {
    const diff = (Date.now() - new Date(isoStr)) / 1000;
    if (diff < 60)    return 'vừa xong';
    if (diff < 3600)  return `${Math.floor(diff / 60)} phút trước`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
    return `${Math.floor(diff / 86400)} ngày trước`;
}

function notifCardHTML(n) {
    const unreadStyle = n.is_read
        ? 'background:#fff;'
        : 'background:linear-gradient(135deg,#f0f0ff 0%,#fff 100%); border-left:4px solid var(--color-primary,#4f46e5);';
    const url = n.quiz_url || '/notifications/';
    return `
    <a href="${escapeHtml(url)}" class="text-decoration-none" data-notif-id="${n.id}" data-is-read="${n.is_read}">
        <div class="d-flex gap-3 align-items-start px-3 py-3 border-bottom notif-card"
             style="${unreadStyle} transition:background .2s;">
            <div style="min-width:38px;height:38px;border-radius:50%;background:var(--color-primary,#4f46e5);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                <i class="bi bi-bell-fill text-white" style="font-size:.95rem;"></i>
            </div>
            <div style="flex:1;min-width:0;">
                <div class="small fw-600 text-dark" style="line-height:1.4;">${escapeHtml(n.message)}</div>
                <div class="text-muted mt-1" style="font-size:.75rem;">
                    <i class="bi bi-clock me-1"></i>${relativeTime(n.created_at)}
                </div>
            </div>
            ${n.is_read ? '' : '<span class="badge rounded-pill bg-primary ms-1" style="font-size:.6rem;padding:.35em .55em;align-self:center;">Mới</span>'}
        </div>
    </a>`;
}

// ── Render ─────────────────────────────────────────────────────────────────

function renderNotifPage(data) {
    const list = document.getElementById('notifPageList');
    const loading = document.getElementById('notifPageLoading');
    if (!list) return;
    loading.style.display = 'none';
    list.style.display = 'block';

    const notifs = data.results || [];
    if (!notifs.length) {
        list.innerHTML = `
        <div class="text-center py-5" style="background:#fff;border:1px solid var(--color-border,#e5e7eb);border-radius:16px;">
            <i class="bi bi-bell-slash" style="font-size:2.5rem;color:#9ca3af;"></i>
            <p class="mt-3 text-muted">Bạn chưa có thông báo nào.</p>
        </div>`;
        renderPagination(data);
        return;
    }

    list.innerHTML = `
    <div style="border:1px solid var(--color-border,#e5e7eb);border-radius:16px;overflow:hidden;">
        ${notifs.map(notifCardHTML).join('')}
    </div>`;

    // Click: mark as read then navigate
    list.querySelectorAll('[data-notif-id]').forEach(el => {
        el.addEventListener('click', async (e) => {
            const id = el.dataset.notifId;
            const isRead = el.dataset.isRead === 'true';
            if (!isRead) {
                e.preventDefault();
                await fetch(`${API}${id}/read/`, {
                    method: 'PATCH',
                    headers: authHeaders(),
                });
                window.location.href = el.getAttribute('href');
            }
        });
    });

    renderPagination(data);
}

function renderPagination(data) {
    const container = document.getElementById('notifPagePagination');
    if (!container) return;
    const total = data.count || 0;
    const pageSize = (data.results || []).length || 20;
    const totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    container.innerHTML = Array.from({ length: totalPages }, (_, i) => i + 1).map(p => `
        <button class="btn btn-sm ${p === currentPage ? 'btn-primary' : 'btn-outline-secondary'}"
                style="min-width:38px;border-radius:8px;" onclick="loadPage(${p})">${p}</button>
    `).join('');
}

// ── Data fetch ─────────────────────────────────────────────────────────────

async function loadPage(page = 1) {
    currentPage = page;
    if (!localStorage.getItem('auth_hint')) { window.location.href = '/login/'; return; }
    document.getElementById('notifPageLoading').style.display = 'block';
    document.getElementById('notifPageList').style.display = 'none';
    try {
        const res = await fetch(`${API}?page=${page}`, {
            headers: authHeaders(),
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        renderNotifPage(data);
    } catch {
        document.getElementById('notifPageLoading').innerHTML =
            '<p class="text-danger">Không thể tải thông báo. Vui lòng thử lại.</p>';
    }
}

// ── Mark all read ──────────────────────────────────────────────────────────

async function markAllRead() {
    if (!localStorage.getItem('auth_hint')) return;
    await fetch(`${API}mark-all-read/`, {
        method: 'POST',
        headers: authHeaders(),
    });
    // Refresh count in navbar
    if (typeof window.refreshNotifCount === 'function') window.refreshNotifCount();
    // Reload page list
    await loadPage(currentPage);
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadPage(1);

    const btn = document.getElementById('pageMarkAllBtn');
    if (btn) btn.addEventListener('click', markAllRead);
});
