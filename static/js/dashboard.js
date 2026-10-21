function escapeHtml(value) {
    return (value ?? '').toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboardContent = document.getElementById('dashboardContent');
    if (!dashboardContent) return;

    if (!localStorage.getItem('auth_hint')) window.location.href = '/login/';
    
    function authH() { return { 'Content-Type': 'application/json' }; }
    
    async function initDashboard() {
        try {
            const user = await window.getCurrentUser(true);
            if (!user) {
                // Token không hợp lệ → cần đăng nhập lại
                localStorage.clear();
                window.location.href = '/login/';
                return;
            }

            const statsRes = await fetch('/api/accounts/stats/', { headers: authH() });

            if (statsRes.status === 401) {
                // Token hết hạn
                localStorage.clear();
                window.location.href = '/login/';
                return;
            }

            if (!statsRes.ok) {
                // Lỗi server (500, 403...) → hiển thị thông báo lỗi thay vì loop redirect
                console.error('Stats API lỗi:', statsRes.status);
                showDashboardError('Không thể tải dữ liệu từ máy chủ (lỗi ' + statsRes.status + '). Vui lòng thử tải lại trang.');
                return;
            }

            const data = await statsRes.json();
            renderDashboard(user, data);
        } catch (e) {
            console.error('initDashboard error:', e);
            showDashboardError('Đã xảy ra lỗi kết nối. Vui lòng kiểm tra mạng và tải lại trang.');
        }
    }

    function showDashboardError(msg) {
        const placeholder = document.getElementById('loadingPlaceholder');
        if (placeholder) {
            placeholder.innerHTML = `
                <div class="py-5 text-center">
                    <div style="font-size:3rem;">⚠️</div>
                    <p class="mt-3 text-danger fw-medium">${escapeHtml(msg)}</p>
                    <button class="btn btn-outline-primary btn-sm mt-2" onclick="window.location.reload()">
                        <i class="bi bi-arrow-clockwise me-1"></i>Tải lại trang
                    </button>
                </div>`;
        }
    }
    
    function renderDashboard(user, data) {
        document.getElementById('loadingPlaceholder').style.display = 'none';
        dashboardContent.style.display = 'block';
    
        // Greeting
        const h = new Date().getHours();
        const greet = h < 12 ? 'Chào buổi sáng' : h < 18 ? 'Chào buổi chiều' : 'Chào buổi tối';
        const fullName = [user.last_name, user.first_name].filter(Boolean).join(' ') || user.username;
        document.getElementById('greetingText').textContent = `${greet}, ${fullName}!`;
        document.getElementById('currentDateText').textContent = new Date().toLocaleDateString('vi-VN', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
    
        const roleLabels = { admin: 'Quản trị viên', teacher: 'Giáo viên', student: 'Học sinh' };
        document.getElementById('userRoleBadge').textContent = roleLabels[data.role] || data.role;
    
        const banner = document.getElementById('welcomeBanner');
        if (data.role === 'admin') banner.classList.add('bg-admin');
        else if (data.role === 'teacher') banner.classList.add('bg-teacher');
        else banner.classList.add('bg-student');
    
        renderKPIs(data.role, data.stats);
        renderActions(data.role);
        renderActivities(data.recent_activities);
        
        if (data.role === 'student') {
            document.getElementById('analyticsSection').style.display = 'block';
            loadStudentProgress();
        } else if (data.role === 'teacher' || data.role === 'admin') {
            document.getElementById('teacherAnalyticsSection').style.display = 'block';
            loadTeacherAdminProgress();
        }
    }
    
    function renderKPIs(role, stats) {
        const grid = document.getElementById('kpiGrid');
        grid.innerHTML = '';
    
        let configs = [];
        if (role === 'admin') {
            configs = [
                { label: 'Người dùng',  val: stats.total_users,    icon: 'bi-people',             color: 'primary' },
                { label: 'Giáo viên',   val: stats.total_teachers,  icon: 'bi-person-workspace',   color: 'info' },
                { label: 'Học sinh',    val: stats.total_students,  icon: 'bi-mortarboard',         color: 'success' },
                { label: 'Lớp học',     val: stats.total_classes,   icon: 'bi-door-open',           color: 'warning' },
            ];
        } else if (role === 'teacher') {
            configs = [
                { label: 'Lớp đang dạy',  val: stats.total_classes,  icon: 'bi-cast',          color: 'primary' },
                { label: 'Tổng học sinh', val: stats.total_students, icon: 'bi-mortarboard',    color: 'success' },
            ];
        } else {
            configs = [
                { label: 'Lớp tham gia', val: stats.joined_classes,     icon: 'bi-collection',  color: 'primary' },
                { label: 'Bài đã làm',   val: stats.completed_quizzes,  icon: 'bi-check2-all',  color: 'success' },
                { label: 'Điểm TB',      val: stats.avg_score,           icon: 'bi-star',        color: 'warning' },
            ];
        }
    
        const colClass = role === 'admin' ? 'col-12 col-sm-6 col-lg-3' : 'col-12 col-sm-6';
        configs.forEach((c, i) => {
            const col = document.createElement('div');
            col.className = colClass;
            col.innerHTML = `
                <div class="kpi-card ${c.color} animate-in" style="animation-delay:${i * 0.06}s">
                    <div class="kpi-icon ${c.color}"><i class="bi ${c.icon}"></i></div>
                    <div class="kpi-num">${c.val ?? '–'}</div>
                    <div class="kpi-label">${c.label}</div>
                </div>`;
            grid.appendChild(col);
        });
    }
    
    function renderActions(role) {
        const container = document.getElementById('quickActions');
        let items = [];
        if (role === 'admin') {
            items = [
                { label: 'Quản lý Người dùng', desc: 'Xem & phân quyền tài khoản',       icon: 'bi-people-fill',                href: '/admin-panel/', color: 'danger' },
                { label: 'Danh sách Lớp',       desc: 'Xem tất cả lớp trong hệ thống',   icon: 'bi-grid-fill',                  href: '/classes/',     color: 'primary' },
                { label: 'Báo cáo & Xuất Excel',desc: 'Xuất bảng điểm theo bộ lọc',      icon: 'bi-file-earmark-spreadsheet-fill', href: 'javascript:exportReport()', color: 'success' },
            ];
        } else if (role === 'teacher') {
            items = [
                { label: 'Lớp học của tôi',   desc: 'Quản lý và theo dõi lớp',      icon: 'bi-door-open-fill',   href: '/classes/',                color: 'primary' },
                { label: 'Báo cáo & Xuất Excel',desc: 'Xuất bảng điểm theo bộ lọc', icon: 'bi-file-earmark-spreadsheet-fill', href: 'javascript:exportReport()', color: 'success' },
                { label: 'Ngân hàng câu hỏi', desc: 'Quản lý kho đề thi',           icon: 'bi-bank2',            href: '/exams/question-bank/',    color: 'warning' },
            ];
        } else {
            items = [
                { label: 'Lớp của tôi',     desc: 'Xem bài thi & kết quả',    icon: 'bi-book-half',          href: '/classes/', color: 'primary' },
                { label: 'Tham gia lớp mới',desc: 'Nhập mã lớp để vào thi',   icon: 'bi-plus-circle-fill',   href: '/classes/', color: 'success' },
            ];
        }
    
        container.innerHTML = items.map((it, i) => `
            <div class="col-md-4">
                <a href="${it.href}" class="action-card animate-in" style="animation-delay:${0.25 + i*0.07}s;" onclick="${it.href.startsWith('javascript') ? 'event.preventDefault();' + it.href.replace('javascript:','') : ''}">
                    <div class="action-icon" style="background:var(--color-${it.color}-light,var(--color-primary-light));color:var(--color-${it.color},var(--color-primary));">
                        <i class="bi ${it.icon}"></i>
                    </div>
                    <div>
                        <div class="action-title">${it.label}</div>
                        <div class="action-desc">${it.desc}</div>
                    </div>
                </a>
            </div>`).join('');
    }
    
    function renderActivities(activities) {
        const feed = document.getElementById('activityFeed');
        if (!activities || !activities.length) {
            feed.innerHTML = '<div class="empty-state" style="padding:2rem;"><div class="empty-icon" style="font-size:2rem;">📭</div><div class="empty-title" style="font-size:0.875rem;">Chưa có hoạt động nào</div></div>';
            return;
        }
    
        const iconMap = { new_user: {icon:'bi-person-plus-fill', bg:'var(--color-info-light)', c:'var(--color-info)'}, quiz_submission:{icon:'bi-check-circle-fill', bg:'var(--color-success-light)', c:'var(--color-success)'}, quiz_result:{icon:'bi-award-fill', bg:'var(--color-warning-light)', c:'var(--color-warning)'} };
        feed.innerHTML = activities.map(act => {
            const im = iconMap[act.type] || {icon:'bi-circle-fill', bg:'var(--color-primary-light)', c:'var(--color-primary)'};
            const t = new Date(act.time);
            const timeStr = t.toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit'}) + ' · ' + t.toLocaleDateString('vi-VN');
            return `<div class="activity-item">
                <div class="activity-avatar" style="background:${im.bg};color:${im.c};"><i class="bi ${im.icon}"></i></div>
                <div class="activity-content">
                    <div class="activity-title">${escapeHtml(act.title)}</div>
                    <div class="activity-sub">${escapeHtml(act.detail)}</div>
                    <div class="activity-time">${timeStr}</div>
                </div>
            </div>`;
        }).join('');
    }

    async function loadStudentProgress() {
        try {
            const res = await fetch('/api/exams/student-progress/', { headers: authH() });
            if (!res.ok) return;
            const data = await res.json();
            
            // Render Graph
            const ctx = document.getElementById('progressChart').getContext('2d');
            
            if (!data.timeline || data.timeline.length === 0) {
                // Return empty state chart or leave it empty with a message
                return;
            }

            const labels = data.timeline.map(t => new Date(t.date).toLocaleDateString('vi-VN'));
            const scores = data.timeline.map(t => t.score);
            const titles = data.timeline.map(t => t.quiz_title);

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Điểm số',
                        data: scores,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#0d6efd',
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (tooltipItems) => {
                                    return titles[tooltipItems[0].dataIndex];
                                },
                                label: (context) => {
                                    return 'Điểm: ' + context.parsed.y;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 10,
                            grid: { borderDash: [5, 5] }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });

            // Render Weaknesses
            const weaknessList = document.getElementById('weaknessList');
            const aiActions = document.getElementById('aiLearningActions');
            if (data.weaknesses && data.weaknesses.length > 0) {
                weaknessList.innerHTML = data.weaknesses.map(w => {
                    const isDecline = w.startsWith('Điểm sụt mạnh');
                    return `<li class="list-group-item d-flex align-items-start gap-2 py-2 border-0 border-bottom ${isDecline ? 'bg-danger-subtle' : ''}">
                        <i class="bi ${isDecline ? 'bi-graph-down-arrow text-danger fs-5' : 'bi-x-circle text-warning'} flex-shrink-0 mt-1"></i>
                        <span class="${isDecline ? 'text-danger fw-semibold' : ''}">${escapeHtml(w)}</span>
                    </li>`;
                }).join('');
                aiActions.style.display = 'block'; // Show AI actions if there are weaknesses
            } else if (data.total_completed > 0) {
                weaknessList.innerHTML = '<li class="list-group-item text-success text-center py-4 border-0"><i class="bi bi-check-circle-fill me-2"></i>Phong độ tuyệt vời! Không phát hiện lỗ hổng kiến thức nghiêm trọng.</li>';
            }

            // Hiển thị xu hướng điểm (score_trend) nếu có
            const trendEl = document.getElementById('scoreTrendBadge');
            if (trendEl && data.score_trend) {
                const trendMap = {
                    up:     { icon: 'bi-arrow-up-circle-fill', text: 'Đang tiến bộ', cls: 'text-success' },
                    down:   { icon: 'bi-arrow-down-circle-fill', text: 'Có dấu hiệu sụt giảm', cls: 'text-danger' },
                    stable: { icon: 'bi-dash-circle-fill', text: 'Ổn định', cls: 'text-secondary' },
                };
                const t = trendMap[data.score_trend];
                if (t) {
                    trendEl.innerHTML = `<i class="bi ${t.icon} me-1"></i><span>${t.text}</span>`;
                    trendEl.className = `fw-medium small ${t.cls}`;
                }
            }

        } catch (e) {
            console.error('Lỗi khi tải biểu đồ', e);
        }
    }

    async function loadTeacherAdminProgress() {
        try {
            const messageEl = document.getElementById('teacherProgressMessage');
            messageEl.textContent = 'Đang tải dữ liệu...';

            const res = await fetch('/api/exams/teacher-progress/', { headers: authH() });
            if (!res.ok) {
                messageEl.textContent = 'Không thể tải dữ liệu hoặc không có quyền.';
                return;
            }

            const data = await res.json();
            if (!data.quizzes || !data.quizzes.length) {
                messageEl.textContent = 'Chưa có dữ liệu điểm bài thi hoàn thành.';
                return;
            }

            const labels = data.quizzes.map(q => `${q.class_name || 'Lớp'} - ${q.quiz_title}`);
            const avgScores = data.quizzes.map(q => parseFloat(q.average_score));
            const attemptCounts = data.quizzes.map(q => q.total_attempts);

            const ctx = document.getElementById('teacherProgressChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Điểm trung bình',
                        data: avgScores,
                        backgroundColor: 'rgba(13, 110, 253, 0.6)',
                        borderColor: 'rgba(13, 110, 253, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: items => items[0] ? items[0].label : '',
                                label: ctxInfo => `Điểm TB: ${ctxInfo.parsed.y || 0} - ${attemptCounts[ctxInfo.dataIndex]} lượt`,
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 10,
                            ticks: {stepSize: 1},
                            grid: { borderDash: [5,5] }
                        },
                        x: {
                            ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 },
                            grid: { display: false }
                        }
                    }
                }
            });

            messageEl.style.display = 'none';
        } catch (e) {
            console.error('Lỗi khi tải dữ liệu giáo viên/admin', e);
            const messageEl = document.getElementById('teacherProgressMessage');
            if (messageEl) {
                messageEl.textContent = 'Lỗi khi tải dữ liệu. Vui lòng thử lại sau.';
            }
        }
    }

    // Global AI functions for inline onClick
    window.getPersonalizedPath = async function() {
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('aiPathModal'));
        modal.show();
        
        const body = document.getElementById('aiPathModalBody');
        body.innerHTML = '<div class="text-center py-4"><div class="spinner-grow text-primary" role="status"></div><p class="mt-3 text-muted">AI đang phân tích dữ liệu lịch sử của bạn...</p></div>';
        
        try {
            const res = await fetch('/api/ai/path/', { headers: authH() });
            const data = await res.json();
            if(!res.ok) throw new Error(data.error || 'Lỗi hệ thống');
            
            let rawInsight = data.insight || "";
            // Unescape newline if server sent literal string \\n
            if (rawInsight.includes('\\n')) {
                rawInsight = rawInsight.replace(/\\n/g, '\n');
            }

            const safeInsight = escapeHtml(rawInsight);
            let formattedInsight = safeInsight;
            if (typeof marked !== 'undefined') {
                formattedInsight = marked.parse(safeInsight);
            } else {
                // Fallback basic parse if marked is missing
                formattedInsight = safeInsight
                    .replace(/\n/g, '<br>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/### (.*?)(?:<br>|\n|$)/g, '<h5>$1</h5>');
            }
            if (window.sanitizeMarkdownHtml) {
                formattedInsight = window.sanitizeMarkdownHtml(formattedInsight);
            }

            body.innerHTML = `<div class="p-3 ai-markdown-content" style="line-height: 1.6;">${formattedInsight}</div>`;
            if (window.MathJax && window.MathJax.typesetPromise) {
                window.MathJax.typesetPromise([body]).catch(err => console.warn('MathJax error:', err));
            }
        } catch (e) {
            body.innerHTML = `<div class="alert alert-danger m-3"><i class="bi bi-exclamation-triangle-fill me-2"></i> ${escapeHtml(e.message)}</div>`;
        }
    };

    window.generateQuickTest = async function() {
        if(!confirm('Hệ thống sẽ tạo tự động một bài kiểm tra ngắn gồm các câu hỏi bạn từng làm sai. Bạn đã sẵn sàng làm bài ngay chưa?')) return;
        
        try {
            // Show overlay loader if any
            const res = await fetch('/api/ai/quick-test/', { 
                method: 'POST',
                headers: authH()
            });
            const data = await res.json();
            if(!res.ok) throw new Error(data.error || 'Thất bại');
            
            alert(data.message);
            window.location.href = `/exams/taker/${data.quiz_id}/`;
        } catch (e) {
            alert('Lỗi: ' + e.message);
        }
    };

    initDashboard();
});
