let questions = [];
let subjects = [];
let currentDrafts = { file: [], rag: [] }; // Storage cho AI Generator

function authHeaders() {
    return { 'Content-Type': 'application/json' };
}

function authOnlyHeaders() {
    return {};
}



async function init() {
    try {
        const subRes = await fetch('/api/classes/subjects/', { headers: authHeaders() });
        subjects = await subRes.json();
        
        const filterSub = document.getElementById('filterSubject');
        const aiExtractSub = document.getElementById('aiExtractSubject');
        
        if (filterSub) filterSub.innerHTML = '<option value="">Tất cả môn học</option>';
        if (aiExtractSub) aiExtractSub.innerHTML = '';
        
        subjects.forEach(s => {
            if (filterSub) filterSub.add(new Option(s.name, s.id));
            if (aiExtractSub) aiExtractSub.add(new Option(s.name, s.id));
        });

        const classRes = await fetch('/api/classes/', { headers: authHeaders() });
        if (classRes.ok) {
            const classData = await classRes.json();
            const ragClassSelect = document.getElementById('ragClass');
            if (ragClassSelect && Array.isArray(classData)) {
                classData.forEach(c => {
                    ragClassSelect.add(new Option(c.name, c.id));
                });
            }
        }

        // Bắt sự kiện thay đổi Lớp học ⇒ tải danh sách Tài liệu
        const ragClassEl = document.getElementById('ragClass');
        if (ragClassEl) {
            ragClassEl.addEventListener('change', async () => {
                await loadRagDocuments(ragClassEl.value);
            });
        }

        // Initialize Shared Question Editor
        QuestionEditor.init({
            context: 'bank',
            subjects: subjects,
            onSave: async () => {
                await loadQuestions();
            }
        });

        loadQuestions();
        initAiGenerator();
    } catch (e) {
        showGlobalAlert('Lỗi khởi tạo màn hình Ngân hàng.', 'danger');
    }
}

let searchTimer;
function debounceSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        loadQuestions();
    }, 500);
}

let currentPage = 1;
let totalQuestions = 0;

function normalizeListResponse(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
}

async function loadQuestions(page = 1) {
    currentPage = page;
    const loading = document.getElementById('loading');
    const questionList = document.getElementById('questionList');
    const paginationContainer = document.getElementById('paginationContainer');
    
    loading.style.display = 'block';
    questionList.style.display = 'none';
    if (paginationContainer) paginationContainer.innerHTML = '';

    // Clear selection
    selectedIds = [];
    updateBulkToolbar();

    try {
        const sub = document.getElementById('filterSubject').value;
        const diff = document.getElementById('filterDiff').value;
        const type = document.getElementById('filterType').value;
        const search = document.getElementById('filterSearch').value;
        const status = document.getElementById('filterStatus') ? document.getElementById('filterStatus').value : '';
        
        let url = `/api/exams/questions/?page=${page}&subject=${sub}&difficulty=${diff}&question_type=${type}&search=${encodeURIComponent(search)}&status=${status}`;
        
        const res = await fetch(url, { headers: authHeaders() });
        const data = await res.json();
        
        questions = normalizeListResponse(data);
        totalQuestions = data.count || questions.length;
        
        // Sorting: Needs review items first (client-side sort is fine for metadata)
        questions.sort((a,b) => {
            const aNeeds = isNeedsReview(a);
            const bNeeds = isNeedsReview(b);
            if(aNeeds && !bNeeds) return -1;
            if(!aNeeds && bNeeds) return 1;
            return 0; // Backend already sorted by created_at
        });

        renderQuestions();
        renderPagination(data);
    } catch(e) {
        console.error(e);
        showGlobalAlert('Lỗi tải danh sách câu hỏi', 'danger');
    } finally {
        loading.style.display = 'none';
        questionList.style.display = 'flex';
    }
}

function renderPagination(data) {
    const container = document.getElementById('paginationContainer');
    if (!container || !data.count) {
        if (container) container.innerHTML = '';
        return;
    }

    const pageSize = 20; // DRF backend default
    const totalPages = Math.ceil(data.count / pageSize);
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `
        <nav aria-label="Page navigation" class="mt-4">
            <ul class="pagination justify-content-center">
                <li class="page-item ${!data.previous ? 'disabled' : ''}">
                    <a class="page-link shadow-sm border-0" href="#" onclick="loadQuestions(${currentPage - 1}); return false;" aria-label="Previous">
                        <i class="bi bi-chevron-left"></i>
                    </a>
                </li>
    `;

    // Advanced pagination algorithm (ellipsis)
    const delta = 2; // Pages to show around current
    const left = currentPage - delta;
    const right = currentPage + delta + 1;
    const range = [];
    const rangeWithDots = [];
    let l;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= left && i < right)) {
            range.push(i);
        }
    }

    for (const i of range) {
        if (l) {
            if (i - l === 2) {
                rangeWithDots.push(l + 1);
            } else if (i - l !== 1) {
                rangeWithDots.push('...');
            }
        }
        rangeWithDots.push(i);
        l = i;
    }

    rangeWithDots.forEach(i => {
        if (i === '...') {
            html += `<li class="page-item disabled"><span class="page-link bg-transparent border-0">...</span></li>`;
        } else {
            html += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link shadow-sm border-0 mx-1 rounded" href="#" onclick="loadQuestions(${i}); return false;">${i}</a>
                </li>
            `;
        }
    });

    html += `
                <li class="page-item ${!data.next ? 'disabled' : ''}">
                    <a class="page-link shadow-sm border-0" href="#" onclick="loadQuestions(${currentPage + 1}); return false;" aria-label="Next">
                        <i class="bi bi-chevron-right"></i>
                    </a>
                </li>
            </ul>
        </nav>
        <div class="text-center text-muted small mt-2">
            Hiển thị ${Math.min(data.count, (currentPage - 1) * pageSize + 1)} - ${Math.min(data.count, currentPage * pageSize)} trên tổng số ${data.count} câu hỏi
        </div>
    `;

    container.innerHTML = html;
}

let selectedIds = [];

function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('.q-checkbox');
    selectedIds = [];
    checkboxes.forEach(cb => {
        cb.checked = checked;
        if (checked) {
            selectedIds.push(parseInt(cb.dataset.id));
        }
    });
    updateBulkToolbar();
}

function toggleSelectQuestion(id, checked) {
    if (checked) {
        if (!selectedIds.includes(id)) selectedIds.push(id);
    } else {
        selectedIds = selectedIds.filter(x => x !== id);
    }
    document.getElementById('selectAllQuestions').checked = (selectedIds.length === questions.length && questions.length > 0);
    updateBulkToolbar();
}

function updateBulkToolbar() {
    const toolbar = document.getElementById('bulkActionsToolbar');
    const countSpan = document.getElementById('selectedCount');
    
    if (selectedIds.length > 0) {
        toolbar.style.setProperty('display', 'flex', 'important');
        countSpan.innerText = `${selectedIds.length} đã chọn`;
    } else {
        toolbar.style.setProperty('display', 'none', 'important');
    }
}


const TYPE_LBL = {
    multiple_choice: '<span class="badge bg-primary-subtle text-primary"><i class="bi bi-ui-radios-grid me-1"></i>Trắc nghiệm</span>',
    true_false: '<span class="badge bg-info-subtle text-info"><i class="bi bi-toggle-on me-1"></i>Đúng/Sai</span>',
    short_answer: '<span class="badge bg-warning-subtle text-dark"><i class="bi bi-pencil-square me-1"></i>Trả lời ngắn</span>'
};

const DIFF_LBL = {
    easy: '<span class="badge bg-success">Nhận biết</span>',
    medium: '<span class="badge bg-warning text-dark">Thông hiểu</span>',
    hard: '<span class="badge bg-danger">Vận dụng</span>'
};

function renderQuestions() {
    const list = document.getElementById('questionList');
    list.innerHTML = '';
    
    if(questions.length === 0) {
        list.innerHTML = '<div class="col-12 py-5 text-center text-muted"><i class="bi bi-inbox fs-1 d-block mb-3"></i>Không tìm thấy câu hỏi nào.</div>';
        return;
    }

    questions.forEach((q, idx) => {
        const needsReview = isNeedsReview(q);
        const canEdit = q.can_edit === true;
        const reviewBadge = needsReview
            ? (canEdit
                ? `<span class="badge bg-danger ms-2 cursor-pointer" onclick="openQuickReview(${q.id})" title="Nhấp để cập nhật đáp án ngay"><i class="bi bi-exclamation-triangle-fill me-1"></i>Cần Cập nhật Đáp án</span>`
                : `<span class="badge bg-danger ms-2"><i class="bi bi-exclamation-triangle-fill me-1"></i>Cần Cập nhật Đáp án</span>`)
            : '';

        let subName = q.subject_name || subjects.find(s => s.id === q.subject)?.name || 'N/A';
        const isSelected = selectedIds.includes(q.id);
        const questionImages = Array.isArray(q.question_images) ? q.question_images : [];
        const questionText = (q.text || '').trim() || QuestionRenderer.extractTextFromBlocks(q.content_json || []);
        const questionHtml = QuestionRenderer.renderStem(q);
        const imagesPreview = questionImages.slice(0, 6).map((qi) => {
            const url = qi.image_url || qi.image?.image_url;
            if (!url) return '';
            return `<img src="${escapeHtml(url)}" class="rounded border" style="height:44px;width:44px;object-fit:cover;" title="${escapeHtml(qi.placement || 'stem')} • ${escapeHtml(qi.source_type || '')}">`;
        }).join('');

        list.innerHTML += `
            <div class="col-12">
                <div class="card border-0 border-start border-4 ${needsReview ? 'border-danger' : 'border-primary'} shadow-sm h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div class="d-flex align-items-start gap-3">
                                ${canEdit ? `<div class="form-check mt-1">
                                    <input class="form-check-input q-checkbox" type="checkbox" data-id="${q.id}" ${isSelected ? 'checked' : ''} onchange="toggleSelectQuestion(${q.id}, this.checked)">
                                </div>` : ''}
                                <div>
                                    ${TYPE_LBL[q.question_type || 'multiple_choice']}
                                    ${DIFF_LBL[q.difficulty || 'medium']}
                                    <span class="badge bg-light text-muted border border-secondary border-opacity-25 ms-1">${escapeHtml(subName)}</span>
                                    ${reviewBadge}
                                </div>
                            </div>
                            <div class="d-flex gap-2">
                                ${canEdit ? `
                                <button class="btn btn-sm btn-outline-primary" onclick="editQuestion(${q.id})" title="Chỉnh sửa">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                
                                <button class="btn btn-sm btn-outline-danger" onclick="deleteQuestion(${q.id})" title="Xoá">
                                    <i class="bi bi-trash"></i>
                                </button>` : ''}
                            </div>
                        </div>
                        <div class="mb-2" style="margin-left: 2rem;">
                            ${QuestionRenderer.renderStem(q)}
                            ${imagesPreview ? `<div class="mt-2 d-flex flex-wrap gap-2">${imagesPreview}</div>` : ''}
                        </div>
                        
                        <div class="p-3 bg-light rounded mt-3 small" style="margin-left: 2rem;">
                            ${renderAnswerSnippet(q)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
}

function escapeHtml(unsafe) {
    return (unsafe ?? '').toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Redundant helpers removed. Using QuestionRenderer.

function isNeedsReview(q) {
    if (q.question_type === 'short_answer') {
        return !q.correct_answer_text || q.correct_answer_text.trim() === '';
    }
    const options = Array.isArray(q.options) ? q.options : [];
    if (options.length === 0) return true;
    // Câu Đúng/Sai: hợp lệ khi có ít nhất 2 phát biểu
    // (mỗi phát biểu đã được AI gán is_correct true/false — không yêu cầu có phát biểu nào là Đúng)
    if (q.question_type === 'true_false') {
        return options.length < 2;
    }
    return !options.some(o => !!o.is_correct);
}

function renderAnswerSnippet(q) {
    const type = q.question_type || 'multiple_choice';
    if(type === 'short_answer') {
        return `<strong>Đáp án:</strong> <span class="${!q.correct_answer_text ? 'text-danger fst-italic' : 'text-success fw-bold'}">${escapeHtml(q.correct_answer_text || '(Chưa điền đáp án)')}</span>`;
    }
    
    if(!q.options || q.options.length === 0) return '<span class="text-danger fst-italic">Chưa có tuỳ chọn đáp án nào.</span>';
    
    if(type === 'multiple_choice') {
        return q.options.map((o, i) => {
            const l = String.fromCharCode(65 + i);
            const optText = (o.text || '').trim();
            const contentHtml = QuestionRenderer.renderOption(o, q.question_images);
            return `<span class="${o.is_correct ? 'text-success fw-bold' : 'text-muted'} me-3">${l}. ${contentHtml}</span>`;
        }).join('');
    }
    // True/False
    return q.options.map((o, i) => {
        const l = String.fromCharCode(97 + i);
        const icon = o.is_correct ? '<span class="text-success fw-bold">[Đ]</span>' : '<span class="text-danger fw-bold">[S]</span>';
        const optText = (o.text || '').trim();
        const contentHtml = QuestionRenderer.renderOption(o, q.question_images);
        return `<div class="mb-1">${l}) ${contentHtml} ${icon}</div>`;
    }).join('');
}


// ─── Modal Functions ─────────────────────────────────────────────────────────

// ─── Question Editor Trigger ────────────────────────────────────────────────

function openQuestionEditor() {
    QuestionEditor.open();
}

async function editQuestion(id) {
    try {
        const res = await fetch(`/api/exams/questions/${id}/`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Lỗi tải thông tin.");
        const q = await res.json();
        QuestionEditor.open({ data: q });
    } catch (e) {
        showGlobalAlert(e.message, 'danger');
    }
}

let reviewQId = null;

function openQuickReview(qId) {
    reviewQId = qId;
    const q = questions.find(x => x.id === qId);
    if(!q) return;

    const c = document.getElementById('quickReviewContent');
    let html = '';
    const type = q.question_type || 'multiple_choice';
    const stemHtml = QuestionRenderer.renderStem(q);
    html += `<div class="p-3 bg-light border rounded mb-3">${stemHtml}</div>`;

    if (type === 'short_answer') {
        html += `
            <label class="fw-bold mb-1">Đáp án đúng:</label>
            <input type="text" id="qrText" class="form-control" placeholder="Nhập số hoặc văn bản ngắn..." value="${escapeHtml(q.correct_answer_text || '')}">
        `;
    } else if (type === 'multiple_choice') {
        html += `<label class="fw-bold mb-2">Chọn đáp án đúng (A/B/C/D):</label>`;
        if(q.options && q.options.length) {
            q.options.forEach((o, i) => {
                html += `
                <div class="form-check mb-2">
                    <input class="form-check-input" type="radio" name="qrOpt" value="${i}" id="qrOpt${i}" ${o.is_correct?'checked':''}>
                    <label class="form-check-label" for="qrOpt${i}">${String.fromCharCode(65+i)}. ${escapeHtml(o.text)}</label>
                </div>`;
            });
        }
    } else if (type === 'true_false') {
        html += `<label class="fw-bold mb-2">Chọn Đúng/Sai:</label>`;
        if(q.options && q.options.length) {
            q.options.forEach((o, i) => {
                html += `
                <div class="d-flex align-items-center mb-2 justify-content-between p-2 border rounded">
                    <span>${String.fromCharCode(97+i)}) ${escapeHtml(o.text)}</span>
                    <div class="btn-group btn-group-sm">
                        <input type="radio" class="btn-check" name="qrTf_${i}" id="qrTf_${i}_t" value="true" ${o.is_correct?'checked':''}>
                        <label class="btn btn-outline-success" for="qrTf_${i}_t">Đ</label>
                        <input type="radio" class="btn-check" name="qrTf_${i}" id="qrTf_${i}_f" value="false" ${!o.is_correct?'checked':''}>
                        <label class="btn btn-outline-danger" for="qrTf_${i}_f">S</label>
                    </div>
                </div>`;
            });
        }
    }

    c.innerHTML = html;
    new bootstrap.Modal(document.getElementById('quickReviewModal')).show();
}

async function saveQuickReview() {
    const q = questions.find(x => x.id === reviewQId);
    if(!q) return;
    
    const type = q.question_type || 'multiple_choice';
    let options = JSON.parse(JSON.stringify(q.options || []));
    let cat = q.correct_answer_text;

    if (type === 'short_answer') {
        cat = document.getElementById('qrText').value.trim();
        if(!cat) { alert('Vui lòng nhập.'); return; }
    } else if (type === 'multiple_choice') {
        const sel = document.querySelector('input[name="qrOpt"]:checked');
        if(!sel) { alert('Vui lòng chọn 1 ý.'); return; }
        const idx = parseInt(sel.value);
        options.forEach((o, i) => o.is_correct = (i === idx));
    } else if (type === 'true_false') {
        options.forEach((o, i) => {
            const val = document.querySelector(`input[name="qrTf_${i}"]:checked`)?.value;
            o.is_correct = (val === 'true');
        });
    }

    try {
        const res = await fetch(`/api/exams/questions/${reviewQId}/update-full/`, {
            method: 'PUT',
            headers: authHeaders(),
            body: JSON.stringify({
                text: q.text,
                difficulty: q.difficulty,
                question_type: type,
                context: q.context,
                correct_answer_text: cat,
                options: options
            })
        });
        
        if(res.ok) {
            bootstrap.Modal.getInstance(document.getElementById('quickReviewModal')).hide();
            showGlobalAlert('Cập nhật đáp án thành công!', 'success');
            loadQuestions();
        } else {
            alert('Lỗi cập nhật');
        }
    } catch(e) {
        alert('Lỗi mạng');
    }
}

async function bulkDeleteQuestions() {
    if(!selectedIds.length) return;
    if(!confirm(`Bạn có chắc muốn xoá ${selectedIds.length} câu hỏi đã chọn?`)) return;

    try {
        const res = await fetch('/api/exams/questions/bulk-delete/', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ ids: selectedIds })
        });
        if(res.ok) {
            showGlobalAlert(`Đã xoá ${selectedIds.length} câu hỏi.`, 'warning');
            selectedIds = [];
            loadQuestions();
        } else {
            alert('Lỗi khi xoá hàng loạt');
        }
    } catch(e) {
        console.error(e);
        alert('Lỗi mạng');
    }
}

async function deleteQuestion(id) {
    if(!confirm('Bạn có chắc xoá câu hỏi này khỏi ngân hàng?')) return;
    try {
        const res = await fetch(`/api/exams/questions/${id}/`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        if(res.ok) {
            showGlobalAlert('Đã xoá.', 'warning');
            loadQuestions();
        }
    } catch(e) { console.error(e); }
}

document.addEventListener("DOMContentLoaded", init);


// ─── AI Modal Initialization ──────────────────────────────────────────────
async function initAiGenerator() {
    AIGenerator.init({
        context: 'bank',
        onSaveSuccess: loadQuestions
    });
}

// ─── RAG Helpers ───
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

