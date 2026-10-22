# Kế hoạch unit, API integration và E2E từ Clean up project

Trạng thái: chờ người dùng duyệt, chưa triển khai hoặc chạy test. Ngày lập: 22/10/2026.

## 1. Phạm vi và cơ sở

- Bao gồm commit `fc5d896` (Clean up project) và mọi thay đổi đến `7c7950a` (HEAD lúc khảo sát). So sánh `fc5d896^..7c7950a`, gồm 21 commit và 80 đường dẫn thay đổi.
- Đã đọc README, tài liệu API câu hỏi/ảnh, hướng dẫn tạo câu hỏi, lịch sử thay đổi, test hiện có và các phần code liên quan.
- Kiểm tra tất cả nhóm chức năng bị ảnh hưởng và luồng LMS liên quan. File chỉ bị xóa/di chuyển hoặc tài liệu được kiểm tra qua migration, import, route và smoke tương ứng, không tạo test máy móc cho từng file.
- Luồng nộp bài hiện là JSON cho trắc nghiệm, Đúng/Sai và trả lời ngắn. Upload file hiện phục vụ tài liệu lớp, nhập đề và ảnh câu hỏi; chưa thấy chức năng học sinh nộp bài tự luận bằng tệp. Không thêm chức năng đó trong phạm vi này.
- Test có sẵn chủ yếu dùng Django/DRF TestCase, APITestCase và mock AI; chưa thấy cấu hình browser E2E trong repository.

## 2. Cách tổ chức và môi trường

- Unit: logic thuần về chấm điểm, chuẩn hóa, parser, AI response, URL và chữ ký upload. Tái sử dụng framework hiện có.
- API/DB integration: xác thực, phân quyền, serializer, transaction, constraint, signal, migration và command; chạy PostgreSQL có pgvector trong DB test riêng.
- Browser E2E: đề xuất Playwright với Chromium trước; backend và DB thật. Chỉ giả lập biên Cloudinary/AI để kết quả ổn định, không giả lập API nội bộ của LMS trong các luồng thành công.
- Ca race dùng TransactionTestCase, kết nối DB riêng và đồng bộ request; không dùng SQLite để kết luận về khóa hàng.
- Dữ liệu: admin, hai giáo viên, học sinh trong/ngoài lớp, hai lớp; bài nháp/công khai/hẹn giờ/quá hạn/giao riêng; đủ ba loại câu hỏi, câu có ảnh, kết quả biết trước.
- File fixture nhỏ: DOCX có bảng/ảnh/công thức, PDF có text, TXT theo khả năng parser; file rỗng/hỏng/sai đuôi, tên tiếng Việt. Kiểm tra file scan không có text theo hành vi hỗ trợ thực tế.
- Kiểm tra biên kích thước với file ngay dưới/đúng/trên 25 MiB, batch 10/11 file; dùng dữ liệu sinh hoặc fake stream cho ca lớn, không commit binary lớn.
- Cố định thời gian để kiểm tra publish_at, due_date và thời lượng; E2E không chờ hết bài thi thật.
- Thêm smoke riêng trên staging cho upload Cloudinary thật và AI thật với fixture nhỏ; tài nguyên có tiền tố test và được dọn. Các ca mock không chứng minh tích hợp dịch vụ thật hay giới hạn serverless.

## 3. Ma trận kiểm thử

| ID / ưu tiên | Chức năng và đường dẫn chính | Unit / API / DB cần kiểm tra | Browser E2E cần kiểm tra |
|---|---|---|---|
| SUB / P0 | Nộp bài: exams/models.py, views.py, serializers.py; static/js/quiz_taker.js | Đúng/sai/bỏ trống cho 3 loại; điểm trọng số và thang 10; ID câu/option ngoài đề; payload sai kiểu, trùng đáp án, >500 đáp án; rollback khi lưu lỗi; không đọc/nộp attempt người khác; không lộ đáp án trước nộp | Làm bài hỗn hợp, đổi đáp án, bỏ trống, xác nhận nộp, xem review và tải lại; so điểm và đáp án với dữ liệu kỳ vọng |
| TIME / P0 | Start/submit và bộ đếm giờ | Nháp, chưa đến giờ, đúng biên giờ mở/hạn nộp; thời lượng có khoảng đệm 60 giây hiện tại; request sát biên; gọi start lại không reset giờ; start/nộp đồng thời; nộp lại không sửa điểm | Hai tab; tự nộp hết giờ; nộp tay trùng tự nộp; lỗi mạng trước lưu và mất response sau khi đã lưu; refresh auth trong lúc nộp; không báo thành công giả |
| DOC / P0 | Tài liệu lớp: ai_core/views.py, services; static/js/class_detail.js | Multipart và URL; quyền chủ lớp/admin; missing/empty/corrupt/oversize; download timeout/HTTP lỗi/redirect; ingest/chunk/embedding lỗi; rollback DB/chunks và dọn file tạm/Cloudinary đúng asset, không xóa asset không thuộc tác vụ | Lấy signature → upload → đăng ký URL → xử lý → thấy tài liệu → đọc dùng RAG → xóa; lỗi ở từng chặng, thử lại và trạng thái loading phục hồi |
| IMP / P0 | Nhập đề: AIExtractFromFileView, AIBulkSaveQuestionsView; ai_generator.js | DOCX/PDF và kiểu thực sự hỗ trợ; batch giới hạn, một file lỗi giữa batch; JSON AI rỗng/sai/cắt cụt; giữ options, context, giải thích và ảnh; lưu bulk vào bank/quiz nhất quán; rollback, cleanup khi thất bại | Chọn nhiều file → preview → sửa/bỏ câu → lưu ngân hàng hoặc đề → học sinh làm bài; thất bại giữa batch không hiện thành công hoặc lưu trùng âm thầm |
| IMG / P0 | cloudinary_service.py; exams upload/link/update-full; question_editor.js, question_renderer.js | Signature không lộ secret; URL HTTPS/host/DNS public, chặn nội bộ và redirect; public_id theo resource_type/folder; SHA dedupe; quyền sửa/link/unlink; invalid payload rollback toàn bộ; xóa relation không làm hỏng ảnh dùng chung | Tạo/sửa câu có ảnh ở stem/option → lưu → tải lại → đưa vào đề; upload lỗi, save lỗi sau upload; gỡ ảnh ở một câu không phá câu khác |
| AUTH / P0 | accounts authentication/views/serializers; base.js, auth.js | Login username/email, cookie flags/path, Bearer fallback; refresh/rotation/blacklist; logout; role escalation; dữ liệu đầu vào; CSRF/cross-origin với xác thực cookie; password cũ/mới và phiên sau đổi mật khẩu | Đăng ký → login → trang theo role; access hết hạn và nhiều API cùng 401; refresh hết hạn; logout → back/URL trực tiếp; không lưu token vào localStorage |
| QB / P1 | Ngân hàng/quiz: exams views/serializers; question_bank.js, quiz_builder.js | CRUD full, content_json/text, context/topic; filter/search/pagination; needs_review với Đúng/Sai toàn Sai/toàn Đúng; option đúng của MC; bulk delete phân quyền; thêm câu trùng, order, rebalance khi thêm/xóa, duration và lịch không hợp lệ | Tạo đủ 3 loại → lọc/sửa → ghép/sắp đề → công bố; reload còn dữ liệu; lỗi validation có thông báo; không lộ đáp án qua payload public |
| CLS / P1 | classes models/views/serializers; classes.js, class_detail.js | CRUD/chủ lớp/admin; tham gia bằng mã, join lại và join đồng thời; thêm/xóa học sinh; dữ liệu lớp khác; thống kê nhánh prefetch/fallback phải bằng nhau | Giáo viên tạo lớp → học sinh tham gia → nhận đề; người ngoài lớp bị chặn; xóa học sinh và kiểm tra quyền truy cập tiếp theo |
| AI / P1 | ai_provider/openai_client/ai_generator/docx_parser; ai_core views; ai_generator.js | Giữ test hiện có cho model params, JSON legacy/wrapped và 16 mẫu nhãn Đúng/Sai; thêm parser DOCX an toàn; chọn đúng document/class; RAG có/thiếu/không liên quan source; fallback, NoQuestionsGenerated/422; refusal/timeout/missing key; không lưu câu rỗng; kiểm tra cấu trúc prompt có ý nghĩa | Tạo từ tài liệu và yêu cầu cần đạt → draft → sửa → lưu → làm bài; lỗi AI hiện rõ và phục hồi; chatbot, insight/cooldown, lộ trình, quick-test/phục thù và giải thích câu sai đúng phạm vi người dùng |
| PROF / P1 | accounts profile/password; profile.js/template | Email trùng không phân biệt hoa thường, validation password; chỉ sửa hồ sơ mình; trường role bị chặn; mật khẩu hiện tại sai và mật khẩu yếu | Sửa hồ sơ → reload; đổi mật khẩu → kiểm tra login/phiên theo chính sách; lỗi form không mất dữ liệu hợp lệ |
| NOTI / P1 | notifications models/signals/views/commands; notifications.js | Publish ngay/hẹn giờ; join lớp sau publish; resave/cron chạy lặp không trùng; bài giao riêng đúng người; unpublish/delete cleanup; phân trang/count/read; cron thiếu/sai secret; giữ trạng thái đã đọc khi dedupe | Nhận thông báo → mở đúng đề → đánh dấu đọc/mọi thông báo → badge đúng sau reload; người khác không đọc/sửa được |
| REP / P1 | Analytics/progress, admin reports/export; dashboard.js/admin_panel.js | Chỉ attempt completed; điểm 0/NULL, lớp chưa có bài; phạm vi GV/HS/admin; thống kê nhất quán sau nộp; XLSX đúng nội dung và quyền | Sau nộp, HS thấy tiến độ và GV thấy thống kê tương ứng; admin lọc/xuất báo cáo; không hiện dữ liệu lớp khác |
| OPS / P1 | exams migrations 0014–0016; notifications 0002; management commands; settings/build/routes | Migrate DB mới và DB cũ có duplicate; kiểm tra dữ liệu còn lại, câu trả lời liên quan và read flag, không chỉ migrate thành công; command migrate_local_images skip URL, missing file/upload lỗi không ghi đè dữ liệu, chạy lại an toàn; cache locmem/db và cấu hình thiếu | Smoke login/profile/classes/quiz/static sau build; staging upload trực tiếp file lớn hơn ngưỡng payload serverless; cron route; DEBUG=False và cookie Secure qua HTTPS |
| SAFE / P0/P1 | Nội dung động ở base/question_renderer và các trang thay đổi | Input không tin cậy ở text/HTML/Markdown/link/ảnh; dữ liệu UUID/ID lỗi không gây 500; permission matrix áp dụng cả list/detail/mutation | Payload XSS trong câu hỏi, tên lớp, tài liệu, thông báo, AI response không chạy script; thao tác chính dùng bàn phím được; lỗi không khóa nút/loading |

P0: nguy cơ mất bài, sai điểm, lộ dữ liệu hoặc hỏng upload. P1: phần thay đổi còn lại và tính nhất quán luồng LMS.

## 4. Các ca cần làm trước

1. SUB-01: đề hỗn hợp, đáp án đã biết; assert response, DB, review và thống kê cùng một kết quả.
2. SUB-02: Đúng/Sai với cùng một nhận định nhưng đổi lựa chọn Đúng ↔ Sai phải đổi kết quả đúng/sai; bao phủ đủ 16 mẫu đáp án của bốn nhận định, có cả toàn Sai. Không dùng chính hàm chấm điểm để tính expected.
3. SUB-03: trả lời ngắn có khoảng trắng/hoa thường, dấu phẩy thập phân, phân số tương đương, đáp án sai/rỗng và chuỗi quá dài; kiểm tra giới hạn lưu không làm điểm sai.
4. SUB-04: duplicate option/câu, option của câu khác, ID không hợp lệ không làm tăng điểm hoặc ghi câu trả lời ngoài đề; điểm luôn trong [0,10], đề tổng điểm 0 không chia cho 0.
5. SUB-05: hai request submit cùng lúc chỉ ghi một kết quả; lỗi DB giữa chừng không để attempt hoàn tất một phần. Start ở hai tab không sinh lượt trùng.
6. SUB-06: trước/đúng/sau hạn, thời lượng và khoảng đệm; retry sau timeout phân biệt chưa lưu với đã lưu; không tự gia hạn giờ khi tải lại.
7. DOC-01: Cloudinary → URL → ingestion → chunks → hiển thị; kiểm tra không còn DB/chunks/file tạm khi ingestion lỗi, và cleanup Cloudinary gọi đúng ID/resource_type.
8. DOC-02: URL không được phép, stream vượt giới hạn, HTTP/redirect/timeout; kiểm tra dọn file tạm cả khi tải chưa xong.
9. IMP-01: batch có file thành công trước file lỗi; kiểm tra kết quả, DB và asset theo chính sách all-or-nothing hay partial đã xác nhận, không mặc định đoán.
10. IMG-01: một ảnh dùng ở hai câu; gỡ/xóa/sửa một câu không phá ảnh còn lại; request save thất bại không làm mất dữ liệu cũ.
11. AUTH-01: token hết hạn ngay lúc nộp/upload; refresh chỉ thử hữu hạn, body được gửi lại đúng và không tạo dữ liệu trùng.
12. LMS-01: GV tạo lớp/câu/đề → công bố → HS join/nhận thông báo/làm/nộp → GV xem thống kê → HS xem tiến độ và bài luyện riêng.

## 5. Những điều cần xác nhận bằng test và nghiệp vụ

- Frontend Đúng/Sai lưu boolean ở currentAnswers nhưng submit chỉ gửi option ID; StudentAnswer chưa có field lưu lựa chọn boolean, is_correct hiện đọc nhãn của option. Đây là nghi vấn sai điểm quan trọng từ code, chưa phải kết quả test thực thi.
- QuizStart dùng get_or_create nhưng QuizAttempt chưa có unique constraint theo quiz/student: cần tái hiện race, không giả định đã chống trùng.
- Đáp án hiện ở bộ nhớ trang, chưa thấy cơ chế lưu nháp. Test reload/mất mạng phải ghi nhận hành vi hiện tại; mong muốn khôi phục đáp án cần chốt nếu phát hiện mất dữ liệu, không tự thêm autosave.
- Cần chốt chính sách nếu GV sửa/xóa câu đã có người nộp, thu hồi đề hoặc loại HS đang thi; giữ lịch sử/điểm là invariant mong muốn, không sửa test để hợp thức hóa mất dữ liệu.
- Cách tính điểm Đúng/Sai hiện chia theo số nhận định. Mặc định kiểm tra mô hình LMS này; nếu muốn biểu điểm THPT cần xác nhận riêng.
- Một học sinh/đề được API xử lý như một lượt; không tự thêm retake. Cần chốt cách xử lý dữ liệu legacy nhiều lượt nếu test phát hiện.

## 6. Trình tự sau khi duyệt

1. Chạy suite hiện có trên DB test riêng, lưu baseline, phân loại lỗi cũ/môi trường/fixture. Tạo bảng mapping mỗi nhóm thay đổi → test hiện có → test thiếu.
2. Bổ sung unit/API/transaction cho SUB, TIME, DOC, IMP, IMG và AUTH trước; test tái hiện lỗi giữ trạng thái fail cho đến khi có bản sửa phù hợp.
3. Dựng E2E tối thiểu cùng fixture/seed/cleanup và thực hiện các ca P0 xuyên suốt trình duyệt → server → DB.
4. Hoàn tất P1 cho classes, ngân hàng/đề, AI, profile, notifications, reports, migrations/commands và cấu hình build; smoke các màn hình bị ảnh hưởng.
5. Chạy regression toàn suite, kiểm tra tính ổn định của ca race/E2E đã thêm; smoke dịch vụ thật trên staging khi có môi trường; bàn giao báo cáo.

Không tự sửa production logic, đổi schema hay deploy trong bước lập plan. Khi triển khai test, lỗi tái hiện được sẽ có case, expected/actual và bằng chứng để xem xét bản sửa.

## 7. Tiêu chí hoàn tất và sản phẩm bàn giao

- Tất cả nhóm chức năng thay đổi được gắn test ID hoặc lý do không áp dụng; tái sử dụng test cũ, không đếm lại là coverage mới.
- P0 và P1 trong phạm vi đều pass; không còn lỗi gây mất bài/sai điểm/truy cập trái phép; không skip hoặc nới expected để làm xanh suite. Nếu còn fail/blocked phải báo rõ, chưa coi hoàn tất kiểm thử.
- E2E happy path dùng API/DB thật; số liệu expected được tính độc lập; có assert dữ liệu sau reload, không chỉ HTTP 200 hoặc toast.
- Các ca biên/race có bằng chứng DB; E2E lỗi có trace/screenshot và log đã che thông tin nhạy cảm.
- Có lệnh chạy unit/API/E2E, fixture tái lập được và môi trường tách biệt; không dùng tài khoản/dữ liệu production.
- Báo cáo cuối: phạm vi commit, case pass/fail/blocked, lỗi và cách tái hiện, test chưa chạy, dịch vụ thật đã/chưa kiểm tra, rủi ro còn lại.
- Không đặt mục tiêu phần trăm coverage hoặc số lượng case tùy ý. Ưu tiên đủ invariant và nhánh lỗi trong ma trận.

Ngoài phạm vi đợt này: load/stress quy mô lớn, toàn bộ browser/device, đánh giá sư phạm mọi câu AI, tính năng LMS mới. Chromium là browser automation đầu tiên; smoke thật vẫn cần để kết luận về Cloudinary/AI và môi trường serverless.
