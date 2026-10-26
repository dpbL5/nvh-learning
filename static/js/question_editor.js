/**
 * Shared Question Editor Controller
 * Handles creation and editing of questions across Quiz Builder, Question Bank, and AI Drafts.
 */

function escapeHtml(value) {
    return (value ?? '').toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

const QuestionEditor = {
    config: {
        context: 'bank', // 'bank' or 'quiz'
        onSave: null,
        subjects: [],
        currentQuizId: null,
    },
    
    state: {
        mde: null,
        editingId: null,
        isDraft: false,
        draftSource: null, // 'file' or 'rag'
        draftIndex: null,
        currentImages: [],
    },

    init(options = {}) {
        this.config = { ...this.config, ...options };
        this.bindEvents();
    },

    bindEvents() {
        if (window.questionEditorEventsBound) return;
        window.questionEditorEventsBound = true;

        const typeSelect = document.getElementById('editorType');
        if (typeSelect) {
            typeSelect.addEventListener('change', () => this.renderOptionFields());
        }

        const textEl = document.getElementById('editorText');
        if (textEl) {
            textEl.addEventListener('input', () => this.updatePreview());
        }

        const tfTextEl = document.getElementById('editorTfText');
        if (tfTextEl) {
            tfTextEl.addEventListener('input', () => this.updatePreview());
        }

        const tfQEl = document.getElementById('editorTfQuestion');
        if (tfQEl) {
            tfQEl.addEventListener('input', () => this.updatePreview());
        }

        const ctxEl = document.getElementById('editorContext');
        if (ctxEl) {
            ctxEl.addEventListener('input', () => this.updatePreview());
        }

        const saveBtn = document.getElementById('btnEditorSave');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.handleSave());
        }

        const uploadBtn = document.getElementById('btnEditorUploadImage');
        if (uploadBtn) {
            uploadBtn.addEventListener('click', () => this.handleImageUpload());
        }

        const modalEl = document.getElementById('sharedQuestionModal');
        if (modalEl) {
            modalEl.addEventListener('shown.bs.modal', () => {
                const textEl = document.getElementById('editorText');
                if (textEl) textEl.focus();
            });
        }
    },

    /**
     * Open the editor modal
     * @param {Object} options 
     *   - data: question object (optional)
     *   - isDraft: boolean
     *   - draftSource: 'file'|'rag'
     *   - draftIndex: number
     *   - onSave: callback function
     */
    open(options = {}) {
        const { data, isDraft, draftSource, draftIndex, onSave } = options;
        
        this.state.editingId = isDraft ? null : (data ? data.id : null);
        this.state.isDraft = !!isDraft;
        this.state.draftSource = draftSource;
        this.state.draftIndex = draftIndex;
        if (onSave) this.config.onSave = onSave;

        this.resetForm();
        this.initEditor();

        const modalTitle = document.getElementById('sharedQuestionModalTitle');
        const modalHeader = document.getElementById('sharedQuestionModalHeader');
        const addQuizWrap = document.getElementById('editorAddQuizWrap');

        if (this.state.isDraft) {
            modalTitle.innerText = 'Chỉnh sửa bản nháp AI';
            modalHeader.className = 'modal-header bg-gradient-success text-white';
            if (addQuizWrap) addQuizWrap.style.display = 'none';
        } else if (this.state.editingId) {
            modalTitle.innerText = 'Chỉnh sửa câu hỏi';
            modalHeader.className = 'modal-header bg-gradient-primary text-white';
            if (addQuizWrap) addQuizWrap.style.display = 'none';
        } else {
            modalTitle.innerText = 'Tạo câu hỏi thủ công';
            modalHeader.className = 'modal-header bg-gradient-primary text-white';
            if (this.config.context === 'quiz' && addQuizWrap) {
                addQuizWrap.style.display = 'block';
            }
        }

        this.populateSubjects();

        if (data) {
            this.fillData(data);
        } else {
            this.renderOptionFields();
            this.updatePreview();
        }

        const modal = new bootstrap.Modal(document.getElementById('sharedQuestionModal'));
        modal.show();
    },

    resetForm() {
        const form = document.getElementById('sharedQuestionForm');
        if (form) form.reset();
        const textEl = document.getElementById('editorText');
        if (textEl) textEl.value = '';
        const tfQEl = document.getElementById('editorTfQuestion');
        if (tfQEl) tfQEl.value = '';
        const tfTextEl = document.getElementById('editorTfText');
        if (tfTextEl) tfTextEl.value = '';
        const ctxEl = document.getElementById('editorContext');
        if (ctxEl) ctxEl.value = '';
        document.getElementById('editorError').textContent = '';
        document.getElementById('editorImageStatus').textContent = '';
        document.getElementById('editorImageList').innerHTML = '<div class="text-muted small p-2">Lưu câu hỏi trước khi quản lý ảnh đính kèm chi tiết.</div>';
        this.state.currentImages = [];
    },

    initEditor() {
        // We now use standard textarea, no need for EasyMDE
        const textEl = document.getElementById('editorText');
        if (textEl) {
            textEl.placeholder = "Nhập nội dung câu hỏi. Dùng [IMG:sha256] để chèn ảnh...";
            // style handled in HTML
        }
        this.updatePreview();
    },

    populateSubjects() {
        const subSel = document.getElementById('editorSubject');
        if (!subSel) return;
        
        subSel.innerHTML = '';
        this.config.subjects.forEach(s => {
            subSel.add(new Option(s.name, s.id));
        });

        // If in quiz context, set default subject and disable if config says so
        if (this.config.context === 'quiz' && this.config.subjectId) {
            subSel.value = this.config.subjectId;
            // subSel.disabled = true; // Optional: let teacher change subject if they want
        }
    },

    fillData(q) {
        document.getElementById('editorType').value = q.question_type || 'multiple_choice';
        document.getElementById('editorDiff').value = q.difficulty || 'medium';
        const gradeEl = document.getElementById('editorGrade');
        if (gradeEl) gradeEl.value = q.grade || '';
        
        if (q.subject) document.getElementById('editorSubject').value = q.subject;
        
        const qText = q.text || (Array.isArray(q.content_json) ? this.extractTextFromBlocks(q.content_json) : '');
        const qContext = q.context || '';
        const qQuestionText = q.question_text || '';
        const textEl = document.getElementById('editorText');
        const tfQEl = document.getElementById('editorTfQuestion');
        const tfTextEl = document.getElementById('editorTfText');
        const ctxEl = document.getElementById('editorContext');

        if (q.question_type === 'true_false') {
            // 3-field layout: editorTfQuestion = question_text, editorContext = context, editorTfText = text (stem)
            if (textEl) textEl.value = '';
            if (tfQEl) tfQEl.value = qQuestionText;
            if (ctxEl) ctxEl.value = qContext;
            if (tfTextEl) tfTextEl.value = qText;
        } else {
            if (textEl) textEl.value = qText;
            if (tfQEl) tfQEl.value = '';
            if (ctxEl) ctxEl.value = '';
            if (tfTextEl) tfTextEl.value = '';
        }

        this.renderOptionFields();

        // Fill options
        if (q.question_type === 'short_answer') {
            const saInput = document.getElementById('editorSaCorrect');
            if (saInput) saInput.value = q.correct_answer_text || '';
        } else if (Array.isArray(q.options)) {
            const optTexts = document.querySelectorAll('.editorOptText');
            q.options.forEach((opt, i) => {
                const optVal = opt.text || (Array.isArray(opt.content_json) ? this.extractTextFromBlocks(opt.content_json) : '');
                if (optTexts[i]) optTexts[i].value = optVal;
                
                if (q.question_type === 'multiple_choice') {
                    if (opt.is_correct) {
                        const radio = document.querySelector(`input[name="editorOptCorrect"][value="${i}"]`);
                        if (radio) radio.checked = true;
                    }
                } else if (q.question_type === 'true_false') {
                    const tRadio = document.getElementById(`editorTfOpt_${i}_t`);
                    const fRadio = document.getElementById(`editorTfOpt_${i}_f`);
                    if (opt.is_correct) {
                        if (tRadio) tRadio.checked = true;
                    } else {
                        if (fRadio) fRadio.checked = true;
                    }
                }
            });
        }

        if (!this.state.isDraft && this.state.editingId) {
            this.state.currentImages = Array.isArray(q.question_images) ? q.question_images : [];
            this.renderImageList();
        }
    },

    _getTfText() {
        // Returns the effective question text for true/false questions
        const tfEl = document.getElementById('editorTfText');
        if (tfEl && tfEl.value.trim()) return tfEl.value.trim();
        return 'Sau đây là các nhận định/nhận xét như sau:';
    },

    renderOptionFields() {
        const type = document.getElementById('editorType').value;
        const container = document.getElementById('editorOptionsContainer');
        const ctxWrap = document.getElementById('editorContextWrapper');
        const mainLabel = document.getElementById('editorMainLabel');
        const mainText = document.getElementById('editorText');

        if (type === 'true_false') {
            if (ctxWrap) ctxWrap.style.display = 'block';
            if (mainLabel) mainLabel.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Nội dung câu hỏi';
            if (mainText) {
                mainText.placeholder = 'Nhập nội dung câu hỏi...';
                mainText.style.display = 'none';
            }
            
            // Pre-fill stem if empty
            const tfTextEl = document.getElementById('editorTfText');
            if (tfTextEl && !tfTextEl.value.trim()) {
                tfTextEl.value = 'Sau đây là các nhận định/nhận xét của ... về ... như sau:';
            }
        } else {
            if (ctxWrap) ctxWrap.style.display = 'none';
            if (mainLabel) mainLabel.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Nội dung câu hỏi';
            if (mainText) {
                mainText.placeholder = 'Nhập nội dung câu hỏi...';
                mainText.style.display = '';
            }
        }

        let html = '';
        if (type === 'multiple_choice') {
            html = `
                <p class="text-muted small mb-2">Nhập 4 phương án và chọn 1 phương án đúng:</p>
                ${[0, 1, 2, 3].map(i => `
                    <div class="d-flex mb-2 align-items-center gap-2">
                        <div class="form-check m-0">
                            <input class="form-check-input" type="radio" name="editorOptCorrect" value="${i}" ${i === 0 ? 'checked' : ''}>
                        </div>
                        <span class="fw-bold">${String.fromCharCode(65 + i)}.</span>
                        <input type="text" class="form-control form-control-sm editorOptText" placeholder="Nội dung phương án ${String.fromCharCode(65 + i)}..." required>
                    </div>
                `).join('')}
            `;
        } else if (type === 'true_false') {
            html = `
                <p class="text-muted small mb-2">Nhập 4 phát biểu và xét tính Đúng/Sai:</p>
                ${[0, 1, 2, 3].map(i => `
                    <div class="d-flex mb-2 align-items-center gap-2">
                        <span class="fw-bold">${String.fromCharCode(97 + i)}.</span>
                        <input type="text" class="form-control form-control-sm editorOptText" placeholder="Phát biểu ${String.fromCharCode(97 + i)}..." required>
                        <div class="btn-group btn-group-sm ms-2" role="group">
                            <input type="radio" class="btn-check editorTfOpt_${i}" name="editorTfOpt_${i}" id="editorTfOpt_${i}_t" value="true">
                            <label class="btn btn-outline-success px-2" for="editorTfOpt_${i}_t">Đ</label>
                            <input type="radio" class="btn-check editorTfOpt_${i}" name="editorTfOpt_${i}" id="editorTfOpt_${i}_f" value="false" checked>
                            <label class="btn btn-outline-danger px-2" for="editorTfOpt_${i}_f">S</label>
                        </div>
                    </div>
                `).join('')}
            `;
        } else if (type === 'short_answer') {
            html = `
                <p class="text-muted small mb-2">Nhập chính xác đáp án (hệ thống tự loại bỏ khoảng trắng khi chấm):</p>
                <input type="text" id="editorSaCorrect" class="form-control form-control-lg text-primary fw-bold" placeholder="Vd: 5.5, HCl..." required>
            `;
        }
        container.innerHTML = html;
    },

    async handleSave() {
        const errEl = document.getElementById('editorError');
        errEl.textContent = '';

        const text = (document.getElementById('editorText')?.value || '').trim();
        const difficulty = document.getElementById('editorDiff').value;
        const qType = document.getElementById('editorType').value;
        const subject = document.getElementById('editorSubject').value;
        const grade = document.getElementById('editorGrade')?.value || '';

        let effectiveText, effectiveContext, effectiveQuestionText;

        if (qType === 'true_false') {
            effectiveQuestionText = (document.getElementById('editorTfQuestion')?.value || '').trim();
            effectiveContext = (document.getElementById('editorContext')?.value || '').trim();
            effectiveText = this._getTfText(); // stem from editorTfText
            if (!effectiveText) { errEl.textContent = "Vui lòng nhập câu dẫn (Lệnh hỏi)."; return; }
        } else {
            effectiveText = text;
            effectiveContext = '';
            effectiveQuestionText = '';
            if (!effectiveText) { errEl.textContent = "Bạn chưa nhập nội dung câu hỏi."; return; }
        }

        let payload = {
            question_type: qType,
            text: effectiveText,
            content_json: this._buildContentJson(effectiveText),
            difficulty: difficulty,
            grade: grade,
            context: effectiveContext,
            question_text: effectiveQuestionText,
            subject: subject,
            question_images: this.state.currentImages.map(img => ({
                sha256: img.image?.sha256 || img.sha256 || '',
                url: img.image?.image_url || img.image_url || '',
                placement: img.placement || 'stem'
            }))
        };

        if (qType === 'short_answer') {
            const correctText = (document.getElementById('editorSaCorrect')?.value || '').trim();
            if (!correctText) { errEl.textContent = "Vui lòng nhập đáp án đúng."; return; }
            payload.correct_answer_text = correctText;
        } else {
            const optTexts = document.querySelectorAll('.editorOptText');
            let options = [];
            let hasEmpty = false;

            if (qType === 'multiple_choice') {
                const correctVal = document.querySelector('input[name="editorOptCorrect"]:checked');
                const correctIdx = correctVal ? parseInt(correctVal.value) : 0;

                optTexts.forEach((el, i) => {
                    const val = el.value.trim();
                    if (!val) hasEmpty = true;
                    options.push({ 
                        text: val, 
                        content_json: this._buildContentJson(val),
                        is_correct: (i === correctIdx) 
                    });
                });
            } else if (qType === 'true_false') {
                optTexts.forEach((el, i) => {
                    const val = el.value.trim();
                    if (!val) hasEmpty = true;
                    const isCorrect = document.getElementById(`editorTfOpt_${i}_t`).checked;
                    options.push({ 
                        text: val, 
                        content_json: this._buildContentJson(val),
                        is_correct: isCorrect 
                    });
                });
            }

            if (hasEmpty) { errEl.textContent = "Vui lòng nhập đầy đủ nội dung các phương án."; return; }
            payload.options = options;
        }

        const btn = document.getElementById('btnEditorSave');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang lưu...';

        try {
            if (this.state.isDraft) {
                // Return data to AI Generator
                if (typeof this.config.onSave === 'function') {
                    await this.config.onSave(payload, this.state.draftSource, this.state.draftIndex);
                }
                this.hide();
            } else {
                // Save to API
                const isEdit = !!this.state.editingId;
                const addToQuizNow = !!document.getElementById('editorAddToQuiz')?.checked;
                
                let res;
                if (isEdit) {
                    res = await fetch(`/api/exams/questions/${this.state.editingId}/update-full/`, {
                        method: 'PUT',
                        headers: this.authHeaders(),
                        body: JSON.stringify(payload)
                    });
                } else if (this.config.context === 'quiz' && addToQuizNow) {
                    res = await fetch('/api/ai/generate/save-bulk/', {
                        method: 'POST',
                        headers: this.authHeaders(),
                        body: JSON.stringify({
                            questions: [payload],
                            quiz_id: this.config.currentQuizId,
                            subject_id: subject
                        })
                    });
                } else {
                    res = await fetch('/api/exams/questions/', {
                        method: 'POST',
                        headers: this.authHeaders(),
                        body: JSON.stringify(payload)
                    });
                }

                if (res.ok) {
                    if (typeof this.config.onSave === 'function') await this.config.onSave();
                    this.hide();
                    if (window.showGlobalAlert) window.showGlobalAlert(isEdit ? 'Cập nhật thành công!' : 'Tạo mới thành công!', 'success');
                } else {
                    const data = await res.json();
                    errEl.textContent = (data.error || data.detail || "Lỗi lưu câu hỏi.");
                }
            }
        } catch (e) {
            errEl.textContent = "Lỗi kết nối server.";
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Lưu câu hỏi';
        }
    },

    hide() {
        const modalEl = document.getElementById('sharedQuestionModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
    },

    authHeaders(isMultipart = false) {
        const h = {};
        if (!isMultipart) h['Content-Type'] = 'application/json';
        return h;
    },

    async handleImageUpload() {
        if (!this.state.editingId && !this.state.isDraft) {
            alert('Vui lòng lưu câu hỏi trước khi gắn ảnh kho.');
            return;
        }

        const fileInput = document.getElementById('editorImageFile');
        const file = fileInput?.files?.[0];
        if (!file) return;

        const statusEl = document.getElementById('editorImageStatus');
        statusEl.innerHTML = '<span class="text-primary">Đang tải...</span>';

        const fd = new FormData();
        fd.append('image', file);
        if (this.state.editingId) fd.append('question_id', this.state.editingId);
        fd.append('source_type', 'user_upload');
        fd.append('placement', 'gallery');

        try {
            const res = await fetch('/api/exams/questions/images/upload/', {
                method: 'POST',
                headers: this.authHeaders(true),
                body: fd
            });
            const data = await res.json();
            if (res.ok) {
                statusEl.innerHTML = '<span class="text-success">Thành công!</span>';
                fileInput.value = '';
                if (window.showGlobalAlert) window.showGlobalAlert('Đã tải ảnh lên kho!', 'success');
                if (this.state.editingId) {
                    this.refreshImages();
                } else if (this.state.isDraft) {
                    // For drafts, just add to local gallery state
                    // The backend returned { sha256, url, ... }
                    this.state.currentImages.push({
                        id: data.question_image_id || null,
                        image: { sha256: data.sha256, image_url: data.url }
                    });
                    this.renderImageList();
                    this.updatePreview();
                }
            } else {
                statusEl.innerHTML = `<span class="text-danger">Lỗi: ${escapeHtml(data.error || 'Thất bại')}</span>`;
            }
        } catch (e) {
            statusEl.innerHTML = '<span class="text-danger">Lỗi kết nối.</span>';
        }
    },

    async refreshImages() {
        if (!this.state.editingId) return;
        try {
            const res = await fetch(`/api/exams/questions/${this.state.editingId}/`, { headers: this.authHeaders() });
            if (res.ok) {
                const q = await res.json();
                this.state.currentImages = Array.isArray(q.question_images) ? q.question_images : [];
                this.renderImageList();
                this.updatePreview();
            }
        } catch (e) {}
    },

    renderImageList() {
        const listEl = document.getElementById('editorImageList');
        if (!listEl) return;

        if (!this.state.currentImages.length) {
            listEl.innerHTML = '<div class="text-muted small">Chưa có ảnh nào được gắn.</div>';
            return;
        }

        listEl.innerHTML = this.state.currentImages.map(img => {
            const url = img.image_url || img.image?.image_url || '';
            const sha = img.image?.sha256 || '';
            const safeSha = /^[a-fA-F0-9]{32,64}$/.test(sha) ? sha : '';
            const shortSha = safeSha ? safeSha.slice(0, 8) + '...' : 'N/A';
            return `
                <div class="card shadow-sm border" style="width: 120px; flex-shrink: 0;">
                    <img src="${escapeHtml(url)}" class="card-img-top" style="height: 80px; object-fit: cover; cursor: pointer;" onclick="QuestionEditor.copyImgTag('${safeSha}')" title="Click để chèn vào nội dung">
                    <div class="card-body p-1 text-center">
                        <div class="text-muted" style="font-size: 9px; overflow: hidden; white-space: nowrap;">${shortSha}</div>
                        <div class="d-flex justify-content-center gap-1">
                            <button type="button" class="btn btn-xs btn-link p-0" onclick="QuestionEditor.copyImgTag('${safeSha}')" title="Chép mã chèn">
                                <i class="bi bi-clipboard" style="font-size: 12px;"></i>
                            </button>
                            ${(!this.state.isDraft && img.id) ? `
                            <button type="button" class="btn btn-xs btn-link p-0 text-danger" onclick="QuestionEditor.unlinkImage(${img.id})" title="Gỡ bỏ">
                                <i class="bi bi-trash" style="font-size: 12px;"></i>
                            </button>` : ''}
                        </div>
                    </div>
                </div>`;
        }).join('');
    },

    copyImgTag(sha) {
        if (!sha) return;
        const tag = `[IMG:${sha}]`;
        navigator.clipboard.writeText(tag).then(() => {
            if (window.showGlobalAlert) window.showGlobalAlert('Đã copy mã chèn ảnh!', 'info');
            
            // Auto insert into editor at cursor
            const textEl = document.getElementById('editorText');
            if (textEl) {
                const start = textEl.selectionStart;
                const end = textEl.selectionEnd;
                const val = textEl.value;
                textEl.value = val.substring(0, start) + tag + val.substring(end);
                textEl.focus();
                textEl.selectionStart = textEl.selectionEnd = start + tag.length;
                this.updatePreview();
            }
        });
    },

    updatePreview() {
        const qType = document.getElementById('editorType')?.value || 'multiple_choice';
        const text = (document.getElementById('editorText')?.value || '').trim();
        const tfQText = (document.getElementById('editorTfQuestion')?.value || '').trim();
        const tfCtx = (document.getElementById('editorContext')?.value || '').trim();
        const tfText = (document.getElementById('editorTfText')?.value || '').trim();
        const previewEl = document.getElementById('editorPreview');
        if (!previewEl) return;
        
        const previewTitle = document.getElementById('editorPreviewTitle');
        const previewContent = document.getElementById('editorPreviewContent');
        if (!previewTitle || !previewContent) return;

        let dummyQ;
        if (qType === 'true_false') {
            dummyQ = {
                question_type: 'true_false',
                question_text: tfQText,
                context: tfCtx,
                text: tfText,
                question_images: this.state.currentImages
            };
        } else {
            dummyQ = {
                question_type: qType,
                text: text,
                question_images: this.state.currentImages,
                content_json: this._buildContentJson(text)
            };
        }

        const previewHtml = QuestionRenderer.renderStem(dummyQ);
        
        const displayTitle = tfQText || text; // Use T/F question text or general text for title
        previewTitle.innerHTML = `<span class="badge bg-primary me-2">Xem trước</span> <strong>${escapeHtml(displayTitle.substring(0, 50))}${displayTitle.length > 50 ? '...' : ''}</strong>`;
        previewContent.innerHTML = previewHtml;
    },

    _buildContentJson(text) {
        if (!text) return [];
        const blocks = [];
        const imgPattern = /\[IMG:([a-fA-F0-9]{32,64})\]/g;
        let lastEnd = 0;
        let match;
        
        while ((match = imgPattern.exec(text)) !== null) {
            const start = match.index;
            const end = imgPattern.lastIndex;
            if (start > lastEnd) {
                blocks.push({ type: 'text', value: text.substring(lastEnd, start) });
            }
            blocks.push({ type: 'image', sha256: match[1] });
            lastEnd = end;
        }
        if (lastEnd < text.length) {
            blocks.push({ type: 'text', value: text.substring(lastEnd) });
        }
        return blocks;
    },

    async unlinkImage(qImgId) {
        if (!confirm('Xoá ảnh này khỏi câu hỏi?')) return;
        try {
            const res = await fetch(`/api/exams/questions/images/${qImgId}/`, {
                method: 'DELETE',
                headers: this.authHeaders()
            });
            if (res.ok) this.refreshImages();
        } catch (e) {}
    },

    extractTextFromBlocks(blocks) {
        if (!Array.isArray(blocks)) return '';
        return blocks
            .filter(b => b && b.type === 'text')
            .map(b => b.value)
            .join(' ')
            .trim();
    },

    directUpload(file, onSuccess, onError) {
        const fd = new FormData();
        fd.append('image', file);
        fd.append('source_type', 'user_upload');
        
        fetch('/api/exams/questions/images/upload/', {
            method: 'POST',
            headers: this.authHeaders(true),
            body: fd
        })
        .then(res => res.json())
        .then(data => {
            if (data.url) onSuccess(data.url);
            else onError(data.error || 'Upload failed');
        })
        .catch(e => onError('Network error'));
    }
};

window.QuestionEditor = QuestionEditor;
