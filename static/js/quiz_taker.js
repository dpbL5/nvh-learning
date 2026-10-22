let attemptId = null, quizQuestions = [], endTimeTime = null, timerInterval = null;
let currentAnswers = {};
if (!localStorage.getItem('auth_hint')) window.location.href = '/login/';

function quizAuthHeaders() {
    return { 'Content-Type': 'application/json' };
}
function escapeHtml(s) { return (s ?? '').toString().replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;"); }
// Rendering helpers removed. Using QuestionRenderer.

async function init() {
    try {
        // 1. Fetch quiz info
        const res = await fetch('/api/exams/' + quizId + '/', {headers: quizAuthHeaders()});
        if (!res.ok) throw new Error();
        const quizInfo = await res.json();
        
        if (!quizInfo) { showGlobalAlert('Bạn không có quyền hoặc đề thi chưa mở.', 'danger'); setTimeout(function() { window.location.href='/dashboard/'; }, 2000); return; }
        document.getElementById('introTitle').textContent = quizInfo.title;
        document.getElementById('activeQuizTitle').textContent = quizInfo.title;
        document.getElementById('introDesc').textContent = quizInfo.description || 'Không có mô tả.';
        document.getElementById('introDuration').textContent = quizInfo.duration_minutes;
        document.getElementById('introCount').textContent = quizInfo.question_count;

        // 2. Check if already completed by calling start endpoint
        try {
            var startRes = await fetch('/api/exams/' + quizId + '/start/', {method:'POST', headers:quizAuthHeaders()});
            var startData = await startRes.json();
            if (startData.is_completed) {
                // Already completed — go directly to results
                document.getElementById('loadingState').style.display = 'none';
                document.getElementById('resultTitle').textContent = quizInfo.title;
                showResult(startData);
                return;
            }
        } catch(e) { /* ignore check error, show intro normally */ }

        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('introState').style.display = 'flex';
    } catch(e) { alert('Lỗi khởi tạo bài thi.'); window.location.href = '/dashboard/'; }
}

async function startQuiz() {
    document.getElementById('introState').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    try {
        const res = await fetch(`/api/exams/${quizId}/start/`, {method:'POST',headers:quizAuthHeaders()});
        const data = await res.json();
        if (data.is_completed) { document.getElementById('loadingState').style.display = 'none'; showResult(data); return; }
        if (!res.ok) { alert(data.detail || 'Không thể bắt đầu làm bài.'); window.location.href = '/dashboard/'; return; }
        attemptId = data.attempt_id;
        quizQuestions = data.questions;
        const startTime = new Date(data.start_time).getTime();
        endTimeTime = startTime + data.duration_minutes * 60 * 1000;
        renderQuestions();
        buildNavigator();
        startTimer();
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('quizState').style.display = 'block';
        updateProgress();
    } catch(e) { alert('Lỗi kết nối.'); }
}

function renderQuestions() {
    const container = document.getElementById('questionsContainer');
    document.getElementById('totalQCount').textContent = quizQuestions.length;
    quizQuestions.sort((a,b) => a.order - b.order);
    container.innerHTML = quizQuestions.map((qq, idx) => {
        const q = qq.question;
        const qType = q.question_type || 'multiple_choice';
        const typeBadges = {multiple_choice:'<span class="badge" style="background:var(--color-primary-light);color:var(--color-primary);">Trắc nghiệm</span>',true_false:'<span class="badge" style="background:var(--color-info-light);color:var(--color-info);">Đúng / Sai</span>',short_answer:'<span class="badge" style="background:var(--color-warning-light);color:var(--color-warning);">Trả lời ngắn</span>'};
        
        let contentHtml = '';
        if (qType === 'multiple_choice') {
            const keys = ['A','B','C','D'];
            contentHtml = q.options.map((opt, oi) => {
                const optBlocksHtml = QuestionRenderer.renderOption(opt, q.question_images);
                return `<div class="quiz-option" id="opt_wrap_${opt.id}" onclick="selectMC(${qq.id}, ${opt.id})">
                    <div class="quiz-option-key">${keys[oi]||oi+1}</div>
                    <div class="small">${optBlocksHtml}</div>
                    <input type="radio" name="qq_${qq.id}" id="opt_${opt.id}" value="${opt.id}" class="d-none">
                </div>`;
            }).join('');
        } else if (qType === 'true_false') {
            contentHtml = q.options.map((opt, i) => {
                const optBlocksHtml = QuestionRenderer.renderOption(opt, q.question_images);
                return `<div style="border:1px solid var(--color-border);border-radius:var(--radius-md);padding:0.875rem 1rem;margin-bottom:0.5rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;">
                    <div style="font-size:0.875rem;flex:1;">
                        <div>${String.fromCharCode(97+i)}) ${optBlocksHtml}</div>
                    </div>
                    <div style="display:flex;gap:0.5rem;flex-shrink:0;">
                        <label class="btn btn-sm btn-outline-success tf-btn" id="tf_${qq.id}_${opt.id}_t" onclick="selectTF(${qq.id},${opt.id},true)"><input type="radio" name="tf_${qq.id}_${opt.id}" value="true" class="d-none">Đúng</label>
                        <label class="btn btn-sm btn-outline-danger tf-btn" id="tf_${qq.id}_${opt.id}_f" onclick="selectTF(${qq.id},${opt.id},false)"><input type="radio" name="tf_${qq.id}_${opt.id}" value="false" class="d-none">Sai</label>
                    </div>
                </div>`;
            }).join('');
        } else if (qType === 'short_answer') {
            contentHtml = `<input type="text" class="form-control" id="sa_${qq.id}" placeholder="Nhập đáp án..." oninput="selectSA(${qq.id})"><div class="form-text small">Nhập chính xác kết quả (số, công thức, text...)</div>`;
        }

        const questionHtml = QuestionRenderer.renderStem(q);

        return `<div class="animate-in" id="qBlock_${qq.id}" style="background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-lg);overflow:hidden;" style="animation-delay:${idx*0.04}s">
            <div style="height:4px;background:linear-gradient(90deg,var(--color-primary),var(--color-secondary));"></div>
            <div style="padding:1.5rem;">
                <div class="d-flex align-items-center gap-2 mb-3">
                    <span style="background:var(--color-primary);color:#fff;border-radius:var(--radius-sm);padding:0.3rem 0.75rem;font-weight:700;font-size:0.875rem;">Câu ${idx+1}</span>
                    ${typeBadges[qType]||''}
                    <span style="font-size:0.75rem;color:var(--color-muted);">${qq.points} điểm</span>
                </div>
                ${q.question_text ? `<div class="fw-bold mb-3 text-primary" style="font-size:1.1rem;">${escapeHtml(q.question_text)}</div>` : ''}
                ${questionHtml}
                <div class="mt-4">${contentHtml}</div>
            </div>
        </div>`;
    }).join('');
}

function buildNavigator() {
    const nav = document.getElementById('questionNav');
    nav.innerHTML = quizQuestions.map((qq, i) => `<button class="quiz-nav-btn" id="nav_${qq.id}" onclick="document.getElementById('qBlock_${qq.id}').scrollIntoView({behavior:'smooth',block:'center'})">${i+1}</button>`).join('');
}

function selectMC(qqId, optId) {
    const block = document.getElementById(`qBlock_${qqId}`);
    block.querySelectorAll('.quiz-option').forEach(el => el.classList.remove('selected'));
    document.getElementById(`opt_wrap_${optId}`)?.classList.add('selected');
    const radio = document.getElementById(`opt_${optId}`);
    if (radio) radio.checked = true;
    currentAnswers[qqId] = {selected_option_id: optId};
    updateProgress();
    document.getElementById(`nav_${qqId}`)?.classList.add('answered');
}

function selectTF(qqId, optId, value) {
    if (!currentAnswers[qqId]) currentAnswers[qqId] = {true_false_answers:{}};
    if (!currentAnswers[qqId].true_false_answers) currentAnswers[qqId].true_false_answers = {};
    currentAnswers[qqId].true_false_answers[optId] = value;
    ['t','f'].forEach(k => {
        const btn = document.getElementById(`tf_${qqId}_${optId}_${k}`);
        if (btn) { btn.classList.remove('active','btn-success','btn-danger'); btn.classList.add(k==='t'?'btn-outline-success':'btn-outline-danger'); }
    });
    const activeBtn = document.getElementById(`tf_${qqId}_${optId}_${value?'t':'f'}`);
    if (activeBtn) { activeBtn.classList.remove('btn-outline-success','btn-outline-danger'); activeBtn.classList.add(value?'btn-success':'btn-danger','active'); }
    const allOptionsAnswered = true; // simplified
    updateProgress();
    if (Object.keys(currentAnswers[qqId]?.true_false_answers||{}).length > 0) document.getElementById(`nav_${qqId}`)?.classList.add('answered');
}

function selectSA(qqId) {
    const input = document.getElementById(`sa_${qqId}`);
    if (input?.value.trim()) { currentAnswers[qqId] = {answer_text: input.value.trim()}; document.getElementById(`nav_${qqId}`)?.classList.add('answered'); }
    else { delete currentAnswers[qqId]; document.getElementById(`nav_${qqId}`)?.classList.remove('answered'); }
    updateProgress();
}

function updateProgress() {
    const answered = Object.keys(currentAnswers).length, total = quizQuestions.length;
    document.getElementById('answeredCount').textContent = answered;
    document.getElementById('progressFill').style.width = (total > 0 ? answered/total*100 : 0) + '%';
}

function startTimer() {
    function update() {
        const diff = endTimeTime - Date.now();
        if (diff <= 0) { clearInterval(timerInterval); document.getElementById('timerDisplay').textContent = "00:00"; showGlobalAlert('Hết giờ! Tự động nộp bài.','warning'); submitExam(true); return; }
        const m = Math.floor(diff/60000), s = Math.floor((diff%60000)/1000);
        const display = document.getElementById('timerDisplay');
        display.textContent = `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
        if (m < 2) { display.style.color = 'var(--color-danger)'; display.parentElement.style.background = 'var(--color-danger-light)'; display.parentElement.style.animation = 'subtlePulse 1s infinite'; }
    }
    update(); timerInterval = setInterval(update, 1000);
}

function promptSubmit() {
    const answered = Object.keys(currentAnswers).length, total = quizQuestions.length;
    document.getElementById('submitWarnText').innerHTML = answered < total ?
        `Bạn mới trả lời <strong>${answered}/${total}</strong> câu. Các câu chưa làm sẽ bị 0 điểm. Vẫn nộp?` :
        `Bạn đã trả lời tất cả ${total} câu. Xác nhận nộp bài?`;
    new bootstrap.Modal(document.getElementById('submitConfirmModal')).show();
}

async function submitExam(isAuto=false) {
    const modal = bootstrap.Modal.getInstance(document.getElementById('submitConfirmModal'));
    if (modal) modal.hide();
    const sBtn = document.getElementById('submitExamBtn');
    if (sBtn) { sBtn.disabled = true; sBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang nộp...'; }
    if (timerInterval) clearInterval(timerInterval);
    const answersArr = [];
    for (const [qqIdStr, ansData] of Object.entries(currentAnswers)) {
        const qqId = parseInt(qqIdStr), qq = quizQuestions.find(q => q.id === qqId);
        if (!qq) continue;
        const qType = qq.question.question_type || 'multiple_choice';
        if (qType === 'multiple_choice') answersArr.push({quiz_question_id: qqId, selected_option_id: ansData.selected_option_id});
        else if (qType === 'true_false' && ansData.true_false_answers) {
            for (const [optIdStr] of Object.entries(ansData.true_false_answers)) answersArr.push({quiz_question_id: qqId, selected_option_id: parseInt(optIdStr)});
        } else if (qType === 'short_answer') answersArr.push({quiz_question_id: qqId, answer_text: ansData.answer_text});
    }
    try {
        const res = await fetch(`/api/exams/attempt/${attemptId}/submit/`, {method:'POST',headers:quizAuthHeaders(),body:JSON.stringify({answers:answersArr})});
        const data = await res.json();
        if (res.ok) showResult(data);
        else { alert(data.detail||'Lỗi nộp bài.'); if(sBtn){sBtn.disabled=false;sBtn.innerHTML='<i class="bi bi-send-check me-1"></i>Nộp bài';} }
    } catch(e) { alert('Lỗi mạng.'); if(sBtn){sBtn.disabled=false;sBtn.innerHTML='<i class="bi bi-send-check me-1"></i>Nộp bài';} }
}

function showResult(data) {
    ['introState','quizState','loadingState'].forEach(function(id) { document.getElementById(id).style.display='none'; });
    document.getElementById('resultState').style.display = 'block';
    document.getElementById('finalScore').textContent = parseFloat(data.score).toFixed(1);

    // Save data for AI Explanation
    window.quizResultData = { questions: data.questions, answers: data.answers };

    // Compute stats
    if (data.questions && data.answers) {
        var totalQ = data.questions.length;
        var correctCount = 0;
        var incorrectCount = 0;
        var unansweredCount = 0;

        data.questions.forEach(function(qq) {
            var studentAns = data.answers.filter(function(a) { return a.quiz_question === qq.id; });
            if (studentAns.length === 0) {
                unansweredCount++;
            } else {
                var qType = qq.question ? qq.question.question_type : '';
                if (qType === 'true_false') {
                    var allCorrect = studentAns.every(function(a) { return a.is_correct; });
                    if (allCorrect) correctCount++;
                    else incorrectCount++;
                } else {
                    var ans = studentAns[0];
                    if (ans && ans.is_correct) correctCount++;
                    else incorrectCount++;
                }
            }
        });

        var statCorrectEl = document.getElementById('statCorrect');
        var statIncorrectEl = document.getElementById('statIncorrect');
        var statUnansweredEl = document.getElementById('statUnanswered');
        if (statCorrectEl) statCorrectEl.textContent = correctCount;
        if (statIncorrectEl) statIncorrectEl.textContent = incorrectCount;
        if (statUnansweredEl) statUnansweredEl.textContent = unansweredCount;

        renderReview(data.questions, data.answers);
        document.getElementById('reviewWrapper').style.display = 'block';
        buildKnowledgeGaps(data.questions, data.answers);
    }
}

// ─── Knowledge Gap Analysis ───────────────────────────────────────────────────
function buildKnowledgeGaps(questions, answers) {
    var wrapper = document.getElementById('knowledgeGapsWrapper');
    var body = document.getElementById('knowledgeGapsBody');
    if (!wrapper || !body) return;

    // ── Collect wrong / unanswered questions ─────────────────────────────────
    var wrongItems = []; // { q, qq, isUnanswered }
    questions.forEach(function(qq) {
        var q = qq.question;
        var studentAns = answers.filter(function(a) { return a.quiz_question === qq.id; });
        var isUnanswered = (studentAns.length === 0);
        var isWrong = false;
        if (isUnanswered) {
            isWrong = true;
        } else if (q.question_type === 'true_false') {
            isWrong = !studentAns.every(function(a) { return a.is_correct; });
        } else {
            isWrong = !studentAns[0].is_correct;
        }
        if (isWrong) wrongItems.push({ q: q, qq: qq, isUnanswered: isUnanswered });
    });

    if (wrongItems.length === 0) {
        wrapper.style.display = 'block';
        body.innerHTML = '<div style="text-align:center;padding:1.5rem 0;color:var(--color-success);font-weight:700;font-size:1.05rem;"><i class="bi bi-trophy-fill me-2"></i>Xuất sắc! Bạn đã trả lời đúng tất cả câu hỏi. Không có kiến thức nào cần ôn thêm.</div>';
        return;
    }

    // ── Group by subject ──────────────────────────────────────────────────────
    var subjectMap = {}; // subjectName → { total, wrong, difficulties: {}, items: [] }
    wrongItems.forEach(function(item) {
        var subj = item.q.subject_name || 'Chung';
        var diff = item.q.difficulty || 'easy';
        var diffLabel = item.q.difficulty_display || diff;
        if (!subjectMap[subj]) subjectMap[subj] = { total: 0, wrong: 0, difficulties: {}, items: [] };

        // count total for this subject from all questions
        subjectMap[subj].wrong++;
        subjectMap[subj].items.push({ item: item, diffLabel: diffLabel, diff: diff });

        if (!subjectMap[subj].difficulties[diff]) subjectMap[subj].difficulties[diff] = { label: diffLabel, count: 0 };
        subjectMap[subj].difficulties[diff].count++;
    });

    // Count total per subject
    questions.forEach(function(qq) {
        var subj = (qq.question && qq.question.subject_name) ? qq.question.subject_name : 'Chung';
        if (subjectMap[subj]) subjectMap[subj].total++;
    });

    // ── Difficulty color map ─────────────────────────────────────────────────
    var diffColors = {
        'easy':   { bg: 'var(--color-success-light)', color: 'var(--color-success)', icon: 'bi-circle-fill' },
        'medium': { bg: 'var(--color-warning-light)', color: 'var(--color-warning)', icon: 'bi-triangle-fill' },
        'hard':   { bg: 'var(--color-danger-light)',  color: 'var(--color-danger)',  icon: 'bi-diamond-fill' }
    };

    // ── Build HTML ────────────────────────────────────────────────────────────
    var htmlParts = [];

    // Summary chips row
    htmlParts.push('<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1.25rem;">');
    Object.keys(subjectMap).forEach(function(subj) {
        var d = subjectMap[subj];
        var pct = d.total > 0 ? Math.round(d.wrong / d.total * 100) : 100;
        htmlParts.push(
            '<div style="display:inline-flex;align-items:center;gap:0.5rem;background:var(--color-danger-light);'
            + 'border:1px solid var(--color-danger);border-radius:20px;padding:0.35rem 0.875rem;font-size:0.82rem;font-weight:600;color:var(--color-danger);">'
            + '<i class="bi bi-book-fill" style="font-size:0.7rem;"></i>'
            + escapeHtml(subj)
            + ' &nbsp;<span style="background:var(--color-danger);color:#fff;border-radius:10px;padding:0.1rem 0.45rem;font-size:0.7rem;">'
            + d.wrong + ' câu sai</span></div>'
        );
    });
    htmlParts.push('</div>');

    // Per-subject detail
    Object.keys(subjectMap).forEach(function(subj) {
        var d = subjectMap[subj];
        htmlParts.push(
            '<div style="margin-bottom:1.25rem;border:1px solid var(--color-border);border-radius:var(--radius-lg);overflow:hidden;">'
            + '<div style="background:var(--color-bg);padding:0.875rem 1.25rem;border-bottom:1px solid var(--color-border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">'
            + '<div style="font-weight:700;font-size:0.95rem;"><i class="bi bi-journal-text me-2" style="color:var(--color-primary);"></i>' + escapeHtml(subj) + '</div>'
            + '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;">'
        );
        // Difficulty chips for this subject
        var diffOrder = ['easy', 'medium', 'hard'];
        diffOrder.forEach(function(dk) {
            if (d.difficulties[dk]) {
                var dc = diffColors[dk] || diffColors['easy'];
                htmlParts.push(
                    '<span style="background:' + dc.bg + ';color:' + dc.color + ';border:1px solid ' + dc.color
                    + ';border-radius:10px;padding:0.2rem 0.6rem;font-size:0.72rem;font-weight:700;">'
                    + '<i class="bi ' + dc.icon + '" style="font-size:0.55rem;vertical-align:middle;"></i> '
                    + d.difficulties[dk].label + ': ' + d.difficulties[dk].count + ' câu</span>'
                );
            }
        });
        htmlParts.push('</div></div>'); // end header

        // List specific question topics
        htmlParts.push('<div style="padding:0.875rem 1.25rem;display:flex;flex-direction:column;gap:0.5rem;">');
        d.items.forEach(function(entry) {
            var q = entry.item.q;
            var dc = diffColors[entry.item.q.difficulty] || diffColors['easy'];
            // Extract short topic snippet from the question text
            var rawText = '';
            if (q.content_json && Array.isArray(q.content_json)) {
                rawText = q.content_json.filter(function(b){return b.type==='text';}).map(function(b){return b.value||'';}).join(' ');
            }
            if (!rawText && q.text) rawText = q.text;
            if (!rawText && q.context) rawText = q.context;
            var snippet = rawText.trim().substring(0, 100);
            if (rawText.length > 100) snippet += '…';

            var statusIcon = entry.item.isUnanswered
                ? '<i class="bi bi-dash-circle-fill" style="color:var(--color-muted);"></i>'
                : '<i class="bi bi-x-circle-fill" style="color:var(--color-danger);"></i>';
            var statusLabel = entry.item.isUnanswered ? '<span style="color:var(--color-muted);font-size:0.7rem;font-weight:600;">(Bỏ trống)</span>' : '';

            htmlParts.push(
                '<div style="display:flex;align-items:flex-start;gap:0.65rem;padding:0.6rem 0.75rem;background:var(--color-bg);border-radius:var(--radius-md);border-left:3px solid ' + dc.color + ';font-size:0.82rem;">'
                + '<div style="flex-shrink:0;margin-top:2px;">' + statusIcon + '</div>'
                + '<div style="flex:1;min-width:0;">'
                + (snippet ? '<div style="color:var(--color-text);line-height:1.5;">' + escapeHtml(snippet) + '</div>' : '<div style="color:var(--color-muted);font-style:italic;">Câu hỏi có hình ảnh/công thức</div>')
                + '<div style="margin-top:0.25rem;display:flex;gap:0.4rem;flex-wrap:wrap;align-items:center;">'
                + '<span style="background:' + dc.bg + ';color:' + dc.color + ';border-radius:8px;padding:0.1rem 0.45rem;font-size:0.65rem;font-weight:700;">' + escapeHtml(entry.diffLabel) + '</span>'
                + statusLabel
                + '</div></div></div>'
            );
        });
        htmlParts.push('</div></div>'); // end body + card
    });

    // Call to action
    htmlParts.push(
        '<div style="margin-top:0.75rem;padding:0.875rem 1rem;background:linear-gradient(135deg,rgba(245,158,11,0.08),rgba(239,68,68,0.08));'
        + 'border:1px solid rgba(245,158,11,0.3);border-radius:var(--radius-md);font-size:0.82rem;">'
        + '<i class="bi bi-lightbulb-fill me-2" style="color:#f59e0b;"></i>'
        + '<strong>Gợi ý:</strong> Hãy xem lại phần giải thích cho các câu sai ở bên dưới, '
        + 'hoặc yêu cầu giáo viên tạo <em>bài phục thù</em> để ôn lại những chủ đề này.'
        + '</div>'
    );

    body.innerHTML = htmlParts.join('');
    wrapper.style.display = 'block';
}

function renderReview(questions, answers) {
    var container = document.getElementById('reviewContainer');
    questions.sort(function(a,b) { return a.order - b.order; });
    
    container.innerHTML = questions.map(function(qq, idx) {
        var q = qq.question;
        var qType = q.question_type;
        var studentAns = answers.filter(function(a) { return a.quiz_question === qq.id; });
        
        var reviewHtml = '';
        if (qType === 'multiple_choice') {
            var keys = ['A','B','C','D'];
            var selectedOptId = studentAns[0] ? studentAns[0].selected_option : null;
            var isSkipped = !selectedOptId;

            reviewHtml = q.options.map(function(opt, oi) {
                var isStudent = opt.id === selectedOptId;
                var isCorrect = opt.is_correct;
                var statusClass = '';
                var badge = '';
                if (isCorrect) {
                    statusClass = 'correct';
                    badge = '<span class="review-badge correct">Đáp án đúng</span>';
                } else if (isStudent && !isCorrect) {
                    statusClass = 'incorrect';
                    badge = '<span class="review-badge incorrect">Bạn chọn sai</span>';
                }
                var selClass = isStudent ? 'student-selected' : '';
                var optContent = QuestionRenderer.renderOption(opt, q.question_images);
                return '<div class="review-opt ' + statusClass + ' ' + selClass + '">'
                    + '<div class="quiz-option-key" style="width:24px;height:24px;font-size:0.75rem;">' + (keys[oi] || oi+1) + '</div>'
                    + '<div style="flex:1;">' + optContent + '</div>'
                    + badge
                    + '</div>';
            }).join('');
            
            if (isSkipped) {
                reviewHtml = '<div class="mb-2"><span class="text-muted small">(Bỏ trống)</span></div>' + reviewHtml;
            }

        } else if (qType === 'true_false') {
            reviewHtml = q.options.map(function(opt, i) {
                var ans = studentAns.find(function(a) { return a.selected_option === opt.id; });
                var isCorrect = ans ? ans.is_correct : false;
                var statusClass = ans ? (isCorrect ? 'correct' : 'incorrect') : '';
                var badge = '';
                if (ans) {
                    badge = isCorrect
                        ? '<i class="bi bi-check-circle-fill text-success"></i>'
                        : '<i class="bi bi-x-circle-fill text-danger"></i>';
                } else {
                    badge = '<span class="text-muted small">(Bỏ trống)</span>';
                }
                var correctLabel = opt.is_correct ? 'Đúng' : 'Sai';
                var optContent = QuestionRenderer.renderOption(opt, q.question_images);
                return '<div class="review-opt ' + statusClass + '" style="justify-content:space-between;">'
                    + '<div style="flex:1;">' + String.fromCharCode(97+i) + ') ' + optContent + '</div>'
                    + '<div class="d-flex align-items-center gap-2">'
                    + '<span class="small fw-bold">' + correctLabel + '</span>'
                    + badge
                    + '</div></div>';
            }).join('');

        } else if (qType === 'short_answer') {
            var ans = studentAns[0];
            var isCorrect = ans ? ans.is_correct : false;
            var bgClass = isCorrect ? 'bg-success-light text-success' : 'bg-danger-light text-danger';
            var ansText = ans ? escapeHtml(ans.answer_text) : '<span class="text-muted small">(Bỏ trống)</span>';
            var icon = isCorrect ? '<i class="bi bi-check-circle-fill"></i>' : '<i class="bi bi-x-circle-fill"></i>';
            var correctAns = escapeHtml(q.correct_answer_text || '');
            reviewHtml = '<div class="p-2 rounded ' + bgClass + '" style="border:1px solid;font-size:0.875rem;">'
                + '<div><strong>Bạn trả lời:</strong> ' + ansText + ' ' + icon + '</div>'
                + '<div class="mt-1"><strong>Đáp án đúng:</strong> ' + correctAns + '</div>'
                + '</div>';
        }

        var stemHtml = QuestionRenderer.renderStem(q);
        var explanationHtml = '';
        if (q.explanation) {
            explanationHtml = '<div class="mt-2 p-2 bg-light rounded small text-muted"><strong>Giải thích:</strong> ' + escapeHtml(q.explanation) + '</div>';
        }
        
        var isOverallCorrect = false;
        if (qType === 'multiple_choice' || qType === 'short_answer') {
            isOverallCorrect = studentAns[0] ? studentAns[0].is_correct : false;
        } else if (qType === 'true_false') {
            isOverallCorrect = studentAns.length === 4 && studentAns.every(function(a){return a.is_correct;});
        }
        
        var aiBtnHtml = '';
        if (!isOverallCorrect) {
            aiBtnHtml = '<div class="mt-2"><button id="btn_ai_explain_' + qq.id + '" class="btn btn-sm btn-outline-info" onclick="explainWithAI(' + qq.id + ')"><i class="bi bi-robot me-1"></i>AI Giải thích</button></div>'
                      + '<div id="ai_explain_' + qq.id + '" class="mt-2 text-wrap"></div>';
        }

        return '<div class="review-q-item">'
            + '<div class="d-flex align-items-center gap-2 mb-2">'
            + '<span class="badge bg-primary">Câu ' + (idx+1) + '</span>'
            + '<span class="small text-muted">' + qq.points + ' điểm</span>'
            + '</div>'
            + '<div class="mb-3" style="font-size:0.9rem;">' + stemHtml + '</div>'
            + '<div>' + reviewHtml + '</div>'
            + explanationHtml
            + aiBtnHtml
            + '</div>';
    }).join('');
}

window.explainWithAI = async function(qqId) {
    var btn = document.getElementById('btn_ai_explain_' + qqId);
    var box = document.getElementById('ai_explain_' + qqId);
    if (!btn || !box) return;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> AI đang suy nghĩ...';
    box.innerHTML = '';
    
    var qq = window.quizResultData.questions.find(function(q) { return q.id === qqId; });
    var q = qq.question;
    var studentAns = window.quizResultData.answers.filter(function(a) { return a.quiz_question === qqId; });
    
    var qText = q.question_text || '';
    if (q.context) qText += '\nNgữ cảnh: ' + q.context;
    
    var stemText = (q.content_json || []).filter(function(b) { return b.type==='text'; }).map(function(b) { return b.value; }).join(' ');
    qText += '\nCâu hỏi: ' + stemText;
    
    var correctText = '';
    var studentText = '';
    
    if (q.question_type === 'multiple_choice') {
        var keys = ['A','B','C','D'];
        q.options.forEach(function(opt, oi) {
            var optText = (opt.content_json || []).filter(function(b){return b.type==='text'}).map(function(b){return b.value}).join(' ');
            qText += '\n' + keys[oi] + '. ' + optText;
            if (opt.is_correct) correctText = keys[oi] + '. ' + optText;
            
            var isStudent = studentAns[0] && studentAns[0].selected_option === opt.id;
            if (isStudent) studentText = keys[oi] + '. ' + optText;
        });
        if (!studentText) studentText = '(Bỏ trống)';
    } else if (q.question_type === 'true_false') {
        q.options.forEach(function(opt, i) {
            var optText = (opt.content_json || []).filter(function(b){return b.type==='text'}).map(function(b){return b.value}).join(' ');
            qText += '\n' + String.fromCharCode(97+i) + ') ' + optText;
            correctText += String.fromCharCode(97+i) + ') ' + optText + ' -> ' + (opt.is_correct ? 'Đúng' : 'Sai') + '\n';
            
            var ans = studentAns.find(function(a){return a.selected_option === opt.id;});
            if (ans) {
                var studentChoseCorrect = (ans.is_correct === opt.is_correct) ? opt.is_correct : !opt.is_correct;
                studentText += String.fromCharCode(97+i) + ') ' + optText + ' -> ' + (studentChoseCorrect ? 'Đúng' : 'Sai') + '\n';
            } else {
                studentText += String.fromCharCode(97+i) + ') (Bỏ trống)\n';
            }
        });
    } else if (q.question_type === 'short_answer') {
        correctText = q.correct_answer_text || '';
        studentText = studentAns[0] ? studentAns[0].answer_text : '(Bỏ trống)';
    }

    try {
        var res = await fetch('/api/ai/explain-wrong-answer/', {
            method: 'POST',
            headers: quizAuthHeaders(),
            body: JSON.stringify({
                question_text: qText,
                correct_answer: correctText,
                student_answer: studentText
            })
        });
        var data = await res.json();
        if (res.ok) {
            var formattedInsight = escapeHtml(data.explanation) || "";
            formattedInsight = formattedInsight.replace(/\n/g, '<br>');
            formattedInsight = formattedInsight.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            
            box.innerHTML = '<div class="p-3 bg-info-subtle text-info-emphasis rounded mt-2" style="border-left: 4px solid var(--bs-info);"><h6 class="fw-bold mb-2"><i class="bi bi-robot me-1"></i>AI Giải thích:</h6><div class="small">' + formattedInsight + '</div></div>';
            btn.style.display = 'none';
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([box]).catch(function(err) { console.warn('MathJax error:', err); });
            }
        } else {
            box.innerHTML = '<div class="text-danger small mt-2">' + escapeHtml(data.error || 'Lỗi lấy giải thích từ AI') + '</div>';
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot me-1"></i>Thử lại';
        }
    } catch(e) {
        box.innerHTML = '<div class="text-danger small mt-2">Lỗi kết nối mạng.</div>';
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-robot me-1"></i>Thử lại';
    }
};

init();
