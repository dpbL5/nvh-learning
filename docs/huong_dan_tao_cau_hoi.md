# Hướng Dẫn Tạo Câu Hỏi Trắc Nghiệm

---

## 1. Trắc Nghiệm Nhiều Lựa Chọn (Multiple Choice — MCQ)

### Hướng dẫn

Tạo câu hỏi trắc nghiệm với **4 phương án trả lời**: 1 đáp án đúng và 3 đáp án sai, các phương án có độ dài tương đương.

**Yêu cầu phần dẫn:**
- Ngắn gọn, rõ ý, không hỏi theo kiểu tự luận.
- Bắt buộc hỏi theo dạng lựa chọn: *"Phương án nào sau đây nêu đúng...?"*, *"Phát biểu nào sau đây đúng về...?"*, *"Định nghĩa nào nêu đúng về...?"* hoặc cách hỏi tương đương.
- Không dùng câu hỏi mở như *"... là gì?"*, *"... có vai trò gì?"*, *"... diễn ra như thế nào?"*. Viết lại thành câu hỏi lựa chọn, giữ nguyên kiến thức và mức nhận thức cần kiểm tra.
- Ví dụ: *"Thiết bị thông minh có vai trò gì trong cuộc sống hiện đại?"* → *"Phương án nào sau đây nêu đúng vai trò của thiết bị thông minh trong cuộc sống hiện đại?"*

**Yêu cầu các phương án:**
- Đồng nhất về cấu trúc và độ dài.
- Không trùng lặp nội dung.
- Không tạo cơ hội đoán mò.

---

### Định dạng kết quả

```
**Câu [Số thứ tự].** [Nội dung câu hỏi].

A. [Nội dung đáp án A].
B. [Nội dung đáp án B].
C. [Nội dung đáp án C].
D. [Nội dung đáp án D].

**Lời giải:**
[Giải thích chi tiết tại sao đáp án đúng. Không dùng danh sách có thứ tự hoặc không thứ tự trong phần này.]

**Chọn [A / B / C / D]**
```

> **Lưu ý:** Không có thông tin thêm giữa các câu hỏi. Kết thúc mỗi phương án bằng dấu chấm (`.`).

---

### Ví dụ

**Câu 1.** Thiết bị nào dưới đây có nhiệm vụ kết nối các thiết bị trong mạng LAN và truyền dữ liệu giữa chúng?

A. Modem.

B. Switch.

C. Router.

D. Access Point.

**Lời giải:**
Switch là thiết bị có chức năng kết nối các thiết bị mạng trong mạng LAN và truyền dữ liệu giữa chúng, khác với Router (kết nối các mạng khác nhau), Modem (chuyển đổi tín hiệu từ ISP), và Access Point (phát sóng Wi-Fi).

**Chọn B**

---

## 2. Trắc Nghiệm Đúng / Sai (True-False)

### Hướng dẫn

**Phần dẫn (bối cảnh):**
- Đưa ra một tình huống thực tiễn hoặc giả định phù hợp thực tiễn.
- Khi viết tình huống giả định, nêu người tham gia, mục tiêu, sự việc/vướng mắc và điều kiện xử lí. Các nhận định phải phục vụ việc hiểu hoặc xử lí chính tình huống đó; tránh chỉ thêm “Giả sử” vào một danh sách số liệu.
- Có thể tự xây dựng bối cảnh ngoài RAG từ kiến thức nền, ngay cả khi RAG đủ thông tin; kiến thức cần kiểm tra vẫn đúng chủ đề/YCCĐ, không đòi thêm chuyên môn ngoài bài. Ghi rõ tình huống giả định, không gán dữ kiện tự dựng cho tài liệu.
- Ngắn gọn: khoảng 5–10 dòng hoặc ít hơn.
- Chỉ cung cấp dữ kiện tình huống (số liệu, trạng thái, cấu hình, hành động, quan sát); không cung cấp định nghĩa, công thức, quy tắc hoặc cách giải đang kiểm tra. Học sinh phải tự nhớ lại kiến thức đã học để áp dụng.
- Phần dẫn và phần câu hỏi phải có câu liên kết — học sinh **bắt buộc phải dựa vào bối cảnh** để trả lời đúng. Nếu bỏ bối cảnh đi mà học sinh vẫn trả lời được thì ý hỏi **không đạt yêu cầu**.

**Phần câu hỏi:**
- Gồm **4 ý hỏi đúng/sai** (a, b, c, d).
- 4 ý phải thể hiện đủ **3 mức nhận thức**: Nhận biết — Thông hiểu — Vận dụng.
- Cả bốn ý, kể cả Nhận biết, phải dùng dữ kiện quyết định trong bối cảnh. Không dùng phát biểu lý thuyết chung rồi thêm tên nhân vật hoặc cụm “trong tình huống trên”.
- Tự kiểm tra từng ý: **che bối cảnh** thì chưa đủ cơ sở kết luận; **đổi dữ kiện quyết định** một cách hợp lí thì có thể đảo đáp án. Nếu không đạt, viết lại ý hỏi.
- Mỗi ý phải cần cả **kiến thức đã học** và **dữ kiện bối cảnh**. Nếu chỉ đọc hoặc đối chiếu câu chữ trong bối cảnh là trả lời được thì viết lại; kiến thức dùng để giải thích chỉ trình bày trong lời giải.
- Bối cảnh phải đủ dữ kiện, không nói sẵn kết luận; không đánh dấu Sai chỉ vì thông tin không được đề cập. Lời giải từng ý phải nêu dữ kiện đã dùng và kiến thức áp dụng để kết luận.

---

### Định dạng kết quả

```
**Câu [Số thứ tự].** [Phần dẫn — tình huống/bối cảnh]

[Câu liên kết dẫn vào các ý hỏi]

a) [Ý hỏi 1]
b) [Ý hỏi 2]
c) [Ý hỏi 3]
d) [Ý hỏi 4]

**Lời giải:**

**a) [Mức nhận thức], [Đúng/Sai]** — [Giải thích].
**b) [Mức nhận thức], [Đúng/Sai]** — [Giải thích].
**c) [Mức nhận thức], [Đúng/Sai]** — [Giải thích].
**d) [Mức nhận thức], [Đúng/Sai]** — [Giải thích].
```

---

### Ví dụ

**Câu 2.** Trường THPT XYZ có hai tòa nhà, các tòa nhà cách nhau khoảng 200m. Trong các phòng học của mỗi tòa nhà đều có các máy tính được kết nối với nhau thông qua cáp mạng. Tại từng tầng của mỗi tòa nhà có một thiết bị Access Point được lắp đặt sao cho có thể phủ sóng Wi-Fi cho tất cả các máy tính trong các phòng học của mỗi tòa nhà. Nhà trường ký hợp đồng với nhà cung cấp dịch vụ (ISP) để tất cả các máy tính đều có thể truy cập Internet. Thời khóa biểu, các kế hoạch hoạt động của nhà trường đều đưa lên mạng để phụ huynh, học sinh có thể tìm hiểu. Nhà trường đang xây dựng một trang web mượn, trả thiết bị dạy học.

*Một số bạn học sinh đưa ra các ý kiến sau về hệ thống mạng của nhà trường:*

a) Mạng máy tính của trường thuộc loại mạng LAN.

b) Máy tính trong các phòng học truy cập Internet thông qua mạng Wi-Fi.

c) Máy tính trong các phòng học trao đổi dữ liệu với nhau nhờ các thiết bị mạng, nhưng nếu muốn kết nối Internet thì phải nhờ tới ISP.

d) Hiện nay giáo viên và học sinh có thể đăng ký mượn thiết bị dạy học online.

**Lời giải:**

**a) Nhận biết, Đúng** — Các máy tính kết nối trong phạm vi trường học nên thuộc loại mạng LAN.

**b) Thông hiểu, Sai** — Máy tính trong phòng học dùng cáp mạng, không truy cập Internet qua Wi-Fi.

**c) Vận dụng, Đúng** — Máy tính trao đổi dữ liệu qua thiết bị mạng; muốn vào Internet thì cần ISP.

**d) Vận dụng, Sai** — Trang web mượn thiết bị chưa hoàn thành, nên chưa thể đăng ký online.

---

## 3. Bảng So Sánh Hai Dạng Câu Hỏi

| Tiêu chí | MCQ (Nhiều lựa chọn) | True-False (Đúng/Sai) |
|---|---|---|
| Số phương án | 4 (A, B, C, D) | 4 ý (a, b, c, d) |
| Cấu trúc phần dẫn | Câu hỏi ngắn, độc lập | Bối cảnh thực tiễn 5–10 dòng |
| Yêu cầu bối cảnh | Không bắt buộc | Bắt buộc — học sinh phải dựa vào bối cảnh |
| Mức nhận thức | Không yêu cầu phân tầng | Phải đủ 3 mức: Nhận biết / Thông hiểu / Vận dụng |
| Lời giải | Giải thích đáp án đúng | Giải thích từng ý kèm mức nhận thức |
| Đáp án cuối | `**Chọn [A/B/C/D]**` | Ghi rõ Đúng/Sai cho từng ý |

## 4. Cách viết tham khảo từ đề Tin học mã 0501

Đối chiếu tệp `Đề_Tin học_0501.pdf` do người dùng cung cấp (4 trang). Áp dụng cách đặt nhiệm vụ và xây dựng phương án, không sao chép câu hỏi, số lượng câu hay phần thi tự chọn.

- **MCQ, trang 1–3:** Câu dẫn gọn, hỏi một yêu cầu cụ thể; đa dạng dạng xác định kết quả chương trình, chọn đoạn mã, sắp xếp thao tác và lựa chọn cách xử lí. Phương án kỹ thuật thường khác nhau ở chi tiết then chốt như đơn vị, thuộc tính, điều kiện hoặc thứ tự. Giữ nguyên cú pháp mã/lệnh, không thêm dấu chấm vào mã chỉ để đồng nhất hình thức.
- **Đúng/Sai, trang 3–4:** Bối cảnh có thể gồm nhiệm vụ kèm đoạn mã HTML, chương trình, hồ sơ dữ liệu hoặc lược đồ cơ sở dữ liệu. Câu liên kết gọi đúng đối tượng đang phân tích; bốn ý xét thành phần, ý nghĩa, kết quả và phương án thay đổi/xử lí. Mỗi ý được đánh giá độc lập, có thể đặt giả thiết riêng.
- **Áp dụng vào hệ thống:** Giữ yêu cầu mỗi ý cần cả dữ kiện bối cảnh và kiến thức đã học, đủ ba mức nhận thức. Bối cảnh ngoài RAG vẫn được phép. Ví dụ trong prompt là tình huống giả định siêu thị mini thử quầy cân dùng camera nhận diện trái cây, có vấn đề ùn khách và tình huống khách mang loại quả chưa có trong bộ ảnh; các ý vận dụng kiến thức nhận diện ảnh, nhãn dữ liệu, phạm vi mô hình và tách bộ kiểm tra.
- **Tự rà soát:** Tính hoặc mô phỏng kết quả, đối chiếu tên trường/thuộc tính, điều kiện, đơn vị và từng đáp án. Sai sót trong một phương án phải có chủ đích và được giải thích; không để lỗi vô ý trong dữ kiện làm câu hỏi mơ hồ.
