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
- Ngắn gọn: khoảng 5–10 dòng hoặc ít hơn.
- Phần dẫn và phần câu hỏi phải có câu liên kết — học sinh **bắt buộc phải dựa vào bối cảnh** để trả lời đúng. Nếu bỏ bối cảnh đi mà học sinh vẫn trả lời được thì ý hỏi **không đạt yêu cầu**.

**Phần câu hỏi:**
- Gồm **4 ý hỏi đúng/sai** (a, b, c, d).
- 4 ý phải thể hiện đủ **3 mức nhận thức**: Nhận biết — Thông hiểu — Vận dụng.

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
