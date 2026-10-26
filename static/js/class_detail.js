window.switchTab = function(targetId, btn) {
    document.querySelectorAll('.tab-content-pane').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.nvh-tab').forEach(b => b.classList.remove('active'));
    document.getElementById(targetId).style.display = 'block';
    btn.classList.add('active');
}

document.addEventListener('DOMContentLoaded', () => {
    const classDetailContent = document.getElementById('classDetailContent');
    if (!classDetailContent) return;

    const classId = window.CLASS_ID; // Defined in template
    if (!classId) return;

    let currentRole = null;
    let globalAnalyticsData = null;
    let aiChatInitialized = false;

    if (!localStorage.getItem('auth_hint')) window.location.href = '/login/';
    function authHeaders() { return {'Content-Type':'application/json'}; }

    async function init() {
        try {
            const me = await window.getCurrentUser(true);
            if (!me) { window.location.href = '/login/'; return; }
            currentRole = me.role?.name;
            await Promise.all([loadClassDetail(), loadQuizzes(), loadMembers(), loadRAGDocuments()]);
            if (currentRole === 'teacher' || currentRole === 'admin') {
                const insightTabBtn = document.getElementById('teacher-insight-tab-btn');
                if (insightTabBtn) insightTabBtn.classList.remove('d-none');
                
                const uploadBtn = document.getElementById('btnUploadDoc');
                if (uploadBtn) uploadBtn.style.display = 'inline-block';
            }
            document.getElementById('loadingClass').style.display = 'none';
            document.getElementById('classDetailContent').style.display = 'block';
        } catch(e) { console.error(e); }
    }

    window.loadClassInsight = async function() {
        const loading = document.getElementById('analyticsLoading');
        const display = document.getElementById('analyticsDisplay');
        loading.style.display = 'block'; display.style.display = 'none';
        try {
            const res = await fetch(`/api/exams/analytics/${classId}/`, {headers: authHeaders()});
            const data = await res.json();
            globalAnalyticsData = data;
            const grid = document.getElementById('quizStatsGrid');
            grid.innerHTML = '';
            if (!data.quizzes || !data.quizzes.length) {
                grid.innerHTML = '<div class="col-12 text-muted text-center small py-2">Chưa có dữ liệu.</div>';
            } else {
                data.quizzes.forEach(q => {
                    const safeTitle = escapeHtml(q.quiz_title);
                    grid.innerHTML += `<div class="col-md-4"><div class="kpi-card success"><div class="kpi-icon success"><i class="bi bi-award-fill"></i></div><div class="kpi-num">${q.average_score}</div><div class="kpi-label" title="${safeTitle}">${safeTitle.slice(0,18)}… (${q.total_attempts})</div></div></div>`;
                });
            }
            loading.style.display = 'none'; display.style.display = 'block';
        } catch(e) { document.getElementById('quizStatsGrid').innerHTML = '<div class="col-12 text-danger small">Lỗi tải dữ liệu.</div>'; }
    }

    window.generateAIInsight = async function() {
        if (!globalAnalyticsData || !globalAnalyticsData.quizzes) { alert("Chưa thống kê được dữ liệu hoặc chưa load xong KPI."); return; }
        const textEl = document.getElementById('aiInsightText');
        const btn = document.querySelector('button[onclick="generateAIInsight()"]');
        if (btn) {
            btn.innerHTML = '<span class="spinner-grow spinner-grow-sm me-2"></span>Đang phân tích...';
            btn.disabled = true;
        }
        textEl.innerHTML = '<div class="text-center p-3 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Đang phân tích dữ liệu, vui lòng đợi...</div>';
        
        try {
            const res = await fetch('/api/ai/insight/', {
                method:'POST',
                headers:authHeaders(),
                body:JSON.stringify({
                    class_id: classId,
                    analytics_data: globalAnalyticsData,
                    class_name: globalAnalyticsData.class_name
                })
            });
            const data = await res.json();
            
            if (res.ok) { 
                renderInsight(data.insight);
                updateInsightGenerateButton(data.can_generate, data.days_remaining);
            } else { 
                if (res.status === 429) {
                    textEl.innerHTML = `<div class="alert alert-warning"><i class="bi bi-clock-history me-2"></i>${escapeHtml(data.error)}</div>`;
                    updateInsightGenerateButton(false, data.days_remaining || 0);
                } else {
                    textEl.innerHTML = `<div class="alert alert-danger">Lỗi: ${escapeHtml(data.error || "Không thể lấy insight.")}</div>`;
                    if (btn) {
                        btn.innerHTML = "Thử lại";
                        btn.disabled = false;
                    }
                }
            }
        } catch(e) {
            textEl.innerHTML = "Lỗi kết nối AI.";
            if (btn) {
                btn.innerHTML = "Thử lại";
                btn.disabled = false;
            }
        }
    }

    window.loadSavedInsight = async function() {
        if (!classId || (currentRole !== 'teacher' && currentRole !== 'admin')) return;
        const textEl = document.getElementById('aiInsightText');
        if (!textEl) return;
        textEl.innerHTML = `<div class="d-flex align-items-center text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Đang tải...</div>`;
        
        try {
            const res = await fetch(`/api/ai/insight/?class_id=${classId}`, {headers: authHeaders()});
            const data = await res.json();
            
            if (res.ok && data.insight) {
                renderInsight(data.insight);
                const updatedAt = new Date(data.updated_at).toLocaleString('vi-VN');
                const updateNotice = document.createElement('div');
                updateNotice.className = 'text-muted small mt-4 text-end';
                updateNotice.innerHTML = `<em>Cập nhật lần cuối: ${updatedAt}</em>`;
                textEl.appendChild(updateNotice);
            } else {
                textEl.innerHTML = '<div class="text-muted text-center p-4">Chưa có báo cáo nào. Hãy nhấn nút để AI phân tích dữ liệu lớp học hiện tại.</div>';
            }
            updateInsightGenerateButton(data.can_generate, data.days_remaining);
        } catch(e) {
            textEl.innerHTML = '<div class="alert alert-danger">Không thể tải báo cáo.</div>';
        }
    }

    function renderInsight(markdownText) {
        const textEl = document.getElementById('aiInsightText');
        if (!textEl) return;
        
        // Custom simple Markdown parser (escape first, then apply controlled formatting)
        let html = escapeHtml(markdownText)
            .replace(/^### (.*$)/gim, '<h5 class="mt-3 mb-2" style="font-weight:700;color:var(--color-primary);">$1</h5>')
            .replace(/^## (.*$)/gim, '<h4 class="mt-3 mb-2" style="font-weight:700;">$1</h4>')
            .replace(/^# (.*$)/gim, '<h3 class="mt-3 mb-2" style="font-weight:800;">$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
        
        textEl.innerHTML = html;
        if (window.MathJax) {
            window.MathJax.typesetPromise([textEl]).catch((err) => console.error("MathJax error:", err));
        }
    }

    function updateInsightGenerateButton(canGenerate, daysRemaining) {
        const btn = document.querySelector('button[onclick="generateAIInsight()"]');
        if (!btn) return;
        
        if (canGenerate) {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-stars"></i> Phân tích Báo Cáo AI Mới`;
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');
        } else {
            btn.disabled = true;
            btn.innerHTML = `<i class="bi bi-clock-history"></i> Có thể làm mới sau ${daysRemaining} ngày`;
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
        }
    }

    async function loadClassDetail() {
        const res = await fetch(`/api/classes/${classId}/`, {headers: authHeaders()});
        const cls = await res.json();
        document.getElementById('classNameTitle').textContent = cls.name;
        document.getElementById('breadcrumbClassName').textContent = cls.name;
        document.getElementById('classSubjectBadge').textContent = cls.subject_name;
        document.getElementById('classDescText').textContent = cls.description || 'Chưa có mô tả cho lớp học này.';
        document.getElementById('inviteCode').textContent = cls.invite_code;
        document.getElementById('studentCount').textContent = cls.student_count;
        const teacherName = [cls.teacher?.last_name, cls.teacher?.first_name].filter(Boolean).join(' ') || cls.teacher?.username;
        document.getElementById('teacherName').textContent = teacherName;
        if (currentRole === 'teacher' || currentRole === 'admin') {
            document.getElementById('teacherActionGroup').style.display = 'block';
            const teacherAddPanel = document.getElementById('teacherAddStudentPanel');
            if (teacherAddPanel) teacherAddPanel.classList.remove('d-none');
            document.getElementById('statTotalQuizzes').textContent = cls.total_quizzes || 0;
            document.getElementById('statTotalAttempts').textContent = cls.total_attempts || 0;
            document.getElementById('statAvgScore').textContent = cls.avg_score || 0;
            document.getElementById('classStatsGroup').classList.remove('d-none');
        }
    }

    window.openQuiz = function(id) {
        window.location.href = (currentRole === 'teacher' || currentRole === 'admin') ? `/exams/builder/${id}/` : `/exams/taker/${id}/`;
    }

    async function loadQuizzes() {
        let url = currentRole === 'student' ? `/api/exams/my-quizzes/?class_id=${classId}` : `/api/exams/?class_id=${classId}`;
        const res = await fetch(url, {headers: authHeaders()});
        let quizzes = await res.json();
        const grid = document.getElementById('quizList');
        grid.innerHTML = '';
        if (!quizzes.length) { document.getElementById('noQuizMsg').style.display = 'block'; return; }
        document.getElementById('noQuizMsg').style.display = 'none';
        const isTeacher = currentRole === 'teacher' || currentRole === 'admin';
        quizzes.forEach((q, i) => {
            const col = document.createElement('div');
            col.className = 'col-12 animate-in';
            col.style.animationDelay = (i * 0.04) + 's';
            let statusBadge = '', footerAction = '';
            if (isTeacher) {
                statusBadge = `<span class="badge" style="background:${q.is_published ? 'var(--color-success-light)' : 'var(--color-border)'};color:${q.is_published ? 'var(--color-success)' : 'var(--color-muted)'};">${q.is_published ? '● Công khai' : '○ Nháp'}</span>`;
                footerAction = `<div class="d-flex gap-1">
                    <button class="btn btn-sm btn-primary" onclick="openQuiz('${q.id}')">Chi tiết & Sửa</button>
                    <button class="btn btn-sm btn-outline-secondary" data-title="${escapeHtml(q.title)}" onclick="openCopyQuizModal('${q.id}', this.dataset.title)" title="Sao chép sang lớp khác">
                        <i class="bi bi-files"></i>
                    </button>
                </div>`;
            } else if (q.my_attempt?.is_completed) {
                statusBadge = `<span class="badge" style="background:var(--color-success-light);color:var(--color-success);">✓ Đã nộp ${q.my_attempt.score}/10đ</span>`;
                footerAction = `<button class="btn btn-sm btn-outline-success" onclick="openQuiz('${q.id}')">Xem kết quả</button>`;
            } else if (q.my_attempt) {
                statusBadge = `<span class="badge" style="background:var(--color-warning-light);color:var(--color-warning);">Đang làm dở</span>`;
                footerAction = `<button class="btn btn-sm btn-primary" onclick="openQuiz('${q.id}')">Tiếp tục thi</button>`;
            } else {
                statusBadge = `<span class="badge" style="background:var(--color-primary-light);color:var(--color-primary);">Kỳ thi mới</span>`;
                footerAction = `<button class="btn btn-sm btn-primary" onclick="openQuiz('${q.id}')">Làm bài</button>`;
            }
            col.innerHTML = `
                <div class="d-flex align-items-center justify-content-between p-3 mb-2 shadow-sm rounded border" style="background:var(--color-surface);transition:var(--transition);" onmouseenter="this.style.transform='translateY(-2px)';" onmouseleave="this.style.transform='';">
                    <div class="d-flex align-items-center gap-3 w-100">
                        <div style="width:48px;height:48px;border-radius:12px;background:var(--color-primary-light);color:var(--color-primary);display:flex;align-items:center;justify-content:center;font-size:1.4rem;flex-shrink:0;">
                            <i class="bi bi-journal-text"></i>
                        </div>
                        <div style="flex-grow:1;overflow:hidden;">
                            <h6 style="font-weight:700;margin-bottom:0.25rem;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" onclick="openQuiz('${q.id}')">${escapeHtml(q.title)}</h6>
                            <div class="d-flex align-items-center gap-3 flex-wrap" style="font-size:0.78rem;color:var(--color-muted);">
                                <span><i class="bi bi-clock me-1 text-warning"></i>${q.duration_minutes} phút</span>
                                <span><i class="bi bi-file-earmark-text me-1 text-info"></i>${q.question_count} câu</span>
                                ${statusBadge}
                            </div>
                        </div>
                        <div style="flex-shrink:0;">${footerAction}</div>
                    </div>
                </div>`;
            grid.appendChild(col);
        });
    }

    async function loadMembers() {
        try {
            const res = await fetch(`/api/classes/${classId}/students/`, {headers: authHeaders()});
            const list = document.getElementById('memberListSmall');
            const memberCountBadge = document.getElementById('memberCountBadge');
            if (res.status === 403) { list.innerHTML = '<li class="list-group-item text-muted small py-3">Không có quyền xem.</li>'; return; }
            const data = await res.json();
            if (memberCountBadge) memberCountBadge.textContent = data.students?.length || 0;
            if (!data.students?.length) { list.innerHTML = '<li class="list-group-item text-muted small py-3 text-center">Chưa có học sinh.</li>'; return; }
            
            const isTeacher = currentRole === 'teacher' || currentRole === 'admin';
            
            list.innerHTML = data.students.map(s => {
                const name = s.full_name || s.username;
                const safeName = escapeHtml(name);
                const safeUsername = escapeHtml(s.username);
                const initial = escapeHtml(name.charAt(0).toUpperCase());
                
                let removeBtn = '';
                if (isTeacher) {
                    removeBtn = `<button class="btn btn-sm text-danger p-1" title="Xóa học sinh" data-name="${safeName}" onclick="removeStudent('${s.id}', this.dataset.name)">
                        <i class="bi bi-trash"></i>
                    </button>`;
                }

                return `<li class="list-group-item d-flex justify-content-between align-items-center gap-2 py-2 px-3 border-0 border-bottom">
                    <div class="d-flex align-items-center gap-3">
                        <div style="width:34px;height:34px;border-radius:50%;background:var(--color-primary-light);color:var(--color-primary);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8rem;flex-shrink:0;">${initial}</div>
                        <div><div style="font-weight:600;font-size:0.875rem;">${safeName}</div><div style="font-size:0.72rem;color:var(--color-muted);">@${safeUsername}</div></div>
                    </div>
                    ${removeBtn}
                </li>`;
            }).join('');
        } catch(e) { document.getElementById('memberListSmall').innerHTML = '<li class="list-group-item text-danger small">Lỗi tải thành viên.</li>'; }
    }

    window.submitAddStudent = async function(clsId) {
        const input = document.getElementById('addStudentInput');
        const identifier = input.value.trim();
        if (!identifier) return;
        
        const btn = document.getElementById('addStudentBtn');
        const msg = document.getElementById('addStudentMsg');
        btn.disabled = true; msg.style.display = 'none';
        
        try {
            const res = await fetch(`/api/classes/${clsId}/students/add/`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ identifier })
            });
            const data = await res.json();
            
            msg.style.display = 'block';
            if (res.ok) {
                msg.className = 'small mt-2 text-success';
                msg.innerHTML = '<i class="bi bi-check-circle me-1"></i>' + escapeHtml(data.detail);
                input.value = '';
                await loadMembers();
            } else {
                msg.className = 'small mt-2 text-danger';
                msg.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>' + escapeHtml(data.detail || 'Có lỗi xảy ra.');
            }
        } catch (e) {
            msg.style.display = 'block';
            msg.className = 'small mt-2 text-danger';
            msg.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Lỗi kết nối.';
        } finally {
            btn.disabled = false;
        }
    }

    window.removeStudent = async function(studentId, name) {
        if (!confirm(`Xóa học sinh ${name} khỏi lớp này?`)) return;
        try {
            const res = await fetch(`/api/classes/${window.CLASS_ID}/students/${studentId}/`, {
                method: 'DELETE',
                headers: authHeaders()
            });
            if (res.ok) {
                await loadMembers();
            } else {
                const data = await res.json().catch(() => ({}));
                alert(data.detail || 'Xóa thất bại.');
            }
        } catch (e) {
            alert('Lỗi kết nối.');
        }
    }

    window.submitCreateQuiz = async function() {
        const title = document.getElementById('quizTitle').value.trim();
        const description = document.getElementById('quizDesc').value.trim();
        const duration = document.getElementById('quizDuration').value;
        const dueDate = document.getElementById('quizDueDate').value;
        if (!title) return;
        const res = await fetch('/api/exams/', {method:'POST',headers:authHeaders(),body:JSON.stringify({title,description,classroom:classId,duration_minutes:duration,due_date:dueDate||null})});
        const data = await res.json();
        if (res.ok) window.location.href = `/exams/builder/${data.id}/`;
        else document.getElementById('createQuizError').textContent = "Lỗi khi tạo đề thi.";
    }

    window.openCopyQuizModal = async function(quizId, title) {
        window.copySourceQuizId = quizId;
        const titleEl = document.getElementById('copyQuizSourceTitle');
        if (titleEl) titleEl.textContent = title || '';
        const errEl = document.getElementById('copyQuizError');
        if (errEl) errEl.textContent = '';
        const list = document.getElementById('copyClassList');
        list.innerHTML = '<div class="text-muted small p-2">Đang tải danh sách lớp...</div>';

        const modal = new bootstrap.Modal(document.getElementById('copyQuizModal'));
        modal.show();

        try {
            const res = await fetch('/api/classes/', { headers: authHeaders() });
            const data = await res.json();
            const classes = Array.isArray(data) ? data : (data.results || []);
            const selectable = classes.filter(c => String(c.id) !== String(classId));
            if (!selectable.length) {
                list.innerHTML = '<div class="text-muted small p-2">Bạn chưa có lớp học khác để sao chép.</div>';
                return;
            }
            list.innerHTML = selectable.map(c => `
                <label class="list-group-item d-flex align-items-center gap-2 py-2">
                    <input class="form-check-input copy-class-cb" type="checkbox" value="${c.id}">
                    <span class="fw-semibold">${escapeHtml(c.name)}</span>
                    <span class="text-muted small ms-auto">${escapeHtml(c.subject_name || '')}</span>
                </label>
            `).join('');
        } catch (e) {
            list.innerHTML = '<div class="text-danger small p-2">Không tải được danh sách lớp.</div>';
        }
    }

    window.submitCopyQuiz = async function() {
        const quizId = window.copySourceQuizId;
        if (!quizId) return;
        const ids = Array.from(document.querySelectorAll('.copy-class-cb:checked')).map(cb => cb.value);
        const errEl = document.getElementById('copyQuizError');
        if (!ids.length) {
            if (errEl) errEl.textContent = 'Chọn ít nhất một lớp.';
            return;
        }

        const btn = document.getElementById('btnCopyQuiz');
        if (btn) btn.disabled = true;
        if (errEl) errEl.textContent = '';

        try {
            const res = await fetch(`/api/exams/${quizId}/copy/`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ classroom_ids: ids })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const message = data.detail
                    || (Array.isArray(data.classroom_ids) && data.classroom_ids[0])
                    || 'Sao chép thất bại.';
                if (errEl) errEl.textContent = message;
                return;
            }

            bootstrap.Modal.getInstance(document.getElementById('copyQuizModal'))?.hide();
            const skipped = data.skipped?.length || 0;
            let msg = `Đã sao chép sang ${data.created.length} lớp`;
            if (skipped) msg += `, bỏ qua ${skipped} lớp không hợp lệ`;
            showGlobalAlert(msg + '.', 'success');
            await loadQuizzes();
        } catch (e) {
            if (errEl) errEl.textContent = 'Lỗi kết nối.';
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    window.initAIChat = function() { aiChatInitialized = true; }
    window.checkEnterQA = function(e) { if (e.key === 'Enter') sendAiQA(); }

    window.sendAiQA = async function() {
        const inputEl = document.getElementById('aiInput');
        const sendBtn = document.getElementById('aiSendBtn');
        const question = inputEl.value.trim();
        if (!question) return;
        const win = document.getElementById('aiChatWindow');

        // User bubble
        const userBubble = document.createElement('div');
        userBubble.style.cssText = 'display:flex;justify-content:flex-end;';
        userBubble.innerHTML = `<div style="background:var(--color-primary);color:#fff;border-radius:var(--radius-md) 0 var(--radius-md) var(--radius-md);padding:0.75rem 1rem;max-width:80%;font-size:0.875rem;">${escapeHtml(question)}</div>`;
        win.appendChild(userBubble);
        inputEl.value = ''; win.scrollTop = win.scrollHeight;

        // Loading bubble
        const loadBubble = document.createElement('div');
        loadBubble.id = 'ai_' + Date.now();
        loadBubble.style.cssText = 'background:var(--color-surface);border:1px solid var(--color-border);border-radius:0 var(--radius-md) var(--radius-md) var(--radius-md);padding:0.75rem 1rem;max-width:80%;font-size:0.875rem;color:var(--color-muted);';
        loadBubble.innerHTML = '<span class="spinner-grow spinner-grow-sm me-2"></span>Đang tìm kiếm...';
        win.appendChild(loadBubble);
        win.scrollTop = win.scrollHeight; sendBtn.disabled = true;

        try {
            const res = await fetch('/api/ai/chat/', {method:'POST',headers:authHeaders(),body:JSON.stringify({class_id:classId,question})});
            const data = await res.json();
            loadBubble.remove();

            if (res.status === 429) {
                const errBubble = document.createElement('div');
                errBubble.style.cssText = 'background:var(--color-warning-light);border:1px solid var(--color-warning);border-radius:0 var(--radius-md) var(--radius-md) var(--radius-md);padding:0.75rem 1rem;max-width:80%;font-size:0.875rem;color:var(--color-warning-dark);';
                errBubble.innerHTML = `<i class="bi bi-clock-history me-2"></i>${escapeHtml(data.error || 'Hệ thống đang bận, vui lòng thử lại sau.')}`;
                win.appendChild(errBubble);
                win.scrollTop = win.scrollHeight;
                // Optional: Local countdown for send button
                let remaining = data.wait_seconds || 60;
                sendBtn.disabled = true;
                const originalHtml = sendBtn.innerHTML;
                const timer = setInterval(() => {
                    remaining--;
                    if (remaining <= 0) {
                        clearInterval(timer);
                        sendBtn.disabled = false;
                        sendBtn.innerHTML = originalHtml;
                    } else {
                        sendBtn.innerHTML = `<span style="font-size:0.75rem;">${remaining}s</span>`;
                    }
                }, 1000);
                return;
            }

            if (!res.ok) throw new Error(data.error || 'Lỗi khi gọi AI.');

            // Parse markdown + newlines
            let html = escapeHtml(data.answer)
                    .replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g,'<em>$1</em>')
                    .replace(/`([^`]+)`/g,'<code style="background:var(--color-bg);padding:0.1em 0.4em;border-radius:4px;font-size:0.85em;">$1</code>')
                    .replace(/\n/g,'<br>');

            const aiBubble = document.createElement('div');
            aiBubble.style.cssText = 'background:var(--color-surface);border:1px solid var(--color-border);border-radius:0 var(--radius-md) var(--radius-md) var(--radius-md);padding:0.75rem 1rem;max-width:85%;font-size:0.875rem;line-height:1.75;';
            aiBubble.innerHTML = html;
            win.appendChild(aiBubble);

            // Render LaTeX if MathJax is loaded
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([aiBubble]).catch(err => console.warn('MathJax error:', err));
            }
        } catch(e) {
            loadBubble.remove();
            const errBubble = document.createElement('div');
            errBubble.style.cssText = 'background:var(--color-danger-light);border:1px solid var(--color-danger);border-radius:0 var(--radius-md) var(--radius-md) var(--radius-md);padding:0.75rem 1rem;max-width:80%;font-size:0.875rem;color:var(--color-danger);';
            errBubble.textContent = 'Lỗi kết nối.';
            win.appendChild(errBubble);
        }
        win.scrollTop = win.scrollHeight; sendBtn.disabled = false; inputEl.focus();
    }

    async function loadRAGDocuments() {
        try {
            const res = await fetch(`/api/ai/classes/${classId}/documents/`, {headers: authHeaders()});
            const docs = await res.json();
            const listEl = document.getElementById('ragDocsList');
            if (!docs.length) { listEl.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-muted);font-size:0.8rem;">Chưa có tài liệu nào.</div>'; return; }
            listEl.innerHTML = docs.map(d => {
                const safeTitle = escapeHtml(d.title);
                const deleteBtn = (currentRole === 'teacher' || currentRole === 'admin') ? `<button style="border:none;background:none;color:var(--color-danger);cursor:pointer;padding:0.25rem;" onclick="deleteRAGDocument(${d.id})" title="Xoá"><i class="bi bi-trash"></i></button>` : '';
                return `<div style="display:flex;justify-content:space-between;align-items:center;padding:0.875rem 1rem;border-bottom:1px solid var(--color-border);">
                    <div style="display:flex;gap:0.75rem;align-items:center;">
                        <i class="bi bi-file-earmark-pdf" style="color:var(--color-danger);font-size:1.2rem;"></i>
                        <div><div style="font-size:0.82rem;font-weight:600;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${safeTitle}">${safeTitle}</div><div style="font-size:0.7rem;color:var(--color-muted);">${new Date(d.uploaded_at).toLocaleDateString('vi-VN')}</div></div>
                    </div>${deleteBtn}</div>`;
            }).join('');
        } catch(e) {}
    }

    window.uploadRAGDocument = async function(e) {
        const file = e.target.files[0]; if (!file) return;

        const indicator = document.getElementById('uploadingDocIndicator');
        if (indicator) indicator.style.display = 'block';
        
        try {
            // Bước 1: Upload trực tiếp lên Cloudinary từ thiết bị (bypass lỗi 4.5MB Vercel)
            const signature = await window.getCloudinarySignature();
            const cFormData = new FormData();
            cFormData.append('file', file);
            cFormData.append('api_key', signature.api_key);
            cFormData.append('timestamp', signature.timestamp);
            cFormData.append('signature', signature.signature);
            
            // Dùng /raw/upload để hỗ trợ cả pdf, docx, txt (không phải ảnh)
            const cloudRes = await fetch(`https://api.cloudinary.com/v1_1/${signature.cloud_name}/raw/upload`, {
                method: 'POST',
                body: cFormData
            });
            
            if (!cloudRes.ok) {
                throw new Error("Không thể kết nối máy chủ Cloudinary.");
            }
            const cloudData = await cloudRes.json();
            
            // Bước 2: Báo cho Django biết URL file và public_id
            const payload = {
                file_url: cloudData.secure_url,
                file_name: file.name,
                cloudinary_public_id: cloudData.public_id
            };
            
            const res = await fetch(`/api/ai/classes/${classId}/documents/upload/`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify(payload)
            });
            
            if (res.ok) { 
                const data = await res.json();
                const qCount = data.questions_extracted || 0;
                let msg = 'Tải lên tài liệu thành công!';
                if (qCount > 0) msg += ` AI đã nhận diện được ${qCount} câu hỏi.`;
                showGlobalAlert(msg, 'success'); 
                await loadRAGDocuments(); 
            } else { 
                const err = await res.json().catch(() => ({})); 
                alert("Lỗi: " + (err.error || "Không thể nạp tài liệu."));
            }
        } catch(err) { 
            alert("Lỗi kết nối: " + err.message);
        }
        finally { 
            if (indicator) indicator.style.display = 'none'; 
            e.target.value = ''; 
        }
    }

    window.deleteRAGDocument = async function(docId) {
        if (!confirm("Xoá tài liệu này khỏi hệ thống AI?")) return;
        const res = await fetch(`/api/ai/documents/${docId}/`, {method:'DELETE',headers:authHeaders()});
        if (res.ok) { showGlobalAlert('Đã xoá tài liệu.', 'success'); await loadRAGDocuments(); }
        else alert('Lỗi khi xoá.');
    }

    window.deleteClass = async function(id, name) {
        if (!confirm(`Bạn có chắc chắn muốn xoá lớp "${name}"? Thao tác này sẽ xoá toàn bộ bài thi, kết quả và tài liệu liên quan và không thể hoàn tác.`)) return;
        
        const res = await fetch(`/api/classes/${id}/`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        
        if (res.ok) {
            // Using a delay to ensure the alert is visible before redirecting
            alert(`Đã xoá lớp "${name}" thành công.`);
            window.location.href = '/classes/';
        } else {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || 'Xoá lớp thất bại.');
        }
    }

    function escapeHtml(s) { return (s ?? '').toString().replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;"); }

    document.addEventListener('DOMContentLoaded', () => {
        // Load Insight when tab is clicked
        const insightTabTrigger = document.getElementById('teacher-insight-tab-btn');
        if (insightTabTrigger) {
            insightTabTrigger.addEventListener('shown.bs.tab', function (event) {
                const textEl = document.getElementById('aiInsightText');
                if (textEl && textEl.innerHTML.trim() === '') {
                    loadSavedInsight();
                }
            });
        }

        // Initialize DateTime picker for Due Date with dd/mm/yyyy H:i format
        if (typeof flatpickr !== 'undefined') {
            flatpickr("#quizDueDate", {
                enableTime: true,
                dateFormat: "Y-m-d\\TH:i",
                altInput: true,
                altFormat: "d/m/Y H:i",
                time_24hr: true,
                locale: "vn"
            });
        }
    });

    init();
});
