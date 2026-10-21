(function () {
    const ROLE_LABELS = { student: 'Học sinh', teacher: 'Giáo viên', admin: 'Quản trị viên' };

    function errorMessage(data, fallback) {
        if (!data || typeof data !== 'object') return fallback;
        const parts = [];
        Object.values(data).forEach((value) => {
            if (Array.isArray(value)) parts.push(value.join(' '));
            else if (typeof value === 'string') parts.push(value);
        });
        return parts.join(' ') || fallback;
    }

    function initials(user) {
        return (((user.last_name || '')[0] || '') + ((user.first_name || '')[0] || (user.username || '')[0] || '')).toUpperCase();
    }

    function renderAvatar(user) {
        const el = document.getElementById('profileAvatar');
        if (user.avatar_url) {
            el.innerHTML = `<img src="${escapeHtml(user.avatar_url)}" alt="" style="width:100%;height:100%;object-fit:cover;">`;
        } else {
            el.textContent = initials(user);
        }
    }

    function renderHeader(user) {
        document.getElementById('profileFullName').textContent = user.full_name || `${user.last_name || ''} ${user.first_name || ''}`.trim() || user.username;
        document.getElementById('profileRole').textContent = ROLE_LABELS[user.role?.name] || user.role?.name || '';
    }

    document.addEventListener('DOMContentLoaded', async () => {
        const user = await getCurrentUser(true);
        if (!user) {
            window.location.href = '/login/';
            return;
        }

        document.getElementById('profileLoading').style.display = 'none';
        document.getElementById('profileContent').style.display = 'flex';

        document.getElementById('profileUsername').value = user.username;
        document.getElementById('profileLastName').value = user.last_name || '';
        document.getElementById('profileFirstName').value = user.first_name || '';
        document.getElementById('profileEmail').value = user.email || '';
        document.getElementById('profileAvatarUrl').value = user.avatar_url || '';
        renderAvatar(user);
        renderHeader(user);

        document.getElementById('profileAvatarUrl').addEventListener('input', (e) => {
            renderAvatar({ ...user, avatar_url: e.target.value.trim() });
        });

        document.getElementById('profileForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('profileSaveBtn');
            btn.disabled = true;
            try {
                const res = await fetch('/api/accounts/me/', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: document.getElementById('profileEmail').value.trim(),
                        first_name: document.getElementById('profileFirstName').value.trim(),
                        last_name: document.getElementById('profileLastName').value.trim(),
                        avatar_url: document.getElementById('profileAvatarUrl').value.trim(),
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    showGlobalAlert(errorMessage(data, 'Không thể cập nhật thông tin cá nhân.'), 'error');
                    return;
                }
                localStorage.setItem('user_profile', JSON.stringify(data));
                updateNavbarUI(data);
                renderAvatar(data);
                renderHeader(data);
                showGlobalAlert('Đã cập nhật thông tin cá nhân.');
            } catch (err) {
                showGlobalAlert('Lỗi kết nối. Vui lòng thử lại sau.', 'error');
            } finally {
                btn.disabled = false;
            }
        });

        document.getElementById('passwordForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const currentPassword = document.getElementById('currentPassword');
            const newPassword = document.getElementById('newPassword');
            const confirmPassword = document.getElementById('confirmPassword');

            if (newPassword.value !== confirmPassword.value) {
                showGlobalAlert('Mật khẩu mới nhập lại không khớp.', 'error');
                return;
            }

            const btn = document.getElementById('passwordSaveBtn');
            btn.disabled = true;
            try {
                const res = await fetch('/api/accounts/me/password/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        current_password: currentPassword.value,
                        new_password: newPassword.value,
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    showGlobalAlert(errorMessage(data, 'Không thể đổi mật khẩu.'), 'error');
                    return;
                }
                document.getElementById('passwordForm').reset();
                showGlobalAlert('Đổi mật khẩu thành công.');
            } catch (err) {
                showGlobalAlert('Lỗi kết nối. Vui lòng thử lại sau.', 'error');
            } finally {
                btn.disabled = false;
            }
        });
    });
})();
