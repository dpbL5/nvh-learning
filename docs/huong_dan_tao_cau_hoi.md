# Hướng Dẫn Tạo Câu Hỏi Trắc Nghiệm

Trong form sinh câu hỏi AI, **Yêu cầu cần đạt là tùy chọn** (tối đa 500 ký tự, có thể nhiều dòng), ví dụ: “Nêu được chức năng của switch và Access Point; lựa chọn thiết bị phù hợp để kết nối mạng trong tình huống cụ thể.” Khi có YCCĐ, prompt dùng động từ, đối tượng kiến thức/kỹ năng và giới hạn để chọn nhiệm vụ đánh giá. Khi để trống, AI xác định nội dung cần đánh giá từ tài liệu đã chọn hoặc tài liệu của lớp, không tự gán đó thành YCCĐ chính thức của SGK. Mỗi câu và từng ý Đúng/Sai phải bám phạm vi này; nếu không có cả YCCĐ lẫn nội dung tài liệu thì hệ thống báo cần bổ sung.

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

**Quy trình soạn từ cách giải:**
- Chọn kiến thức cần kiểm tra → dựng tình huống và bốn nhận định → giải thử độc lập từng ý → bổ sung điều kiện còn thiếu → chốt đáp án và lời giải.
- Khi giải thử: tách dữ kiện/yêu cầu/giả thiết riêng → xác định kiến thức cần dùng → đối chiếu nhận định → kiểm tra điều kiện có thể đổi kết luận. Không chọn trước mẫu Đ/S rồi sửa nội dung cho khớp.
- Không ép số lượng hoặc vị trí ý Đúng/Sai; cả bốn ý cùng đúng hoặc cùng sai vẫn hợp lệ nếu có căn cứ. Bước chuẩn hóa giữ nguyên đáp án từng ý, không tự lật đáp án.
- Kiến thức để giải phải thuộc nội dung bài học/SGK và YCCĐ của bài, kể cả phương án nhiễu và lời giải. Tăng yêu cầu tư duy bằng cách kết hợp/vận dụng kiến thức đã học; không thêm kiến thức bài/lớp khác như Gateway khi bài chưa học. Khi thiếu nguồn và chưa xác định chắc phạm vi bài thì không suy đoán để sinh câu hỏi.
- Form sinh câu hỏi không gắn nhãn mức nhận thức cho câu Đúng/Sai: một câu gồm bốn ý độc lập nên không gán một mức chung cho cả câu, cũng không ghi mức cho từng ý. Mức nhận thức chỉ áp dụng và chọn được ở dạng trắc nghiệm nhiều lựa chọn.

**Phần dẫn (bối cảnh):**
- Đưa ra một tình huống thực tiễn hoặc giả định phù hợp thực tiễn.
- Xác định rõ **thực thể → vấn đề thực tiễn → hoạt động/phương án đang thực hiện → dữ kiện/ràng buộc**. Đưa phương án và dữ kiện quyết định vào bối cảnh để học sinh có cơ sở đánh giá, không giảng sẵn phương án đúng hay sai.
- Viết tình huống giả định thành một đoạn tường thuật khách quan: giới thiệu đơn vị/con người và hoạt động → hiện trạng, dữ liệu hoặc điều kiện → nhu cầu/mục tiêu dự định thực hiện. Các câu nối tự nhiên và phục vụ các nhận định; không bắt buộc tạo đối thoại, nhân vật phụ hoặc biến cố bất ngờ.
- Chọn hoạt động thực tế có ý nghĩa trong lĩnh vực ứng dụng: có nhu cầu, dữ kiện/ràng buộc và giải pháp cần đánh giá. Không dùng “trong một buổi học, giáo viên hướng dẫn học sinh…”, tiết thực hành hoặc bài tập đóng vai. Trường học vẫn có thể là đơn vị có nhu cầu vận hành thực, như quản lí thư viện hoặc triển khai mạng.
- Có thể tự xây dựng bối cảnh ngoài RAG từ kiến thức nền, ngay cả khi RAG đủ thông tin; kiến thức cần kiểm tra vẫn đúng chủ đề/YCCĐ, không đòi thêm chuyên môn ngoài bài. Ghi rõ tình huống giả định, không gán dữ kiện tự dựng cho tài liệu.
- Ngắn gọn: khoảng 5–10 dòng hoặc ít hơn.
- Chỉ cung cấp dữ kiện tình huống (số liệu, trạng thái, cấu hình, hành động, quan sát); không cung cấp định nghĩa, công thức, quy tắc hoặc cách giải đang kiểm tra. Học sinh phải tự nhớ lại kiến thức đã học để áp dụng.
- Phần dẫn và phần câu hỏi phải có câu liên kết; các ý xét đối tượng, hoạt động hoặc phương án thực sự có trong tình huống. Ý đánh giá phương án/kết quả phải dựa vào dữ kiện/ràng buộc của bối cảnh để giải.

**Phần câu hỏi:**
- Gồm **4 ý hỏi đúng/sai** (a, b, c, d).
- Mỗi ý có một kết luận trọng tâm; không ghép hai kết luận độc lập khiến một phần đúng, một phần sai. Điều kiện ảnh hưởng đáp án phải được nêu rõ, tránh phủ định kép và từ đánh giá không có tiêu chí.
- Không gắn nhãn **Biết/Hiểu/Vận dụng** cho câu Đúng/Sai hoặc cho từng ý, kể cả trong lời giải. Các ý vẫn đa dạng thao tác tư duy: nhận diện khái niệm/đặc điểm qua dữ kiện, giải thích vai trò/phân biệt/suy luận quan hệ, đánh giá lựa chọn/thao tác/kết quả theo ràng buộc; sắp ý theo mạch của tình huống.
- Ý nhận diện hoặc giải thích có thể dùng đối tượng cụ thể trong bối cảnh, như giao thức trong URL hoặc vai trò tên miền. Không bắt buộc thay dữ kiện phải đảo đáp án của kiến thức nền; không thêm tên nhân vật vào lý thuyết không liên quan.
- Mỗi ý đánh giá lựa chọn, thao tác, cách sử dụng dữ liệu hoặc kết quả cụ thể trong hoạt động của thực thể. Tránh “nâng cao hiệu quả”, “cần dữ liệu chính xác” và những nhận định dùng được cho mọi tình huống. Không chép lại toàn bộ dữ kiện quyết định vào từng ý, khiến học sinh không cần đọc bối cảnh.
- Tự kiểm tra ý đánh giá: nếu bỏ bối cảnh mà vẫn giải được thì viết lại để cần dùng dữ kiện/ràng buộc cụ thể.
- Mỗi ý phải cần **kiến thức đã học** để đánh giá đối tượng hoặc dữ kiện đang xét. Nếu chỉ đọc hoặc đối chiếu câu chữ trong bối cảnh là trả lời được thì viết lại; kiến thức dùng để giải thích chỉ trình bày trong lời giải.
- Câu liên kết gọi đúng hoạt động/hệ thống đang xét; không thêm cảnh giáo viên và học sinh thảo luận. Ý đánh giá phải dùng dữ kiện/ràng buộc để đánh giá phương án hoặc giải quyết nhu cầu thực tế đã nêu.
- Bối cảnh phải đủ dữ kiện, không nói sẵn kết luận; không đánh dấu Sai chỉ vì thông tin không được đề cập. Lời giải từng ý phải nêu dữ kiện đã dùng và kiến thức áp dụng để kết luận.
- Ý Sai phản ánh một hiểu nhầm hợp lí; lời giải phải chỉ chỗ sai và cách sửa. Tự phản biện xem điều kiện chưa nêu hoặc cách hiểu hợp lí khác có thể đảo đáp án hay không; nếu có thì sửa câu hỏi trước khi xuất.
- Điều kiện quyết định phải có ngay trong đề: ví dụ khi máy chủ đổi IP cần làm rõ DNS đã cập nhật; khi cần Wi-Fi từ mạng có dây phải phân biệt chức năng Access Point với thiết bị AP riêng. Không bổ sung giả định chỉ trong lời giải để hợp thức hóa đáp án.
- Lời giải trình bày lần lượt a), b), c), d), mỗi ý ghi Đúng/Sai và mạch **dữ kiện/đối tượng → kiến thức áp dụng → kết luận**, khớp với `options[].is_correct`; không ghi mức nhận thức.

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

**a) [Đúng/Sai]** — [Giải thích].
**b) [Đúng/Sai]** — [Giải thích].
**c) [Đúng/Sai]** — [Giải thích].
**d) [Đúng/Sai]** — [Giải thích].
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

**a) Đúng** — Các máy tính kết nối trong phạm vi trường học nên thuộc loại mạng LAN.

**b) Sai** — Máy tính trong phòng học dùng cáp mạng, không truy cập Internet qua Wi-Fi.

**c) Đúng** — Máy tính trao đổi dữ liệu qua thiết bị mạng; muốn vào Internet thì cần ISP.

**d) Sai** — Trang web mượn thiết bị chưa hoàn thành, nên chưa thể đăng ký online.

---

## 3. Bảng So Sánh Hai Dạng Câu Hỏi

| Tiêu chí | MCQ (Nhiều lựa chọn) | True-False (Đúng/Sai) |
|---|---|---|
| Số phương án | 4 (A, B, C, D) | 4 ý (a, b, c, d) |
| Cấu trúc phần dẫn | Câu hỏi ngắn, độc lập | Bối cảnh thực tiễn 5–10 dòng |
| Yêu cầu bối cảnh | Không bắt buộc | Bắt buộc — học sinh phải dựa vào bối cảnh |
| Mức nhận thức | Chọn được Nhận biết / Thông hiểu / Vận dụng khi sinh câu hỏi (xem mục 4) | Không gắn nhãn mức nhận thức |
| Lời giải | Giải thích đáp án đúng | Giải thích từng ý, không kèm mức nhận thức |
| Đáp án cuối | `**Chọn [A/B/C/D]**` | Ghi rõ Đúng/Sai cho từng ý |

## 4. Phân biệt mức nhận thức khi sinh câu trắc nghiệm

Mức nhận thức chỉ gắn cho câu nhiều lựa chọn; câu Đúng/Sai và trả lời ngắn không gắn nhãn.

### Phân biệt "Biết" và "Hiểu" khi cùng dùng một động từ SMART

- Chỉ nhắc lại, tái hiện kiến thức/kĩ năng đơn thuần → **Biết**.
- Đòi hỏi một trình tự logic, diễn đạt lại, hiểu mối quan hệ giữa các đơn vị kiến thức và kết nối chúng → **Hiểu**.
- Cùng một động từ như "nêu", "trình bày", "mô tả": nếu học sinh chỉ cần nhớ lại hoặc nhận diện đúng câu chữ thì vẫn là Biết; nếu phải lập luận, sắp xếp, chỉ ra quan hệ thì mới là Hiểu.

### Phân biệt "Hiểu" và "Vận dụng"

- "Vận dụng" đôi khi thấp hơn "Hiểu": làm được một cách máy móc nhưng không giải thích được bản chất thì chưa chắc đã là Vận dụng.
- Câu hỏi đưa ra một tình huống cụ thể (bối cảnh có ý nghĩa hoặc bối cảnh thực tiễn) có thể dùng để đánh giá mức Hiểu hoặc mức Vận dụng, nhưng thường được dùng cho mức Vận dụng nhiều hơn.
- Câu đánh giá mức Hiểu đòi hỏi quá trình tư duy thiên về lập luận để tìm ra bản chất của tri thức tin học, không thiên về tính toán hoặc áp dụng tri thức tin học để nhận được một kết quả cụ thể — đó là đặc trưng của câu Vận dụng.
- Không nâng mức chỉ vì câu dài hoặc dùng thuật ngữ khó.

### Dấu hiệu nhận diện nhanh

| Mức | Học sinh phải làm gì | Kiểu câu dẫn |
|---|---|---|
| Nhận biết (Biết) | Nhớ lại, nhận diện đúng định nghĩa, đặc điểm, phát biểu | "Phương án nào sau đây nêu đúng ...?" |
| Thông hiểu (Hiểu) | Giải thích, so sánh, phân biệt, chỉ ra quan hệ để làm rõ bản chất | "Phương án nào sau đây giải thích đúng ...?" |
| Vận dụng | Dùng dữ kiện tình huống (số liệu, cấu hình, hành động, ràng buộc) để tính toán hoặc quyết định | "Trong tình huống ..., phương án nào sau đây ...?" |

### Thứ tự xét mức và kiểm tra

Xét theo thứ tự, dừng ở mức đầu tiên thỏa:

1. Trả lời được bằng nhớ lại hoặc nhận diện đúng câu chữ của bài → **Biết**.
2. Phải so sánh, phân biệt, giải thích hoặc chỉ ra quan hệ mới chọn được → **Hiểu**.
3. Chỉ chọn được khi dùng dữ kiện riêng của tình huống (số liệu, cấu hình, hành động, ràng buộc) để tính hoặc quyết định → **Vận dụng**.

- Mức của câu do thao tác bắt buộc cao nhất quyết định, nhưng chỉ khi thao tác đó thực sự cần để chọn đáp án.
- Có bối cảnh không tự động là Vận dụng: bỏ dữ kiện riêng mà vẫn chọn được đáp án thì hạ xuống Hiểu hoặc Biết.
- Viết xong câu và tự giải mới gán nhãn; không gán nhãn trước rồi viết câu cho khớp.
- Kiểm tra logic: chỉ từ câu dẫn và kiến thức bài phải loại được cả ba nhiễu, giữ đúng một đáp án; mỗi nhiễu sai vì một lỗi kiến thức nêu được trong lời giải; nếu phải thêm giả định ngoài câu dẫn mới loại được nhiễu thì viết lại câu.

## 5. Cách viết tham khảo từ đề Tin học mã 0501

Đối chiếu tệp `Đề_Tin học_0501.pdf` do người dùng cung cấp (4 trang). Áp dụng cách đặt nhiệm vụ và xây dựng phương án, không sao chép câu hỏi, số lượng câu hay phần thi tự chọn.

- **MCQ, trang 1–3:** Câu dẫn gọn, hỏi một yêu cầu cụ thể; đa dạng dạng xác định kết quả chương trình, chọn đoạn mã, sắp xếp thao tác và lựa chọn cách xử lí. Phương án kỹ thuật thường khác nhau ở chi tiết then chốt như đơn vị, thuộc tính, điều kiện hoặc thứ tự. Giữ nguyên cú pháp mã/lệnh, không thêm dấu chấm vào mã chỉ để đồng nhất hình thức.
- **Đúng/Sai, trang 3–4:** Bối cảnh có thể gồm nhiệm vụ kèm đoạn mã HTML, chương trình, hồ sơ dữ liệu hoặc lược đồ cơ sở dữ liệu. Câu liên kết gọi đúng đối tượng đang phân tích; bốn ý xét thành phần, ý nghĩa, kết quả và phương án thay đổi/xử lí. Mỗi ý được đánh giá độc lập, có thể đặt giả thiết riêng.
- **Áp dụng vào hệ thống:** Mỗi ý dùng kiến thức đã học để đánh giá đối tượng trong tình huống; ý đánh giá phải khai thác dữ kiện/ràng buộc cụ thể. Bối cảnh ngoài RAG vẫn được phép. Ví dụ trong prompt là trung tâm bảo hành đang xây dựng hệ thống dự đoán để phân luồng máy giặt; phương án huấn luyện và chọn hồ sơ kiểm tra nằm trong bối cảnh. Bốn ý đánh giá cách gán nhãn, chọn đầu vào, kiểm tra mô hình và dùng dự đoán để đặt linh kiện.
- **Tự rà soát:** Tính hoặc mô phỏng kết quả, đối chiếu tên trường/thuộc tính, điều kiện, đơn vị và từng đáp án. Sai sót trong một phương án phải có chủ đích và được giải thích; không để lỗi vô ý trong dữ kiện làm câu hỏi mơ hồ.

## 6. Nguyên tắc thiết kế câu hỏi và nguồn tham khảo

Trình tự áp dụng: xác định kiến thức/năng lực cần đo → chọn nhiệm vụ vận dụng → dựng bối cảnh đủ dữ kiện → viết từng ý và đáp án → rà soát cách hiểu khác. Đây là cách vận dụng các nguyên tắc dưới đây vào prompt; chất lượng câu sinh ra vẫn cần được kiểm tra thực tế.

- [University of Waterloo – Exam Questions: Types, Characteristics, and Suggestions](https://uwaterloo.ca/centre-for-teaching-excellence/catalogs/tip-sheets/exam-questions-types-characteristics-and-suggestions): mỗi ý Đúng/Sai có một ý trung tâm, tránh câu phức tạp, phủ định kép, khái quát quá rộng và từ ngữ mơ hồ. Áp dụng bằng cách tách các kết luận độc lập và giải thích cách sửa ý Sai.
- [NBME – Item-Writing Guide, chương 2–3 và 5–6](https://www.nbme.org/sites/default/files/2021-02/NBME_Item%20Writing%20Guide_R_6.pdf): chú trọng áp dụng kiến thức qua dữ kiện tình huống; đáp án Đúng/Sai cần rõ, tránh phụ thuộc giả định ngầm hoặc mẹo đoán. Tài liệu thuộc lĩnh vực y khoa và ưu tiên câu một đáp án tốt nhất; ở đây chỉ vận dụng nguyên tắc viết/rà soát, không chuyển định dạng đề sang NBME.
- [OECD – PISA 2018 Science Framework, Organisation of the domain và Cognitive demand](https://www.oecd.org/en/publications/pisa-2018-assessment-and-analytical-framework_b25efab8-en/full-report/component-5.html): thiết kế nhiệm vụ gắn kiến thức, năng lực, bối cảnh và yêu cầu tư duy. Áp dụng vào Tin học bằng cách xác định điều cần đánh giá trước khi dựng tình huống thực tế, không chỉ thêm câu chuyện vào câu hỏi ghi nhớ.
- [Cục Quản lý chất lượng – Cấu trúc định dạng đề thi tốt nghiệp THPT từ năm 2025](https://vqa.moet.gov.vn/vi/news/thong-bao/cau-truc-dinh-dang-de-thi-tot-nghiep-thpt-tu-nam-2025-74.html): dạng Đúng/Sai có bốn ý, trả lời từng ý. Theo yêu cầu thiết kế của dự án, câu Đúng/Sai không bị gắn một mức nhận thức chung hay mức cho từng ý; mức nhận thức chỉ chọn được ở dạng trắc nghiệm. Bối cảnh ngoài RAG và không dùng cảnh dạy học cũng là yêu cầu thiết kế của dự án, không phải quy định được suy ra từ các nguồn quốc tế.
