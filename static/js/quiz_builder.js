let quizData = null;
let selectedQuestions = [];
let questionBank = [];
let qbEasyMDE = null;
let currentDrafts = { file: [], rag: [] };
function normalizeListResponse(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
}

function authHeaders(isMultipart = false) {
    const headers = {};
    if (!isMultipart) {
        headers['Content-Type'] = 'application/json';
    }
    return headers;
}

// ─── Helpers: Question type display ─────────────────────────────────────────

const Q_TYPE_CONFIG = {
    multiple_choice: { label: 'Trắc nghiệm', badge: 'bg-primary', icon: 'bi-ui-radios-grid' },
    true_false: { label: 'Đúng/Sai', badge: 'bg-info text-dark', icon: 'bi-toggle-on' },
    short_answer: { label: 'Trả lời ngắn', badge: 'bg-warning text-dark', icon: 'bi-pencil-square' },
};

const DIFF_CONFIG = {
    easy: { label: 'Nhận biết', badge: 'bg-success' },
    medium: { label: 'Thông hiểu', badge: 'bg-warning text-dark' },
    hard: { label: 'Vận dụng', badge: 'bg-danger' },
};

function typeBadge(type) {
    const c = Q_TYPE_CONFIG[type] || Q_TYPE_CONFIG.multiple_choice;
    return `<span class="badge ${c.badge} rounded-pill px-2" style="font-size:0.65rem"><i class="bi ${c.icon} me-1"></i>${c.label}</span>`;
}

function diffBadge(diff) {
    const c = DIFF_CONFIG[diff] || DIFF_CONFIG.medium;
    return `<span class="badge ${c.badge} rounded-pill px-2" style="font-size:0.65rem">${c.label}</span>`;
}

function escapeHtml(unsafe) {
    return (unsafe || '').toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getQuestionDisplayText(q) {
    if (q?.text && String(q.text).trim()) return q.text;
    return QuestionRenderer.extractTextFromBlocks(q?.content_json || []);
}

function getOptionDisplayText(o) {
    if (o?.text && String(o.text).trim()) return o.text;
    return QuestionRenderer.extractTextFromBlocks(o?.content_json || []);
}
async function loadRagDocuments(classId) {
    const wrap = document.getElementById('ragDocumentWrap');
    const sel = document.getElementById('ragDocument');
    const status = document.getElementById('ragDocumentStatus');
    if (!wrap || !sel || !classId) return;

    // Reset
    sel.innerHTML = '<option value="">Toàn bộ tài liệu trong lớp</option>';
    status.textContent = 'Đang tải danh sách tài liệu...';
    wrap.style.display = 'block';

    try {
        const res = await fetch(`/api/ai/classes/${classId}/documents/`, { headers: authHeaders() });
        if (!res.ok) { status.textContent = 'Không thể tải tài liệu.'; return; }
        const docs = await res.json();
        if (Array.isArray(docs) && docs.length > 0) {
            docs.forEach(d => sel.add(new Option(d.title || 'Tài liệu', d.id)));
            status.textContent = `Đã tải ${docs.length} tài liệu.`;
        } else {
            status.textContent = 'Lớp học này chưa có tài liệu nào.';
        }
    } catch (e) {
        status.textContent = 'Lỗi kết nối.';
    }
}

function renderQuestionStem(q, extraClass = '') {
    return QuestionRenderer.renderStem(q, { containerClass: extraClass });
}

function getQuestionDisplayText(q) {
    if (q?.text && String(q.text).trim()) return q.text;
    return QuestionRenderer.extractTextFromBlocks(q?.content_json || []);
}

function getOptionDisplayText(o) {
    if (o?.text && String(o.text).trim()) return o.text;
    return QuestionRenderer.extractTextFromBlocks(o?.content_json || []);
}

function hasConfiguredAnswer(q) {
    const type = q?.question_type || 'multiple_choice';
    if (type === 'short_answer') return !!(q?.correct_answer_text && String(q.correct_answer_text).trim());
    const options = Array.isArray(q?.options) ? q.options : [];
    if (type === 'true_false') return options.length >= 2;
    return options.length > 0 && options.some((o) => !!o.is_correct);
}

// ─── Render functions for question content ─────────────────────────────────

function renderQuestionContent(q) {
    const type = q.question_type || 'multiple_choice';
    let html = '';

    if (type === 'multiple_choice') {
        html = (q.options || []).map((o, i) => {
            const l = String.fromCharCode(65 + i);
            const cls = o.is_correct ? 'fw-bold text-success' : '';
            const contentHtml = QuestionRenderer.renderOption(o, q.question_images);
            return `<div class="${cls}">${l}. ${contentHtml}</div>`;
        }).join('');

    } else if (type === 'true_false') {
        if (q.context) {
            const safeContext = escapeHtml(q.context);
            let renderedContext = marked.parseInline(safeContext);
            if (window.sanitizeMarkdownHtml) renderedContext = window.sanitizeMarkdownHtml(renderedContext);
            html += `<div class="bg-light border rounded p-2 mb-2 small fst-italic q-markdown-text markdown-inline">${renderedContext}</div>`;
        }
        html += (q.options || []).map((o, i) => {
            const l = String.fromCharCode(97 + i); // a, b, c, d
            const icon = o.is_correct
                ? '<i class="bi bi-check-circle-fill text-success me-1"></i><span class="text-success fw-bold">Đúng</span>'
                : '<i class="bi bi-x-circle-fill text-danger me-1"></i><span class="text-danger fw-bold">Sai</span>';
            const contentHtml = QuestionRenderer.renderOption(o, q.question_images);
            return `<div class="mb-1">${l}) ${contentHtml} → ${icon}</div>`;
        }).join('');

    } else if (type === 'short_answer') {
        const ans = q.correct_answer_text || '(chưa có)';
        html = `<div><i class="bi bi-pencil me-1 text-muted"></i>Đáp án: <strong class="text-primary">${escapeHtml(ans)}</strong></div>`;
    }

    return html;
}

// ─── Init ────────────────────────────────────────────────────────────────────

async function init() {
    const me = await window.getCurrentUser(true);
    if (!me) { window.location.href = '/login/'; return; }

    try {
        if (me.role?.name !== 'teacher' && me.role?.name !== 'admin') {
            alert('Bạn không có quyền truy cập trang này.');
            window.location.href = '/dashboard/';
            return;
        }

        await loadQuizData();
        await loadSelectedQuestions();

        // ─── Initialize Shared Logic & Filters ───
        const subjectsRes = await fetch('/api/classes/subjects/', { headers: authHeaders() });
        const subjectsData = await subjectsRes.json();
        
        // Populate Sidebar Subject Filter (using user's new ID 'filterSubject')
        const subFilter = document.getElementById('filterSubject');
        if (subFilter && Array.isArray(subjectsData)) {
            subFilter.innerHTML = '<option value="">Tất cả môn học</option>';
            subjectsData.forEach(s => {
                const opt = new Option(s.name, s.id);
                if (s.id == quizData?.subject_id) opt.selected = true;
                subFilter.add(opt);
            });
        }

        // Initialize AI Generator shared logic
        AIGenerator.init({
            context: 'quiz',
            quizId: quizId,
            subjectId: quizData?.subject_id,
            onSaveSuccess: async () => {
                await loadQuizData();
                await loadSelectedQuestions();
                await loadQuestionBank();
            }
        });

        QuestionEditor.init({
            context: 'quiz',
            subjects: subjectsData,
            subjectId: quizData?.subject_id,
            currentQuizId: quizId,
            onSave: async () => {
                await loadQuizData();
                await loadSelectedQuestions();
                await loadQuestionBank();
            }
        });

        // Now load the bank (it will use the correct filter value)
        await loadQuestionBank();

        // Hide subject selection in AI Modal for Quiz Builder
        const aiExtractSubWrap = document.getElementById('aiExtractSubjectWrap');
        if (aiExtractSubWrap) aiExtractSubWrap.style.display = 'none';

        // FIX Bug: Remove 'required' from hidden select and populate with quizData.subject_id
        const aiExtractSub = document.getElementById('aiExtractSubject');
        if (aiExtractSub) {
            aiExtractSub.removeAttribute('required');
            if (quizData?.subject_id) {
                aiExtractSub.innerHTML = `<option value="${quizData.subject_id}" selected>${escapeHtml(quizData.subject_name || '')}</option>`;
            }
        }

        // RAG: Tải danh mục tài liệu của lớp học này
        if (quizData && quizData.classroom) {
            const ragClassSelect = document.getElementById('ragClass');
            if (ragClassSelect) {
                // Trong Quiz Builder, mặc định chọn sẵn lớp của Quiz và ẩn selector lớp (hoặc disabled)
                ragClassSelect.innerHTML = `<option value="${quizData.classroom}" selected>${escapeHtml(quizData.classroom_name)}</option>`;
                ragClassSelect.disabled = true;
                await loadRagDocuments(quizData.classroom);
            }
        }

        document.getElementById('loadingQuiz').style.display = 'none';
        document.getElementById('quizContent').style.display = 'block';
    } catch (e) {
        console.error(e);
        showInitError(e?.message || 'Lỗi khởi tạo màn hình. Vui lòng đăng nhập lại.');
    }
}

function showInitError(msg) {
    const loading = document.getElementById('loadingQuiz');
    if (loading) {
        loading.innerHTML = `<div class="alert alert-danger mx-auto" style="max-width:500px">
            <i class="bi bi-exclamation-triangle-fill me-2"></i> ${escapeHtml(msg)}
            <div class="mt-3"><button class="btn btn-sm btn-outline-danger" onclick="location.reload()">Thử lại</button></div>
        </div>`;
    }
}

async function loadQuizData() {
    const res = await fetch(`/api/exams/${quizId}/`, { headers: authHeaders() });
    if (res.status === 401) {
        window.location.href = '/login/';
        return;
    }
    if (!res.ok) {
        throw new Error('Không tìm thấy đề thi hoặc bạn không có quyền truy cập.');
    }
    quizData = await res.json();

    const setElText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };

    setElText('quizTitle', quizData.title);
    setElText('breadcrumbQuizTitle', quizData.title);
    setElText('breadcrumbClassLink', quizData.classroom_name);
    
    const classLink = document.getElementById('breadcrumbClassLink');
    if (classLink && quizData.classroom) {
        classLink.href = `/classes/${quizData.classroom}/`;
    }

    setElText('quizDesc', quizData.description || 'Không có mô tả.');
    setElText('quizDuration', quizData.duration_minutes);
    setElText('quizQuestionCount', quizData.question_count);

    const schedInfo = [];
    if (quizData.publish_at) {
        try {
            schedInfo.push(`Hẹn ngày: ${new Date(quizData.publish_at).toLocaleString('vi-VN')}`);
        } catch(e) {}
    }
    if (quizData.due_date) {
        try {
            schedInfo.push(`Hạn nộp: ${new Date(quizData.due_date).toLocaleString('vi-VN')}`);
        } catch(e) {}
    }
    setElText('quizScheduleInfo', schedInfo.join(' | '));

    const statusEl = document.getElementById('quizStatus');
    if (statusEl) {
        if (quizData.is_published) {
            statusEl.textContent = 'Công khai';
            statusEl.className = 'badge bg-success';
            const pBtn = document.getElementById('publishBtn');
            const uBtn = document.getElementById('unpublishBtn');
            if (pBtn) pBtn.style.display = 'none';
            if (uBtn) uBtn.style.display = 'inline-block';
        } else {
            statusEl.textContent = 'Nháp';
            statusEl.className = 'badge bg-secondary';
            const pBtn = document.getElementById('publishBtn');
            const uBtn = document.getElementById('unpublishBtn');
            if (pBtn) pBtn.style.display = 'inline-block';
            if (uBtn) uBtn.style.display = 'none';
        }
    }
}

async function loadSelectedQuestions() {
    const res = await fetch(`/api/exams/${quizId}/questions/`, { headers: authHeaders() });
    if (res.status === 401) {
        window.location.href = '/login/';
        return;
    }
    if (!res.ok) {
        throw new Error('Không tải được danh sách câu hỏi của đề thi.');
    }
    const data = await res.json();
    selectedQuestions = normalizeListResponse(data);
    renderSelectedQuestions();
}

async function updateQuestionPoints(qqId, rawValue) {
    const value = parseFloat(rawValue);
    if (Number.isNaN(value) || value < 0 || value > 10) {
        showGlobalAlert('Điểm mỗi câu phải nằm trong khoảng 0 đến 10.', 'warning');
        await loadSelectedQuestions();
        return;
    }

    const res = await fetch(`/api/exams/${quizId}/questions/${qqId}/`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ points: value })
    });

    if (res.status === 401) { window.location.href = '/login/'; return; }
    if (!res.ok) {
        showGlobalAlert('Không thể cập nhật điểm câu hỏi.', 'danger');
        await loadSelectedQuestions();
        return;
    }
    await loadSelectedQuestions();
}

async function resetQuestionPoints(qqId) {
    const res = await fetch(`/api/exams/${quizId}/questions/${qqId}/reset-points/`, {
        method: 'POST',
        headers: authHeaders()
    });

    if (res.status === 401) { window.location.href = '/login/'; return; }
    if (!res.ok) {
        showGlobalAlert('Không thể khôi phục điểm mặc định.', 'danger');
        return;
    }
    await loadSelectedQuestions();
}

function updatePointsSummary() {
    const total = selectedQuestions.reduce((sum, qq) => sum + (parseFloat(qq.points) || 0), 0);
    const totalEl = document.getElementById('totalPoints');
    if (totalEl) totalEl.textContent = total.toFixed(2);

    const warning = document.getElementById('pointsWarning');
    if (warning) {
        warning.style.display = Math.abs(total - 10) > 0.01 ? 'inline-block' : 'none';
    }
}

function renderSelectedQuestions() {
    const list = document.getElementById('selectedQuestionsList');
    const msg = document.getElementById('noQuestionsMsg');
    list.innerHTML = '';
    
    if (selectedQuestions.length === 0) {
        msg.style.display = 'block';
        document.getElementById('quizQuestionCount').textContent = 0;
        updatePointsSummary();
        return;
    }
    
    msg.style.display = 'none';
    document.getElementById('quizQuestionCount').textContent = selectedQuestions.length;
    
    selectedQuestions.sort((a,b) => a.order - b.order).forEach((qq, idx) => {
        const q = qq.question;
        const isFixedPoints = q.question_type === 'true_false';
        const pointsControl = isFixedPoints
            ? `<span class="badge bg-light text-primary border ms-1" style="font-size:0.75rem">
                    <i class="bi bi-star-fill me-1 text-warning"></i>1.00 điểm (cố định)
               </span>`
            : `<span class="badge bg-light text-primary border ms-1 d-inline-flex align-items-center gap-1" style="font-size:0.75rem">
                    <i class="bi bi-star-fill text-warning"></i>
                    <input type="number" min="0" max="10" step="0.05" value="${(parseFloat(qq.points) || 0).toFixed(2)}"
                        onchange="updateQuestionPoints(${qq.id}, this.value)"
                        style="width:58px;border:0;background:transparent;font-size:0.75rem;font-weight:700;text-align:right;">
                    điểm
               </span>
               ${qq.is_points_overridden ? `<button class="btn btn-sm btn-link text-muted p-0 ms-1" style="font-size:0.7rem" onclick="resetQuestionPoints(${qq.id})" title="Quay về điểm mặc định">Mặc định</button>` : ''}`;

        const item = document.createElement('li');
        item.className = `qb-question-item animate-in`;
        item.style.animationDelay = `${idx * 0.05}s`;
        item.innerHTML = `
            <div class="qb-q-header">
                <div class="d-flex align-items-center gap-2 flex-wrap">
                    <span class="qb-q-number">Câu ${idx + 1}</span>
                    ${typeBadge(q.question_type)}
                    ${q.question_type === 'true_false' ? '' : diffBadge(q.difficulty)}
                    ${q.grade ? `<span class="badge bg-light text-muted border rounded-pill px-2" style="font-size:0.65rem">Khối ${escapeHtml(q.grade)}</span>` : ''}
                    ${pointsControl}
                </div>
                <div class="d-flex align-items-center gap-2">
                    ${q.can_edit ? `<button class="btn btn-sm btn-light text-primary px-2 border" onclick="editQuestion(${q.id})" title="Sửa nội dung">
                        <i class="bi bi-pencil-square"></i>
                    </button>` : ''}
                    <button class="btn btn-sm btn-light text-danger px-2 border" onclick="promptRemoveQQ(${qq.id})" title="Rút câu hỏi này">
                        <i class="bi bi-trash-fill"></i>
                    </button>
                </div>
            </div>
            <div class="mb-3" style="line-height:1.6; color: var(--color-text);">${renderQuestionStem(q)}</div>
            <div class="small bg-light p-3 rounded-3" style="border-left: 3px solid var(--color-border);">${renderQuestionContent(q)}</div>
        `;
        list.appendChild(item);
    });
    updatePointsSummary();
}

let qbCurrentPage = 1;

async function loadQuestionBank(page = 1) {
    qbCurrentPage = page;
    const term = document.getElementById('bankSearch').value.toLowerCase();
    
    // We'll use the same API with page param
    let url = `/api/exams/questions/?page=${page}`;
    if (term) url += `&search=${encodeURIComponent(term)}`;
    
    // Subject filter from sidebar or default to quiz subject
    const sub = document.getElementById('filterSubject')?.value;
    const diff = document.getElementById('filterDiff')?.value;
    const grade = document.getElementById('filterGrade')?.value;
    const type = document.getElementById('filterType')?.value;
    const status = document.getElementById('filterStatus')?.value;

    if (sub) {
        url += `&subject=${sub}`;
    } else if (sub === undefined && quizData && quizData.subject_id) {
        // Only fallback if element doesn't exist yet
        url += `&subject=${quizData.subject_id}`;
    }

    if (diff) url += `&difficulty=${diff}`;
    if (grade) url += `&grade=${grade}`;
    if (type) url += `&question_type=${type}`;
    if (status) url += `&status=${status}`;

    try {
        const res = await fetch(url, { headers: authHeaders() });
        if (res.status === 401) {
            window.location.href = '/login/';
            return;
        }
        if (!res.ok) {
            throw new Error('Không tải được ngân hàng câu hỏi.');
        }
        const data = await res.json();
        questionBank = normalizeListResponse(data);
        renderQuestionBank(questionBank);
        renderQbPagination(data);
    } catch (err) {
        console.error('Lỗi loadQuestionBank:', err);
        const list = document.getElementById('questionBankList');
        if (list) list.innerHTML = `<div class="p-4 text-center text-danger small">Lỗi: ${escapeHtml(err.message)}</div>`;
    }
}

function renderQbPagination(data) {
    const container = document.getElementById('qbPaginationContainer');
    if (!container) return;
    
    const pageSize = 20;
    const totalPages = Math.ceil(data.count / pageSize);

    if (!data.count || totalPages <= 1) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'block';
    
    let html = `
        <div class="d-flex justify-content-between align-items-center py-2 px-3 bg-light border-top">
            <button class="btn btn-xs btn-outline-primary ${!data.previous ? 'disabled' : ''}" 
                    onclick="loadQuestionBank(${qbCurrentPage - 1})" style="padding: 2px 6px;">
                <i class="bi bi-chevron-left"></i>
            </button>
            <div class="small fw-bold text-primary">
                Trang ${qbCurrentPage} / ${totalPages}
            </div>
            <button class="btn btn-xs btn-outline-primary ${!data.next ? 'disabled' : ''}" 
                    onclick="loadQuestionBank(${qbCurrentPage + 1})" style="padding: 2px 6px;">
                <i class="bi bi-chevron-right"></i>
            </button>
        </div>
        <div class="text-center pb-2 bg-light">
            <span class="text-muted" style="font-size: 0.65rem;">Tổng ${data.count} câu hỏi</span>
        </div>
    `;
    container.innerHTML = html;
}

let bankSearchTimer;
function filterBank(immediate = false) {
    clearTimeout(bankSearchTimer);
    if (immediate) {
        loadQuestionBank(1);
    } else {
        bankSearchTimer = setTimeout(() => {
            loadQuestionBank(1);
        }, 500);
    }
}

function renderQuestionBank(questions) {
    const list = document.getElementById('questionBankList');
    if (!list) return;
    list.innerHTML = '';
    let addedQIDs = new Set(selectedQuestions.map(qq => qq.question.id));
    
    questions.forEach(q => {
        const item = document.createElement('li');
        item.className = 'qb-bank-item';
        const isAdded = addedQIDs.has(q.id);
        
        const actionBtn = isAdded 
            ? `<span class="badge bg-light text-muted border px-2 py-1"><i class="bi bi-check2 me-1"></i>Đã thêm</span>`
            : `<button class="btn btn-sm btn-outline-primary px-3 py-1 rounded-pill" onclick="addQuestionToQuiz(${q.id})" style="font-size:0.75rem; font-weight:700;">Thêm</button>`;
        
        item.innerHTML = `
            <div class="qb-bank-q-text">${escapeHtml(getQuestionDisplayText(q))}</div>
            <div class="d-flex justify-content-between align-items-center">
                <div class="d-flex gap-1">
                    ${typeBadge(q.question_type)}
                    ${q.grade ? `<span class="badge bg-light text-muted border" style="font-size:0.62rem">Khối ${escapeHtml(q.grade)}</span>` : ''}
                    <span class="text-muted" style="font-size:0.7rem; font-weight:500;">${escapeHtml(q.subject_name)}</span>
                </div>
                <div class="d-flex gap-1 align-items-center">
                    ${q.can_edit ? `<button class="btn btn-sm btn-link text-muted p-1" onclick="editQuestion(${q.id})" title="Sửa"><i class="bi bi-pencil-square"></i></button>` : ''}
                    ${actionBtn}
                </div>
            </div>
        `;
        list.appendChild(item);
    });
}

async function addQuestionToQuiz(qId) {
    let maxOrder = 0;
    if (selectedQuestions.length > 0) {
        maxOrder = Math.max(...selectedQuestions.map(qq => qq.order));
    }
    const res = await fetch(`/api/exams/${quizId}/questions/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ question_id: qId, order: maxOrder + 1 })
    });

    if (res.status === 401) { window.location.href = '/login/'; return; }

    if (res.ok) {
        showGlobalAlert('Thêm câu hỏi vào đề thành công.', 'success');
        await loadSelectedQuestions();
        renderQuestionBank(questionBank);
    } else {
        showGlobalAlert('Lỗi không thể thêm câu hỏi.', 'danger');
    }
}

let deleteQQId = null;
function promptRemoveQQ(qqId) {
    deleteQQId = qqId;
    new bootstrap.Modal(document.getElementById('deleteConfirmModal')).show();
}

document.getElementById('confirmDeleteBtn')?.addEventListener('click', async () => {
    if (!deleteQQId) return;
    const res = await fetch(`/api/exams/${quizId}/questions/${deleteQQId}/`, {
        method: 'DELETE',
        headers: authHeaders()
    });
    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal')).hide();
        showGlobalAlert('Đã rút câu hỏi khỏi đề.', 'success');
        await loadSelectedQuestions();
        renderQuestionBank(questionBank);
    }
});

async function togglePublish() {
    const isPub = quizData.is_published;
    const res = await fetch(`/api/exams/${quizId}/`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ is_published: !isPub })
    });

    if (res.ok) {
        showGlobalAlert(`Đã ${!isPub ? 'công khai' : 'ẩn'} đề thi.`, 'success');
        await loadQuizData();
    }
}

function editQuizSettings() {
    document.getElementById('editQuizTitle').value = quizData.title;
    document.getElementById('editQuizDesc').value = quizData.description || '';
    document.getElementById('editQuizDuration').value = quizData.duration_minutes;
    document.getElementById('editQuizPublishAt').value = quizData.publish_at ? quizData.publish_at.slice(0, 16) : '';
    document.getElementById('editQuizDueDate').value = quizData.due_date ? quizData.due_date.slice(0, 16) : '';
    new bootstrap.Modal(document.getElementById('editQuizModal')).show();
}

async function submitEditQuiz() {
    const payload = {
        title: document.getElementById('editQuizTitle').value,
        description: document.getElementById('editQuizDesc').value,
        duration_minutes: document.getElementById('editQuizDuration').value,
        publish_at: document.getElementById('editQuizPublishAt').value || null,
        due_date: document.getElementById('editQuizDueDate').value || null
    };

    const res = await fetch(`/api/exams/${quizId}/`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('editQuizModal')).hide();
        showGlobalAlert('Cập nhật Đề thi thành công.', 'success');
        await loadQuizData();
    }
}



function openQuestionEditor() {
    QuestionEditor.open();
}

async function editQuestion(qId) {
    try {
        const res = await fetch(`/api/exams/questions/${qId}/`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Lỗi tải thông tin câu hỏi.");
        const q = await res.json();
        QuestionEditor.open({ data: q });
    } catch (e) {
        if (window.showGlobalAlert) {
            window.showGlobalAlert(e.message, 'danger');
        } else {
            alert(e.message);
        }
    }
}



// ─── Delete Quiz ────────────────────────────────────────────────────────────

function promptDeleteQuiz() {
    new bootstrap.Modal(document.getElementById('deleteQuizConfirmModal')).show();
}

document.getElementById('confirmDeleteQuizBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('confirmDeleteQuizBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang xoá...';
    try {
        const res = await fetch(`/api/exams/${quizId}/`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        if (res.ok) {
            bootstrap.Modal.getInstance(document.getElementById('deleteQuizConfirmModal')).hide();
            showGlobalAlert('Đã xoá đề thi thành công.', 'success');
            setTimeout(() => {
                window.location.href = `/classes/${quizData.classroom}/`;
            }, 1000);
        } else {
            showGlobalAlert('Lỗi không thể xoá đề thi.', 'danger');
            btn.disabled = false;
            btn.innerHTML = 'Đồng ý Xoá';
        }
    } catch (e) {
        showGlobalAlert('Lỗi kết nối.', 'danger');
        btn.disabled = false;
        btn.innerHTML = 'Đồng ý Xoá';
    }
});





init();
