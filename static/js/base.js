// Navbar scroll effect
function escapeHtml(value) {
    return (value ?? '').toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

function sanitizeMarkdownHtml(html) {
    return (html ?? '').toString().replace(
        /\b(href|src)\s*=\s*("|')\s*(?:javascript|data|vbscript):[^"']*\2/gi,
        '$1="#"'
    );
}
window.sanitizeMarkdownHtml = sanitizeMarkdownHtml;

window.getCloudinarySignature = async function() {
    const res = await fetch('/api/exams/cloudinary-signature/', { headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || 'Không thể lấy chữ ký tải ảnh lên.');
    }
    return data;
};

function authHeaders(extra) {
    return Object.assign({}, extra || {});
}

// Transparently refresh expired access tokens once per request.
(function installTokenRefresh() {
    const nativeFetch = window.fetch.bind(window);
    let refreshPromise = null;

    function clearAuthState() {
        localStorage.removeItem('auth_hint');
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
        localStorage.removeItem('user_profile');
    }

    async function refreshAccessToken() {
        if (!localStorage.getItem('auth_hint')) return false;
        try {
            const res = await nativeFetch('/api/accounts/token/refresh/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (!res.ok) {
                clearAuthState();
                return false;
            }
            localStorage.removeItem('access');
            localStorage.removeItem('refresh');
            return true;
        } catch (e) {
            return false;
        }
    }

    window.fetch = async function(input, init) {
        const response = await nativeFetch(input, init);
        if (response.status !== 401 || typeof input !== 'string') return response;

        const isAuthEndpoint = input.includes('/api/accounts/login/') ||
            input.includes('/api/accounts/token/refresh/');
        if (isAuthEndpoint || !localStorage.getItem('auth_hint')) return response;

        if (!refreshPromise) {
            refreshPromise = refreshAccessToken().finally(() => { refreshPromise = null; });
        }
        const refreshed = await refreshPromise;
        if (!refreshed) return response;
        return nativeFetch(input, init);
    };
})();

window.addEventListener('scroll', () => {
    document.getElementById('mainNavbar').classList.toggle('scrolled', window.scrollY > 10);
});

// Global alert helper
function showGlobalAlert(msg, type='success') {
    const container = document.getElementById('globalAlert');
    if (!container) return;
    const id = 'notif_' + Math.random().toString(36).substr(2, 9);
    const icon = type === 'success' ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill';
    const bg = type === 'success' ? '#10b981' : '#ef4444'; // Emerald 500 / Red 500
    
    const html = `
    <div id="${id}" class="alert animate-slide-in-right d-flex align-items-center gap-3 mb-0 shadow-lg border-0 text-white" 
         style="background:${bg}; border-radius:12px; padding:0.875rem 1.25rem; pointer-events:auto; backdrop-filter:blur(8px); min-height:60px;">
        <div style="background:rgba(255,255,255,0.2); width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
            <i class="bi ${icon} fs-5"></i>
        </div>
        <div style="font-weight:600; font-size:0.875rem; line-height:1.4;">${escapeHtml(msg)}</div>
        <button type="button" class="btn-close btn-close-white ms-auto opacity-50" style="font-size:0.65rem;" onclick="this.parentElement.remove()"></button>
    </div>`;
    
    container.insertAdjacentHTML('beforeend', html);
    
    // Auto-remove after 5s
    setTimeout(() => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.add('animate-slide-out');
            el.addEventListener('animationend', () => el.remove());
        }
    }, 5000);
}

// Helper to fetch user with caching
window.getCurrentUser = async function(forceRefresh = false) {
    if (!localStorage.getItem('auth_hint')) return null;

    if (!forceRefresh) {
        const cached = localStorage.getItem('user_profile');
        if (cached) {
            try { return JSON.parse(cached); } catch (e) { localStorage.removeItem('user_profile'); }
        }
    }

    try {
        const res = await fetch('/api/accounts/me/', { headers: authHeaders() });
        if (res.ok) {
            const user = await res.json();
            localStorage.setItem('user_profile', JSON.stringify(user));
            return user;
        }
        if (res.status === 401) {
            localStorage.removeItem('auth_hint');
            localStorage.removeItem('access');
            localStorage.removeItem('refresh');
            localStorage.removeItem('user_profile');
        }
    } catch (e) { console.error('Auth fetch failed', e); }
    return null;
};

// Update navbar UI based on user
window.updateNavbarUI = function(user) {
    const navAuthLinks = document.getElementById('navAuthLinks');
    if (!navAuthLinks || !user) return;

    const initials = ((user.last_name || '')[0] || '') + ((user.first_name || '')[0] || user.username[0] || '');

    // Workspace navigation lives in the sidebar (app_sidebar.html) on every page, so the
    // top bar only carries account-level actions and never duplicates sidebar links.
    navAuthLinks.innerHTML = `
        <!-- Bell Icon -->
        <button id="navBellBtn" class="nav-btn position-relative" style="background:transparent; border:none; color:#fff; font-size:1.25rem; padding:0 0.5rem;">
            <i class="bi bi-bell-fill"></i>
            <span id="navBellBadge" class="position-absolute translate-middle badge rounded-pill bg-danger" 
                  style="top:8px; right:-12px; font-size:0.6rem; display:none; padding:0.25em 0.5em;">0</span>
        </button>

        <a href="/profile/" class="d-flex align-items-center gap-2 px-2 text-decoration-none" title="Thông tin cá nhân" style="color:inherit;">
            ${user.avatar_url
                ? `<img src="${escapeHtml(user.avatar_url)}" alt="" style="width:30px;height:30px;border-radius:50%;object-fit:cover;">`
                : `<div style="width:30px;height:30px;border-radius:50%;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;color:#fff;">${escapeHtml(initials.toUpperCase())}</div>`}
            <span style="font-size:0.82rem;color:rgba(255,255,255,0.85);font-weight:500;">${escapeHtml(user.first_name || user.username)}</span>
        </a>
        <button class="nav-btn nav-btn-logout" onclick="doLogout()"><i class="bi bi-box-arrow-right"></i> Thoát</button>
    `;
};

// Every authenticated workspace page renders the same sidebar; items are hidden by role.
window.updateAppShell = function(user) {
    const shell = document.querySelector('.app-shell');
    const sidebar = document.getElementById('appSidebar');
    if (!shell || !sidebar) return;

    const role = user?.role?.name;
    const isAdmin = role === 'admin';
    const isTeacher = role === 'teacher' || isAdmin;

    sidebar.hidden = false;
    shell.classList.add('has-sidebar');
    sidebar.querySelectorAll('[data-admin-only]').forEach(el => { el.hidden = !isAdmin; });
    sidebar.querySelectorAll('[data-teacher-only]').forEach(el => { el.hidden = !isTeacher; });

    const path = window.location.pathname.replace(/\/+$/, '') || '/';
    const active = path === '/dashboard' ? 'dashboard'
        : path === '/exams/question-bank' ? 'question-bank'
            : path === '/admin-panel' ? 'admin' : '';
    sidebar.querySelectorAll('[data-nav]').forEach(el => {
        const on = !el.hidden && el.dataset.nav === active;
        el.classList.toggle('is-active', on);
        if (on) el.setAttribute('aria-current', 'page');
        else el.removeAttribute('aria-current');
    });
};

// Flash from sessionStorage
document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem('auth_hint')) {
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
    } else if (window.location.pathname === '/') {
        // Logged-in users should land in their workspace, not the marketing page.
        try {
            const cached = JSON.parse(localStorage.getItem('user_profile') || 'null');
            if (cached) {
                window.location.replace('/dashboard/');
                return;
            }
        } catch (e) { /* ignore malformed cache */ }
        // Fall back to auth hint presence so a missing/stale cache still redirects.
        if (localStorage.getItem('auth_hint')) {
            window.location.replace('/dashboard/');
            return;
        }
    }

    const _alert = sessionStorage.getItem('globalAlert');
    if (_alert) {
        const {msg, type} = JSON.parse(_alert);
        showGlobalAlert(msg, type);
        sessionStorage.removeItem('globalAlert');
    }

    // Update navbar if logged in
    const user = await getCurrentUser(true);
    if (user) {
        if (window.location.pathname === '/') {
            window.location.replace('/dashboard/');
            return;
        }
        updateNavbarUI(user);
        updateAppShell(user);
        setupNotificationPolling();
    }
});

// ── Notifications (Bell & Dropdown) ───────────────────────────────────────

window.refreshNotifCount = async function() {
    if (!localStorage.getItem('auth_hint')) return;
    try {
        const res = await fetch('/api/notifications/unread-count/', { headers: authHeaders() });
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById('navBellBadge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count > 99 ? '99+' : data.count;
                    badge.style.display = 'inline-block';
                } else {
                    badge.style.display = 'none';
                }
            }
        }
    } catch (e) { console.error('Failed to fetch unread count', e); }
};

function setupNotificationPolling() {
    window.refreshNotifCount();
    setInterval(window.refreshNotifCount, 60000); // Polling every 60s

    const bellBtn = document.getElementById('navBellBtn');
    const dropdown = document.getElementById('notifDropdown');
    if (!bellBtn || !dropdown) return;

    // Toggle dropdown
    bellBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isVisible = dropdown.style.display === 'block';
        dropdown.style.display = isVisible ? 'none' : 'block';
        if (!isVisible) loadNotifDropdown();
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    // Mark all read button in dropdown
    const markAllBtn = document.getElementById('notifMarkAllBtn');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!localStorage.getItem('auth_hint')) return;
            await fetch('/api/notifications/mark-all-read/', {
                method: 'POST',
                headers: authHeaders()
            });
            window.refreshNotifCount();
            dropdown.style.display = 'none';
        });
    }
}

async function loadNotifDropdown() {
    const list = document.getElementById('notifList');
    if (!list) return;
    list.innerHTML = '<div class="text-center text-muted py-4 small"><div class="spinner-border spinner-border-sm"></div></div>';
    
    if (!localStorage.getItem('auth_hint')) return;
    
    try {
        // Fetch page 1
        const res = await fetch('/api/notifications/?page=1', { headers: authHeaders() });
        if (!res.ok) throw new Error();
        const data = await res.json();
        const notifs = data.results || [];
        
        if (!notifs.length) {
            list.innerHTML = '<div class="text-center text-muted py-4 small">Không có thông báo mới.</div>';
            return;
        }

        // Show max 5 in dropdown
        list.innerHTML = notifs.slice(0, 5).map(n => {
            const unreadStyle = n.is_read ? '' : 'background:linear-gradient(135deg,#f0f0ff 0%,#fff 100%); border-left:3px solid var(--color-primary,#4f46e5);';
            const url = n.quiz_url || '/notifications/';
            
            // relative time minimal version
            const diff = (Date.now() - new Date(n.created_at)) / 1000;
            let timeStr = 'vừa xong';
            if (diff >= 86400) timeStr = `${Math.floor(diff / 86400)} ngày trước`;
            else if (diff >= 3600) timeStr = `${Math.floor(diff / 3600)} giờ trước`;
            else if (diff >= 60) timeStr = `${Math.floor(diff / 60)} phút trước`;

            return `
            <a href="${escapeHtml(url)}" class="text-decoration-none dropdown-notif-item" data-notif-id="${n.id}" data-is-read="${n.is_read}" style="display:block; padding:0.75rem 1rem; border-bottom:1px solid var(--color-border); ${unreadStyle}">
                <div class="small fw-600 text-dark" style="line-height:1.3; margin-bottom:0.25rem;">${escapeHtml(n.message)}</div>
                <div class="small text-muted" style="font-size:0.7rem;"><i class="bi bi-clock me-1"></i>${timeStr}</div>
            </a>`;
        }).join('');

        // Attach click to mark read
        list.querySelectorAll('.dropdown-notif-item').forEach(el => {
            el.addEventListener('click', async (e) => {
                const id = el.dataset.notifId;
                const isRead = el.dataset.isRead === 'true';
                if (!isRead) {
                    e.preventDefault();
                    await fetch(`/api/notifications/${id}/read/`, {
                        method: 'PATCH',
                        headers: authHeaders()
                    });
                    window.location.href = el.getAttribute('href');
                }
            });
        });
    } catch (e) {
        list.innerHTML = '<div class="text-center text-danger py-4 small">Lỗi tải thông báo.</div>';
    }
}

async function doLogout() {
    try {
        await fetch('/api/accounts/logout/', {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({})
        });
    } catch (e) {}
    localStorage.removeItem('auth_hint');
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    localStorage.removeItem('user_profile');
    window.location.href = '/login/';
}

// ── Report Export Helper (Shared) ────────────────────────────
window.exportReport = async function() {
    if (!localStorage.getItem('auth_hint')) return;

    // Create modal if not exists
    let modalEl = document.getElementById('exportReportModal');
    if (!modalEl) {
        const modalHtml = `
        <div class="modal fade" id="exportReportModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content shadow-lg border-0" style="border-radius:20px; overflow:hidden;">
                    <div class="modal-header border-bottom-0 pb-0 pt-4 px-4">
                        <h5 class="modal-title fw-800" style="font-size:1.4rem; color:var(--color-primary);">Xuất báo cáo Excel</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-4 px-4">
                        <p class="text-muted small mb-4">Vui lòng chọn lớp và khoảng thời gian bạn muốn truy xuất dữ liệu.</p>
                        <div class="mb-4">
                            <label class="form-label fw-700 small text-muted text-uppercase mb-2" style="letter-spacing:0.05em;">1. Chọn lớp học</label>
                            <select id="exportClassSelect" class="form-select shadow-sm border-0 bg-light" style="border-radius:12px; padding:0.85rem 1.25rem; font-weight:500;">
                                <option value="">Tất cả các lớp</option>
                            </select>
                        </div>
                        <div class="row g-3">
                            <div class="col-6">
                                <label class="form-label fw-700 small text-muted text-uppercase mb-2" style="letter-spacing:0.05em;">2. Từ ngày</label>
                                <input type="date" id="exportFromDate" class="form-control shadow-sm border-0 bg-light" style="border-radius:12px; padding:0.85rem 1.25rem;">
                            </div>
                            <div class="col-6">
                                <label class="form-label fw-700 small text-muted text-uppercase mb-2" style="letter-spacing:0.05em;">3. Đến ngày</label>
                                <input type="date" id="exportToDate" class="form-control shadow-sm border-0 bg-light" style="border-radius:12px; padding:0.85rem 1.25rem;">
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer border-top-0 pt-0 pb-4 px-4">
                        <button type="button" id="btnShowReport" class="btn btn-outline-primary border-0 fw-700 rounded-pill px-4">
                            <i class="bi bi-eye me-1"></i> Xem báo cáo
                        </button>
                        <button type="button" id="btnDoExport" class="btn btn-primary px-4 py-2" style="border-radius:12px; font-weight:700; background:var(--color-primary); box-shadow:0 4px 15px rgba(79,70,229,0.3);">
                            <i class="bi bi-cloud-arrow-down-fill me-2"></i> Xuất file ngay
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        modalEl = document.getElementById('exportReportModal');
        
        document.getElementById('btnDoExport').onclick = async () => {
            const cid = document.getElementById('exportClassSelect').value;
            const from = document.getElementById('exportFromDate').value;
            const to = document.getElementById('exportToDate').value;
            
            let params = new URLSearchParams();
            if (cid) params.append('class_id', cid);
            if (from) params.append('from_date', from);
            if (to) params.append('to_date', to);
            
            let url = '/api/accounts/admin/export/?' + params.toString();
            
            const btn = document.getElementById('btnDoExport');
            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Đang tạo file...';
            
            try {
                const res = await fetch(url, { headers: authHeaders() });
                if (!res.ok) throw new Error();
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = window.URL.createObjectURL(blob);
                a.download = `bao_cao_bang_diem_${new Date().getTime()}.xlsx`;
                document.body.appendChild(a); a.click(); a.remove();
                bootstrap.Modal.getInstance(modalEl).hide();
                if (window.showGlobalAlert) showGlobalAlert('Xuất file thành công!');
            } catch (e) {
                alert('Lỗi khi xuất file. Vui lòng thử lại.');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        };

        document.getElementById('btnShowReport').onclick = () => {
            const cid = document.getElementById('exportClassSelect').value;
            const from = document.getElementById('exportFromDate').value;
            const to = document.getElementById('exportToDate').value;
            bootstrap.Modal.getInstance(modalEl).hide();
            window.openReportView(cid, from, to);
        };
    }

    // Load classes dynamically
    try {
        const res = await fetch('/api/classes/', { headers: authHeaders() });
        const classes = await res.json();
        const select = document.getElementById('exportClassSelect');
        const savedVal = select.value;
        select.innerHTML = '<option value="">Tất cả các lớp</option>' + 
            classes.map(c => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)}</option>`).join('');
        if (savedVal) select.value = savedVal;
    } catch (e) { console.error('Failed to load classes for export', e); }

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
};

window.openReportView = function(classId, fromDate, toDate) {
    const section = document.getElementById('reportsSection');
    if (!section) {
        // If not on dashboard, we might want to redirect or show in a large modal
        // For now, assume dashboard integration as requested
        if (window.location.pathname.includes('/admin-panel/')) {
            alert('Vui lòng xem báo cáo tại Dashboard.');
            window.location.href = '/dashboard/';
            return;
        }
        return;
    }
    section.style.display = 'block';
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.loadReports(1, classId, fromDate, toDate);
};

window.loadReports = async function(page = 1, classId = '', fromDate = '', toDate = '') {
    const tbody = document.getElementById('reportsBody');
    if (!tbody) return;

    if (!localStorage.getItem('auth_hint')) return;
    let url = `/api/accounts/admin/report/?page=${page}`;
    if (classId) url += `&class_id=${classId}`;
    if (fromDate) url += `&from_date=${fromDate}`;
    if (toDate) url += `&to_date=${toDate}`;
    
    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-5"><div class="spinner-border spinner-border-sm text-primary"></div></td></tr>';
    
    const res = await fetch(url, { headers: authHeaders() });
    if (res.ok) {
        const data = await res.json();
        renderReports(data.results || data);
        renderReportsPagination(data, classId, fromDate, toDate);
    } else {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-5 text-danger">Lỗi tải dữ liệu báo cáo.</td></tr>';
    }
}

function renderReports(reports) {
    const tbody = document.getElementById('reportsBody');
    if (!tbody) return;
    if (!reports || !reports.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-5 text-muted">Không có dữ liệu nộp bài nào.</td></tr>';
        return;
    }
    
    tbody.innerHTML = reports.map(r => `
        <tr class="fade-in-row">
            <td class="px-4">
                <div class="fw-bold text-dark">${escapeHtml(r.student_name)}</div>
                <div class="small text-muted font-monospace">${escapeHtml(r.student_code)}</div>
            </td>
            <td><span class="badge bg-light text-dark border rounded-pill px-2">${escapeHtml(r.class_name)}</span></td>
            <td><div class="small fw-semibold text-truncate" style="max-width:200px;">${escapeHtml(r.quiz_title)}</div></td>
            <td class="text-center">
                <span class="badge rounded-pill ${r.score >= 5 ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'} px-3 shadow-none border">
                    ${escapeHtml(r.score)}/10
                </span>
            </td>
            <td class="text-end text-muted small px-4">${new Date(r.completed_at).toLocaleString('vi-VN')}</td>
        </tr>
    `).join('');
}

function renderReportsPagination(data, classId, fromDate, toDate) {
    const container = document.getElementById('reportsPagination');
    if (!container) return;
    if (!data.count || data.count <= (data.results?.length || 0)) {
        container.innerHTML = `<small class="text-muted">Hiển thị tất cả ${data.count || 0} kết quả</small>`;
        return;
    }
    
    let html = `<nav aria-label="Page navigation"><ul class="pagination pagination-sm mb-0">`;
    const totalPages = Math.ceil(data.count / (data.page_size || 50));
    const currentPage = data.page || 1;
    
    for (let i = 1; i <= totalPages; i++) {
        html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
            <a class="page-link" href="#" onclick="event.preventDefault(); window.loadReports(${i}, '${classId}', '${fromDate}', '${toDate}')">${i}</a>
        </li>`;
    }
    html += `</ul></nav>`;
    container.innerHTML = html;
}
