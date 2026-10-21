/**
 * AI Generator Shared Controller
 * Unifies AI Modal logic across Question Bank and Quiz Builder
 */

const AIGenerator = {
    config: {
        context: 'bank', // 'bank' or 'quiz'
        onSaveSuccess: null,
        quizId: null,
        subjectId: null
    },
    
    currentDrafts: {
        file: [],
        rag: []
    },
    
    aiParsingInProgress: false,

    init(options = {}) {
        this.config = { ...this.config, ...options };
        this.bindEvents();
        this.setupBeforeUnload();
    },

    setupBeforeUnload() {
        window.addEventListener('beforeunload', (e) => {
            if (this.aiParsingInProgress) {
                e.preventDefault();
                e.returnValue = 'AI đang phân tích tài liệu. Nếu thoát, dữ liệu sẽ bị mất. Bạn có chắc muốn rời trang?';
                return e.returnValue;
            }
        });
    },

    authHeaders() {
        return { 'Content-Type': 'application/json' };
    },

    bindEvents() {
        if (window.aiGeneratorEventsBound) return;
        window.aiGeneratorEventsBound = true;

        document.addEventListener('submit', async (e) => {
            const extractForm = e.target.closest('#aiExtractForm');
            if (extractForm) {
                e.preventDefault();
                await this.handleFileExtraction();
                return;
            }

            const ragForm = e.target.closest('#ragGenerateForm');
            if (ragForm) {
                e.preventDefault();
                await this.handleRagGeneration();
                return;
            }
        });
        
        // Drag and drop for file input if needed (optional enhancement)
    },

    async handleFileExtraction() {
        const fileInput = document.getElementById('aiFileInput');
        const file = fileInput?.files?.[0];
        if (!file) return;

        const btn = document.getElementById('btnExtractAI');
        const loader = document.getElementById('aiExtractLoading');
        const errBox = document.getElementById('aiExtractError');
        const saveBtn = document.getElementById('btnSaveDraftsFile');

        if (errBox) errBox.textContent = '';
        if (btn) btn.disabled = true;
        if (saveBtn) saveBtn.style.display = 'none';

        if (loader) {
            loader.innerHTML = `
                <div class="d-flex align-items-center gap-2 text-primary">
                    <span class="spinner-border spinner-border-sm" role="status"></span>
                    <span><strong>AI đang phân tích tài liệu...</strong><br>
                    <small class="text-muted">Quá trình này có thể mất 1–3 phút tuỳ dung lượng file. Vui lòng <strong>không đóng hoặc chuyển trang</strong> trong thời gian chờ.</small></span>
                </div>`;
            loader.style.display = 'block';
        }

        this.aiParsingInProgress = true;

        try {
            const signature = await window.getCloudinarySignature();
            const filesData = [];
            const filesCount = fileInput.files.length;

            for (let i = 0; i < filesCount; i++) {
                const f = fileInput.files[i];
                if (errBox) errBox.innerHTML = `<span class="text-info">Đang tải lên mây (${i + 1}/${filesCount})...</span>`;

                const formData = new FormData();
                formData.append('file', f);
                formData.append('api_key', signature.api_key);
                formData.append('timestamp', signature.timestamp);
                formData.append('signature', signature.signature);

                const cloudRes = await fetch(`https://api.cloudinary.com/v1_1/${signature.cloud_name}/auto/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (!cloudRes.ok) throw new Error('Có lỗi khi upload file lên Cloudinary.');
                const cloudData = await cloudRes.json();
                filesData.push({ 
                    file_url: cloudData.secure_url, 
                    file_name: f.name,
                    public_id: cloudData.public_id,
                    resource_type: cloudData.resource_type
                });
            }

            if (errBox) errBox.innerHTML = '<span class="text-success">Tải lên xong. Đang trích xuất câu hỏi...</span>';

            const res = await fetch('/api/ai/generate/extract-file/', {
                method: 'POST',
                headers: this.authHeaders(),
                body: JSON.stringify({
                    files: filesData,
                    subject_id: this.config.subjectId || document.getElementById('aiExtractSubject')?.value
                }),
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Lỗi trích xuất từ server.');

            window.extractedImagesMap = data.images || {};
            this.currentDrafts.file = Array.isArray(data.questions) ? data.questions : [];
            this.renderDraftBoard('file');
            if (saveBtn && this.currentDrafts.file.length) saveBtn.style.display = 'inline-block';
            if (errBox) errBox.innerHTML = '';
        } catch (err) {
            if (errBox) errBox.textContent = err.message || 'Lỗi kết nối tới AI Service.';
        } finally {
            this.aiParsingInProgress = false;
            if (btn) btn.disabled = false;
            if (loader) loader.style.display = 'none';
        }
    },

    async handleRagGeneration() {
        const topic = (document.getElementById('ragTopic')?.value || '').trim();
        if (!topic) return;

        const btn = document.getElementById('btnGenerateRAG');
        const loader = document.getElementById('ragLoading');
        const errBox = document.getElementById('ragError');
        const saveBtn = document.getElementById('btnSaveDraftsRag');

        if (errBox) errBox.textContent = '';
        if (btn) btn.disabled = true;
        if (saveBtn) saveBtn.style.display = 'none';

        if (loader) {
            loader.innerHTML = `
                <div class="d-flex align-items-center gap-2 text-success">
                    <span class="spinner-border spinner-border-sm" role="status"></span>
                    <span><strong>AI đang sinh câu hỏi...</strong><br>
                    <small class="text-muted">Quá trình này có thể mất 30-60 giây. Vui lòng không đóng trang.</small></span>
                </div>`;
            loader.style.display = 'block';
        }

        this.aiParsingInProgress = true;

        try {
            const res = await fetch('/api/ai/generate/from-rag/', {
                method: 'POST',
                headers: this.authHeaders(),
                body: JSON.stringify({
                    class_id: document.getElementById('ragClass')?.value,
                    topic,
                    count: parseInt(document.getElementById('ragCount')?.value || '5', 10),
                    difficulty: document.getElementById('ragDifficulty')?.value,
                    question_types: document.getElementById('ragQuestionTypes')?.value,
                    document_id: document.getElementById('ragDocument')?.value || null,
                }),
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Lỗi sinh câu hỏi từ RAG.');

            this.currentDrafts.rag = Array.isArray(data.questions) ? data.questions : [];
            this.renderDraftBoard('rag');
            if (saveBtn && this.currentDrafts.rag.length) saveBtn.style.display = 'inline-block';
        } catch (err) {
            if (errBox) errBox.textContent = err.message || 'Lỗi kết nối tới AI Service.';
        } finally {
            this.aiParsingInProgress = false;
            if (btn) btn.disabled = false;
            if (loader) loader.style.display = 'none';
        }
    },

    renderDraftBoard(source) {
        const drafts = this.currentDrafts[source];
        const board = document.getElementById(source === 'file' ? 'aiDraftBoardFile' : 'aiDraftBoardRag');
        if (!board) return;

        if (!drafts.length) {
            board.innerHTML = '<div class="text-center text-muted mt-5">Không tìm thấy câu hỏi nào hợp lệ.</div>';
            return;
        }

        board.innerHTML = drafts.map((q, index) => {
            const typeLabel = this.getTypeBadge(q.question_type);
            const diffLabel = this.getDiffBadge(q.difficulty);
            const unresolved = !this.hasConfiguredAnswer(q);
            let contextHtml = '';
            // true_false: renderQuestionStem already renders question_text + context, skip here
            if (q.question_type !== 'true_false' && q.context) {
                contextHtml = `<div class="bg-light p-2 mb-2 rounded small border-start border-3 border-secondary text-muted"><strong>Ngữ cảnh:</strong> ${this.renderContext(q.context)}</div>`;
            }
            
            return `
                <div class="card mb-3 border-primary shadow-sm">
                    <div class="card-header bg-white d-flex justify-content-between align-items-start p-3">
                        <div class="form-check w-100 pe-3">
                            <input class="form-check-input ai-draft-cb-${source} mt-2" type="checkbox" value="${index}" checked id="draft_${source}_${index}">
                            <label class="form-check-label fw-bold d-block mb-1" for="draft_${source}_${index}">Câu ${index + 1}:</label>
                            <div class="ps-4">
                                ${contextHtml}
                                ${this.renderQuestionStem(q)}
                            </div>
                            ${unresolved ? '<div class="ps-4 mt-1"><span class="badge bg-danger">Chưa cài đặt đáp án đúng</span></div>' : ''}
                        </div>
                        <div class="d-flex gap-1 align-items-center">
                            ${typeLabel} ${diffLabel}
                            <button class="btn btn-sm btn-outline-secondary ms-2" title="Chỉnh sửa nội dung" onclick="AIGenerator.editDraft('${source}', ${index})"><i class="bi bi-pencil"></i></button>
                            <button class="btn btn-sm btn-outline-danger" onclick="AIGenerator.deleteDraft('${source}', ${index})"><i class="bi bi-trash"></i></button>
                        </div>
                    </div>
                    <div class="card-body p-3">
                        ${this.renderQuestionContent(q)}
                    </div>
                </div>`;
        }).join('');
    },
    
    async saveSelectedDrafts(source) {
        const checkboxes = document.querySelectorAll(`.ai-draft-cb-${source}:checked`);
        if (checkboxes.length === 0) {
            alert('Vui lòng chọn ít nhất 1 câu hỏi.');
            return;
        }

        const selectedQuestions = Array.from(checkboxes).map(cb => this.currentDrafts[source][parseInt(cb.value, 10)]);
        const btnId = source === 'file' ? 'btnSaveDraftsFile' : 'btnSaveDraftsRag';
        const saveToQuizSwitchId = source === 'file' ? 'saveToQuizFile' : 'saveToQuizRag';
        
        const shouldAddToQuiz = !!document.getElementById(saveToQuizSwitchId)?.checked;
        const btn = document.getElementById(btnId);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang lưu...';
        }

        try {
            const res = await fetch('/api/ai/generate/save-bulk/', {
                method: 'POST',
                headers: this.authHeaders(),
                body: JSON.stringify({
                    questions: selectedQuestions,
                    quiz_id: shouldAddToQuiz ? this.config.quizId : null,
                    subject_id: this.config.subjectId || document.getElementById('aiExtractSubject')?.value
                }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Lỗi lưu câu hỏi.');
            }

            if (window.showGlobalAlert) window.showGlobalAlert(`Đã nhập ${selectedQuestions.length} câu hỏi thành công!`, 'success');
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('aiGeneratorModal'));
            if (modal) modal.hide();

            if (typeof this.config.onSaveSuccess === 'function') {
                await this.config.onSaveSuccess();
            }
        } catch (err) {
            alert(err.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-cloud-arrow-up me-1"></i>Lưu các câu đã chọn';
            }
        }
    },

    deleteDraft(source, index) {
        this.currentDrafts[source].splice(index, 1);
        this.renderDraftBoard(source);
        const saveBtn = document.getElementById(source === 'file' ? 'btnSaveDraftsFile' : 'btnSaveDraftsRag');
        if (saveBtn) saveBtn.style.display = this.currentDrafts[source].length ? 'inline-block' : 'none';
    },

    selectAllDrafts(source) {
        const checkboxes = document.querySelectorAll(`.ai-draft-cb-${source}`);
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allChecked);
    },

    editDraft(source, index) {
        const draft = this.currentDrafts[source][index];
        QuestionEditor.open({
            data: draft,
            isDraft: true,
            draftSource: source,
            draftIndex: index,
            onSave: (payload, src, idx) => {
                // Update local draft storage
                this.currentDrafts[src][idx] = { ...this.currentDrafts[src][idx], ...payload };
                this.renderDraftBoard(src);
            }
        });
    },

    // UI Helpers copied from original logic
    escapeHtml(t) {
        if (!t) return '';
        return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    getTypeBadge(t) {
        const labels = {
            'multiple_choice': '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">Trắc nghiệm</span>',
            'true_false': '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Đúng/Sai</span>',
            'short_answer': '<span class="badge bg-info-subtle text-info border border-info-subtle">Trả lời ngắn</span>'
        };
        return labels[t] || labels.multiple_choice;
    },

    getDiffBadge(d) {
        const labels = {
            'easy': '<span class="badge bg-success-subtle text-success border border-success-subtle">Nhận biết</span>',
            'medium': '<span class="badge bg-info-subtle text-info border border-info-subtle">Thông hiểu</span>',
            'hard': '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">Vận dụng</span>'
        };
        return labels[d] || labels.medium;
    },

    renderQuestionStem(q) {
        return QuestionRenderer.renderStem(q);
    },

    renderContext(text) {
        if (!text) return '';
        const imageMap = window.extractedImagesMap || {};
        return QuestionRenderer._renderPlainWithImages(text, imageMap);
    },

    renderQuestionContent(q) {
        const type = q.question_type || 'multiple_choice';
        if (type === 'short_answer') {
            return `<div class="p-2 border rounded bg-light small"><strong>Đáp án đúng:</strong> ${this.escapeHtml(q.correct_answer_text)}</div>`;
        }
        const options = Array.isArray(q.options) ? q.options : [];
        
        // Câu Đúng/Sai: mỗi phát biểu hiển thị nhãn Đúng/Sai thay vì A/B/C/D
        if (type === 'true_false') {
            const labels = ['a', 'b', 'c', 'd'];
            return `<div class="d-flex flex-column gap-2">${options.map((o, i) => {
                const isCorrect = o.is_correct === true;
                const label = labels[i] || String.fromCharCode(97 + i);
                const answerBadge = isCorrect
                    ? '<span class="badge bg-success ms-2"><i class="bi bi-check-lg"></i> Đúng</span>'
                    : '<span class="badge bg-danger ms-2"><i class="bi bi-x-lg"></i> Sai</span>';
                return `
                <div class="p-2 border rounded ${isCorrect ? 'bg-success-subtle border-success' : 'bg-danger-subtle border-danger'} small">
                    <strong class="me-1">${label})</strong> ${QuestionRenderer.renderOption(o, q.question_images)} ${answerBadge}
                </div>`;
            }).join('')}</div>`;
        }
        
        return `<div class="row g-2">${options.map((o, i) => `
            <div class="col-md-6">
                <div class="p-2 border rounded ${o.is_correct ? 'bg-success-subtle border-success' : 'bg-white'} small h-100">
                    <strong class="me-1">${String.fromCharCode(65 + i)}.</strong> ${QuestionRenderer.renderOption(o, q.question_images)}
                    ${o.is_correct ? ' <i class="bi bi-check-lg text-success ms-1"></i>' : ''}
                </div>
            </div>`).join('')}</div>`;
    },

    hasConfiguredAnswer(q) {
        if (q.question_type === 'short_answer') return !!(q.correct_answer_text && q.correct_answer_text.trim());
        // Câu Đúng/Sai: hợp lệ khi có ít nhất 2 phát biểu (mỗi phát biểu đã được gán đúng/sai bởi AI)
        // Không yêu cầu phải có phát biểu nào là_correct: true — vì is_correct là tính chất của phát biểu,
        // không phải "đây là đáp án đúng" như multiple_choice.
        if (q.question_type === 'true_false') {
            return Array.isArray(q.options) && q.options.length >= 2;
        }
        return Array.isArray(q.options) && q.options.some(o => o.is_correct);
    }
};

// Global callbacks for onclick handlers in HTML
window.selectAllDrafts = (s) => AIGenerator.selectAllDrafts(s);
window.saveSelectedDrafts = (s) => AIGenerator.saveSelectedDrafts(s);
