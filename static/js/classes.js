function escapeHtml(value) {
    return (value ?? '').toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
    let currentRole = null;
    const subjectColors = ['primary','success','warning','danger','info','secondary'];
    
    if (!localStorage.getItem('auth_hint')) window.location.href = '/login/';
    
    function authH() { return {'Content-Type':'application/json'}; }
    function formatDate(dt) { return new Date(dt).toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric'}); }
    
    async function init() {
        const pageTitle = document.getElementById('pageTitle');
        if (!pageTitle) return; // Not on classes page

        const me = await window.getCurrentUser(true);
        if (!me) { window.location.href = '/login/'; return; }
        currentRole = me.role?.name;
    
        if (currentRole === 'teacher') {
            document.getElementById('btnCreateClass').classList.remove('d-none');
            document.getElementById('pageTitle').textContent = 'Lớp tôi dạy';
            document.getElementById('pageSubtitle').textContent = 'Tạo và quản lý lớp học, theo dõi tiến độ học sinh';
            await loadSubjects();
        } else if (currentRole === 'student') {
            document.getElementById('btnJoinClass').classList.remove('d-none');
            document.getElementById('pageTitle').textContent = 'Lớp của tôi';
            document.getElementById('pageSubtitle').textContent = 'Các lớp học bạn đang tham gia';
        } else if (currentRole === 'admin') {
            document.getElementById('pageTitle').textContent = 'Tất cả lớp học';
            document.getElementById('pageSubtitle').textContent = 'Danh sách toàn bộ lớp học trong hệ thống';
        }
        await loadClasses();
    }
    
    async function loadSubjects() {
        const res = await fetch('/api/classes/subjects/', {headers: authH()});
        if (!res.ok) return;
        const data = await res.json();
        const sel = document.getElementById('subjectSelect');
        data.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id; opt.textContent = s.name; sel.appendChild(opt);
        });
    }
    
    async function loadClasses() {
        const res = await fetch('/api/classes/', {headers: authH()});
        document.getElementById('classesLoading').style.display = 'none';
        if (!res.ok) return;
        const classes = await res.json();
        const grid = document.getElementById('classList');
        grid.style.display = 'flex'; grid.className = 'row g-3'; grid.innerHTML = '';
    
        if (!classes.length) {
            document.getElementById('noClassMsg').style.display = 'block';
            if (currentRole === 'teacher')  document.getElementById('noClassText').textContent = 'Bạn chưa tạo lớp nào. Bắt đầu bằng cách nhấn "Tạo lớp mới".';
            if (currentRole === 'student')  document.getElementById('noClassText').textContent = 'Bạn chưa tham gia lớp nào. Nhấn "Tham gia lớp" để vào lớp.';
            return;
        }
        document.getElementById('noClassMsg').style.display = 'none';
    
        classes.forEach((cls, i) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 animate-in';
            col.style.animationDelay = (i * 0.05) + 's';
            const teacherName = [cls.teacher?.last_name, cls.teacher?.first_name].filter(Boolean).join(' ') || cls.teacher?.username || '–';
            const safeName = escapeHtml(cls.name);
            const color = subjectColors[i % subjectColors.length];
            col.innerHTML = `
                <div class="class-card" onclick="window.location.href='/classes/${cls.id}/'">
                    <div class="class-card-top" style="background:linear-gradient(90deg,var(--color-${color}),var(--color-secondary));"></div>
                    <div class="class-card-body">
                        <div class="d-flex align-items-start justify-content-between gap-2 mb-2">
                            <h6 class="class-name mb-0">${safeName}</h6>
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge" style="background:var(--color-${color}-light,var(--color-primary-light));color:var(--color-${color},var(--color-primary));white-space:nowrap;">${escapeHtml(cls.subject_name || 'Chưa có môn')}</span>
                                ${(currentRole === 'teacher' || currentRole === 'admin') ? `
                                <button class="btn btn-link text-danger p-0 border-0" data-name="${safeName}" onclick="event.stopPropagation(); deleteClass('${cls.id}', this.dataset.name)" title="Xoá lớp" style="box-shadow:none;">
                                    <i class="bi bi-trash"></i>
                                </button>` : ''}
                            </div>
                        </div>
                        <div class="class-meta d-flex flex-column gap-1">
                            <span><i class="bi bi-person-fill me-1"></i>${escapeHtml(teacherName)}</span>
                            <span><i class="bi bi-people me-1"></i>${cls.student_count} học sinh</span>
                            ${currentRole !== 'student' ? `
                            <div class="d-flex justify-content-between align-items-center border-top pt-2 mt-1">
                                <span class="small" title="Bài thi"><i class="bi bi-file-earmark-text text-danger me-1"></i>${cls.total_quizzes ?? 0}</span>
                                <span class="small" title="Lượt nộp"><i class="bi bi-send-check text-success me-1"></i>${cls.total_attempts ?? 0}</span>
                                <span class="small" title="Điểm trung bình"><i class="bi bi-star-half text-warning me-1"></i><strong>${cls.avg_score ?? 0}</strong></span>
                            </div>` : ''}
                        </div>
                    </div>
                    <div class="class-footer">
                        <span style="font-size:0.78rem;color:var(--color-muted);"><i class="bi bi-key me-1"></i>Mã: <strong style="color:var(--color-text);font-family:monospace;">${escapeHtml(cls.invite_code)}</strong></span>
                        <span style="font-size:0.78rem;color:var(--color-muted);"><i class="bi bi-calendar3 me-1"></i>${formatDate(cls.created_at)}</span>
                    </div>
                </div>`;
            grid.appendChild(col);
        });
    }
    
    window.submitCreateClass = async function() {
        const errEl = document.getElementById('createClassError');
        errEl.textContent = '';
        const name = document.getElementById('className').value.trim();
        const subject = document.getElementById('subjectSelect').value;
        const description = document.getElementById('classDesc').value.trim();
        if (!name || !subject) { errEl.textContent = 'Vui lòng điền đầy đủ tên lớp và môn học.'; return; }
    
        const res = await fetch('/api/classes/', {
            method: 'POST', headers: authH(),
            body: JSON.stringify({name, subject, description})
        });
        const data = await res.json();
        if (res.ok) {
            bootstrap.Modal.getInstance(document.getElementById('createClassModal')).hide();
            document.getElementById('createClassForm').reset();
            showGlobalAlert(`✅ Tạo lớp ${data.name} thành công! Mã lớp: ${data.invite_code}`, 'success');
            await loadClasses();
        } else {
            errEl.textContent = Object.values(data).flat().join(' • ') || 'Tạo lớp thất bại.';
        }
    }
    
    window.submitJoinClass = async function() {
        const errEl = document.getElementById('joinError');
        errEl.textContent = '';
        const invite_code = document.getElementById('inviteCode').value.trim().toUpperCase();
        if (invite_code.length !== 8) { errEl.textContent = 'Mã lớp phải gồm đúng 8 ký tự.'; return; }
    
        const res = await fetch('/api/classes/join/', {
            method: 'POST', headers: authH(),
            body: JSON.stringify({invite_code})
        });
        const data = await res.json();
        if (res.ok) {
            bootstrap.Modal.getInstance(document.getElementById('joinClassModal')).hide();
            document.getElementById('inviteCode').value = '';
            showGlobalAlert(`🎉 Đã tham gia lớp ${data.class_name} thành công!`, 'success');
            await loadClasses();
        } else {
            errEl.textContent = data.detail || 'Tham gia lớp thất bại.';
        }
    }

    window.deleteClass = async function(id, name) {
        if (!confirm(`Bạn có chắc chắn muốn xoá lớp "${name}"? Thao tác này sẽ xoá toàn bộ bài thi, kết quả và tài liệu liên quan và không thể hoàn tác.`)) return;
        
        const res = await fetch(`/api/classes/${id}/`, {
            method: 'DELETE',
            headers: authH()
        });
        
        if (res.ok) {
            showGlobalAlert(`Đã xoá lớp ${name} thành công.`, 'success');
            await loadClasses();
        } else {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || 'Xoá lớp thất bại.');
        }
    }

    init();
});
