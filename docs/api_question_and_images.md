# Tổng hợp API Question + Images + AI (Pipeline Mới)

Tài liệu này tổng hợp các API liên quan đến ngân hàng câu hỏi và quản lý hình ảnh, được thiết kế lại (Refactored) để tối ưu với kiến trúc Serverless trên Vercel, giảm thiểu số lượng Request (Round-trips) và giới hạn Payload 4.5MB.

## 1. Kiến trúc Request-Response Mới (Bulk / Single-Shot) ⚡

Thay vì quá trình tạo câu hỏi bị phân mảnh thành nhiều API calls (Tạo câu hỏi -> Upload ảnh 1 -> Upload ảnh 2 -> Link ảnh), hệ thống giờ đây ưu tiên mô hình **Client-Side Upload & Single-Shot Save**:
1. **Frontend tải ảnh trực tiếp lên Cloudinary** (bỏ qua Vercel) để nhận URL và tính SHA-256 nội bộ.
2. **Frontend gom đúc toàn bộ dữ liệu** (Câu hỏi + Các đáp án + Danh sách ảnh đã có URL Cloudinary) thành một cục JSON duy nhất.
3. **Frontend gọi 1 API POST duy nhất** tới Vercel. Backend sẽ tự động Transaction: lưu Question, lưu Options, và lưu/link QuestionImages vào ImageBank trong 1 lần chạy.

---

## 2. Question Bank APIs (Cập nhật)

### GET `/api/exams/questions/`
- **Mục đích:** Lấy danh sách câu hỏi (có filter và pagination).
- **Quyền:** Teacher/Admin.
- **Query params:** `subject`, `difficulty`, `question_type`, `search`
- **Response:** Danh sách câu hỏi kèm theo options và mảng `question_images`.

### POST `/api/exams/questions/` (Tạo Câu Hỏi Toàn Diện)
- **Mục đích:** Tạo câu hỏi mới kèm theo TẤT CẢ options và images trong một request duy nhất.
- **Quyền:** Teacher/Admin.
- **Body JSON:**
```json
{
  "subject": 1,
  "difficulty": "medium", 
  "question_type": "multiple_choice",
  "text": "Nội dung câu hỏi ở đây...",
  "context": "Context nếu có...",
  "correct_answer_text": "",
  "options": [
    {"text": "Đáp án A", "is_correct": true},
    {"text": "Đáp án B", "is_correct": false}
  ],
  "question_images": [
    {
      "sha256": "hex_sha256...",
      "url": "https://res.cloudinary.com/...", // Đã tự upload ở Frontend
      "placement": "stem",
      "position": 0,
      "source_type": "user_upload",
      "width_pt": 150, // Tuỳ chọn
      "height_pt": 50 // Tuỳ chọn
    }
  ]
}
```

### PUT `/api/exams/questions/{id}/update-full/`
- **Mục đích:** Cập nhật toàn diện câu hỏi (thay thế/sửa options, thêm bớt ảnh).
- **Quyền:** Teacher/Admin.
- Cách hoạt động tương tự như POST, backend sẽ xoá/update các relation JSON mảng phụ để đồng bộ khớp với payload truyền lên.

### DELETE `/api/exams/questions/{id}/`
- **Mục đích:** Xóa 1 câu hỏi cụ thể cùng các mảng phụ (ảnh và options). `ImageBank` gốc không xoá (để tái sử dụng).
- **Quyền:** Teacher/Admin.

### POST `/api/exams/questions/bulk-delete/`
- **Mục đích:** Xóa nhiều câu hỏi.

---

## 3. Question Image APIs (Chỉ dùng khi cần thiết)

Do đã gộp vào Payload chính của Question, các API rời rạc này chỉ nên dùng cho các tác vụ thay đổi siêu nhỏ (Ví dụ: Thầy cô chỉ muốn xoá một cái ảnh khỏi câu hỏi mà không muốn save lại toàn bộ form).

### POST `/api/exams/questions/images/upload/` (Deprecated/Ít dùng)
- **Mục đích cũ:** Upload file qua Vercel. 
- Vercel giới hạn 4.5MB nên API này rất dễ chết nếu file lớn. Khuyến khích đổi sang tự ném file file lên Cloudinary bằng JS frontend, rồi dùng Endpoint Update-Full.

### DELETE `/api/exams/questions/{id}/images/{qimg_id}/`
- **Mục đích:** Gỡ liên kết 1 ảnh cụ thể khỏi câu hỏi. Nhanh và tiện lợi khi edit trên form.

---

## 4. AI APIs (Tối ưu Serverless)

### POST `/api/ai/generate/extract-file/`
- **Mục đích:** Trích xuất câu hỏi từ file.
- **Cơ chế mới:** 
  - File DOCX/PDF lớn -> Frontend tự upload file này ẩn lên Cloudinary.
  - Frontend truyền JSON `{"file_url": "https://res.cloudinary..."}` cho API này.
  - Vercel tải từ Cloudinary rớt xuống `/tmp` (Bypass 4.5MB), phân giải bằng `gemini-1.5-flash` Single-Shot 8192 output tokens.
  - Trả về JSON Draft Array.

### POST `/api/ai/generate/from-rag/`
- **Mục đích:** Sinh câu hỏi ưu tiên RAG (Thư viện tri thức). Khi tài liệu rỗng, không liên quan hoặc chưa đủ thông tin, AI được bổ sung kiến thức nền đúng môn/chủ đề và trình độ THPT.
- **Bối cảnh:** AI được tự xây dựng tình huống ngoài RAG từ kiến thức nền, kể cả khi RAG đủ thông tin. Bối cảnh có thể thuộc nhiều lĩnh vực đời sống, nhưng kiến thức cần kiểm tra vẫn đúng chủ đề/YCCĐ và không đòi thêm chuyên môn ngoài bài; dữ kiện giả định được ghi rõ, không gán cho tài liệu.
- **Chất lượng:** Câu dẫn ngắn, phương án nhiễu từ hiểu sai hợp lí; Đúng/Sai có đúng 4 ý gắn với bối cảnh. Số lượng, loại câu và độ khó vẫn theo request, không cố định theo tài liệu hướng dẫn mẫu.
- **Lời giải:** Trường `explanation` gồm căn cứ đáp án và tên tài liệu sử dụng; phần ngoài RAG được ghi rõ “Kiến thức nền bổ sung ngoài tài liệu lớp học”. Trường này được giữ khi chuẩn hóa và lưu bulk.
- **Giới hạn:** Bổ sung bằng kiến thức sẵn có của mô hình, chưa có tìm kiếm web trực tiếp; không bịa nội dung riêng của lớp, URL hoặc thông tin cập nhật. Nếu không đủ cơ sở tạo câu hỏi chính xác, trả về danh sách rỗng.

### POST `/api/ai/chat/`
- **Mục đích:** Hướng dẫn học sinh bằng tiếng Việt, ưu tiên nội dung RAG liên quan; giải thích từng bước và hỏi lại nếu thiếu dữ kiện quyết định.
- **Khi RAG thiếu:** Vẫn trả lời bằng kiến thức nền đáng tin cậy, ghi rõ phần bổ sung ngoài tài liệu. Câu hỏi về nội dung riêng của lớp chưa được cung cấp sẽ được hỏi lại thay vì suy đoán.
- **Nguồn:** `answer` nêu tên tài liệu thực sự sử dụng và phân biệt kiến thức bổ sung. `sources` là mảng rỗng vì hiện chưa có trích dẫn được xác minh tự động; không gắn nhãn mọi câu trả lời là kiến thức nội bộ.
- **Giới hạn:** Chưa tìm kiếm web trực tiếp. Quyền truy cập lớp và giới hạn tần suất giữ nguyên.

### POST `/api/ai/generate/save-bulk/`
- **Mục đích:** Lưu hàng loạt câu hỏi AI trích xuất (Drafts) vào Database thực sự.
- Tương thích hoàn toàn với cấu trúc mảng `content_json` có chứa các Node hình ảnh JSON. Backend tự tạo ImageBank nếu Sha256 chưa tồn tại.

---

## 5. Dữ liệu Response chuẩn cho Ảnh trong Question

```json
{
  "id": 1,
  "text": "...",
  "question_images": [
    {
      "id": 10,
      "image": {
        "sha256": "...",
        "image_url": "https://res.cloudinary.com/...",
        "original_filename": "hinh1.png",
        "mime_type": "image/png"
      },
      "position": 0,
      "placement": "stem",
      "source_type": "ai_scan"
    }
  ]
}
```

## 6. Lời khuyên Workflow cho Frontend

* **Luồng TẠO MỚI/EDIT Thủ công:**
  1. Người dùng kéo thả ảnh vào Editor/Form.
  2. Javascript bắt file ảnh, gọi API tới `https://api.cloudinary.com/v1_1/YOUR_CLOUD/image/upload` với file đính kèm. Nhận về URL.
  3. Khi bấm "Lưu câu hỏi", Javascript build cục JSON khổng lồ chứa text và các Object ảnh mang URL kia. Bắn phát POST/PUT 1 lần duy nhất vào Backend.
* **Luồng TRÍCH XUẤT AI:**
  1. Người dùng chọn file DOCX > 5MB.
  2. Javascript tải thẳng lên Cloudinary lấy URL.
  3. Gọi `/api/ai/generate/extract-file/` với cái URL đó.
  4. Duyệt kết quả bảng hiển thị.
  5. Bấm "Lưu các câu đã chọn" -> Javascript gọi `/api/ai/generate/save-bulk/` gửi toàn bộ Array 1 lần. 
  6. Backend giải quyết việc tạo Model và Link DB trong nháy mắt.
