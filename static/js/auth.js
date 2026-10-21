// Helper to toggle password visibility
function togglePwd(id, eyeId) {
    const inp = document.getElementById(id);
    const eye = document.getElementById(eyeId);
    if (!inp || !eye) return;
    if (inp.type === 'password') { inp.type = 'text'; eye.className = 'bi bi-eye-slash'; }
    else { inp.type = 'password'; eye.className = 'bi bi-eye'; }
}

// Check password strength for registration
function checkStrength(val) {
    const bar = document.getElementById('strengthBar');
    const fill = document.getElementById('strengthFill');
    const text = document.getElementById('strengthText');
    if (!bar || !fill || !text) return;

    bar.style.display = val.length ? 'block' : 'none';
    let score = 0;
    if (val.length >= 8) score++;
    if (/[A-Z]/.test(val)) score++;
    if (/[0-9]/.test(val)) score++;
    if (/[^A-Za-z0-9]/.test(val)) score++;
    const levels = [
        {w: '25%', c: '#EF4444', l: 'Quá yếu'},
        {w: '50%', c: '#F59E0B', l: 'Yếu'},
        {w: '75%', c: '#3B82F6', l: 'Trung bình'},
        {w: '100%', c: '#10B981', l: 'Mạnh'},
    ];
    const lv = levels[score - 1] || levels[0];
    fill.style.width = lv.w;
    fill.style.background = lv.c;
    text.textContent = lv.l;
    text.style.color = lv.c;
    return score;
}

function showFieldError(fieldId, msg) {
    const errEl = document.getElementById(`err_${fieldId}`);
    const inputEl = document.getElementById(fieldId);
    if (errEl) {
        errEl.textContent = msg;
        errEl.classList.remove('d-none');
    }
    if (inputEl) {
        inputEl.classList.add('is-invalid');
    }
}

function clearFieldErrors() {
    document.querySelectorAll('.text-danger').forEach(el => {
        if (el.id && el.id.startsWith('err_')) {
            el.textContent = '';
            el.classList.add('d-none');
        }
    });
    document.querySelectorAll('.form-control').forEach(el => {
        el.classList.remove('is-invalid');
    });
    const regErr = document.getElementById('registerError');
    if (regErr) regErr.classList.add('d-none');
}

// Attach login form submission
document.addEventListener('DOMContentLoaded', () => {
    // Real-time validation for registration
    const regFields = ['first_name', 'last_name', 'reg_email', 'reg_username', 'reg_password'];
    regFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                el.classList.remove('is-invalid');
                const err = document.getElementById(`err_${id}`);
                if (err) err.classList.add('d-none');
            });
        }
    });

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.onsubmit = async function(e) {
            e.preventDefault();
            const errEl = document.getElementById('loginError');
            if (errEl) errEl.classList.add('d-none');
            
            const btnText = document.getElementById('loginBtnText');
            const btnSpinner = document.getElementById('loginBtnSpinner');
            const btn = document.getElementById('loginBtn');
            
            if (btnText) btnText.classList.add('d-none');
            if (btnSpinner) btnSpinner.classList.remove('d-none');
            if (btn) btn.disabled = true;
        
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            try {
                const res = await fetch('/api/accounts/login/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });
                const data = await res.json();
                if (res.ok && data.access) {
                    localStorage.removeItem('access');
                    localStorage.removeItem('refresh');
                    localStorage.removeItem('user_profile');
                    localStorage.setItem('auth_hint', '1');
                    sessionStorage.setItem('globalAlert', JSON.stringify({msg: '✅ Đã đăng nhập thành công!', type: 'success'}));
                    window.location.href = '/dashboard/';
                } else {
                    if (errEl) {
                        errEl.textContent = data.detail || 'Tên đăng nhập hoặc mật khẩu không đúng.';
                        errEl.classList.remove('d-none');
                    }
                }
            } catch (e) {
                if (errEl) {
                    errEl.textContent = 'Lỗi kết nối máy chủ. Vui lòng thử lại.';
                    errEl.classList.remove('d-none');
                }
            }
            if (btnText) btnText.classList.remove('d-none');
            if (btnSpinner) btnSpinner.classList.add('d-none');
            if (btn) btn.disabled = false;
        };
    }

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.onsubmit = async function(e) {
            e.preventDefault();
            clearFieldErrors();

            const firstName = document.getElementById('first_name').value.trim();
            const lastName = document.getElementById('last_name').value.trim();
            const email = document.getElementById('reg_email').value.trim();
            const username = document.getElementById('reg_username').value.trim();
            const password = document.getElementById('reg_password').value;
            
            let isValid = true;

            if (!lastName) { showFieldError('last_name', 'Vui lòng nhập họ.'); isValid = false; }
            if (!firstName) { showFieldError('first_name', 'Vui lòng nhập tên.'); isValid = false; }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!email) { showFieldError('reg_email', 'Vui lòng nhập email.'); isValid = false; }
            else if (!emailRegex.test(email)) { showFieldError('reg_email', 'Email không đúng định dạng.'); isValid = false; }

            if (!username) { showFieldError('reg_username', 'Vui lòng nhập tên đăng nhập.'); isValid = false; }
            else if (username.length < 3) { showFieldError('reg_username', 'Tên đăng nhập phải có ít nhất 3 ký tự.'); isValid = false; }
            else if (!/^[a-zA-Z0-9_]+$/.test(username)) { showFieldError('reg_username', 'Tên đăng nhập chỉ chứa chữ cái, số và dấu gạch dưới.'); isValid = false; }

            const pwdScore = checkStrength(password);
            if (!password) { showFieldError('reg_password', 'Vui lòng nhập mật khẩu.'); isValid = false; }
            else if (password.length < 8) { showFieldError('reg_password', 'Mật khẩu phải có ít nhất 8 ký tự.'); isValid = false; }
            else if (pwdScore < 3) { showFieldError('reg_password', 'Mật khẩu quá yếu. Hãy dùng thêm chữ hoa, số và ký tự đặc biệt.'); isValid = false; }

            if (!isValid) return;

            document.getElementById('regBtnText').classList.add('d-none');
            document.getElementById('regBtnSpinner').classList.remove('d-none');
            document.getElementById('regBtn').disabled = true;
        
            const roleEl = document.querySelector('input[name="role"]:checked');
            const payload = {
                email,
                username,
                password,
                first_name: firstName,
                last_name: lastName,
                role_name: roleEl ? roleEl.value : 'student',
            };
            try {
                const res = await fetch('/api/accounts/register/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    sessionStorage.setItem('globalAlert', JSON.stringify({msg: '🎉 Đăng ký thành công! Hãy đăng nhập để tiếp tục.', type: 'success'}));
                    window.location.href = '/login/';
                } else {
                    const data = await res.json();
                    const errEl = document.getElementById('registerError');
                    if (data.username) showFieldError('reg_username', data.username.join(' '));
                    if (data.email) showFieldError('reg_email', data.email.join(' '));
                    
                    if (errEl && !data.username && !data.email) {
                        const msgs = Object.values(data).flat().join(' • ');
                        errEl.textContent = msgs || 'Đăng ký thất bại. Vui lòng kiểm tra lại thông tin.';
                        errEl.classList.remove('d-none');
                    }
                }
            } catch (e) {
                const errEl = document.getElementById('registerError');
                if (errEl) {
                    errEl.textContent = 'Lỗi kết nối máy chủ.';
                    errEl.classList.remove('d-none');
                }
            }
            document.getElementById('regBtnText').classList.remove('d-none');
            document.getElementById('regBtnSpinner').classList.add('d-none');
            document.getElementById('regBtn').disabled = false;
        };
    }
});
