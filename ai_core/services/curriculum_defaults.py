"""Chuẩn chương trình mặc định cho module sinh câu hỏi Tin học lớp 10.

Nguồn: tài liệu YCCD lớp 10 và bảng từ ngữ thể hiện cấp độ tư duy do nhà trường cung cấp.
"""

DEFAULT_GRADE_10_LEARNING_OUTCOMES = """
Đây là YCCĐ tổng quát mặc định của môn Tin học lớp 10. Chỉ chọn các YCCĐ liên quan trực tiếp đến
nội dung SOURCE/tài liệu đã chọn; không cố bao phủ tất cả chủ đề trong một lần sinh.

A. Máy tính và xã hội tri thức
- Phân biệt thông tin và dữ liệu; chuyển đổi đơn vị lưu trữ; nêu ưu việt của lưu trữ, xử lí và truyền thông tin số.
- Trình bày đóng góp của tin học; nhận biết thiết bị số và thiết bị thông minh, giải thích vai trò của chúng;
  giới thiệu mốc phát triển của ngành tin học; sử dụng thiết bị số và phần mềm cơ bản.
- Thực hiện AND, OR, NOT; giải thích ứng dụng hệ nhị phân, số hoá văn bản/hình ảnh/âm thanh và bảng mã Unicode.

B. Mạng máy tính và Internet
- Trình bày thay đổi do mạng máy tính tạo ra; so sánh LAN với Internet; nêu dịch vụ điện toán đám mây,
  khái niệm IoT, ví dụ và ích lợi của IoT.
- Sử dụng chức năng xử lí thông tin trên thiết bị số; khai thác học liệu mở; nhận biết nguy cơ trên Internet,
  cách phòng tránh, phòng vệ trước bắt nạt mạng, bảo vệ dữ liệu cá nhân và ngăn ngừa phần mềm độc hại.

D. Đạo đức, pháp luật và văn hoá trong môi trường số
- Nêu vấn đề pháp luật, đạo đức, văn hoá khi giao tiếp mạng; giải thích vi phạm bản quyền và hậu quả.
- Trình bày, giải thích nội dung cơ bản của Luật Công nghệ thông tin, quy định quản lí/cung cấp/sử dụng sản phẩm,
  dịch vụ CNTT và Luật An ninh mạng; vận dụng để xác định tính hợp pháp của hành vi.
- Nêu tác hại của chia sẻ thông tin bất cẩn và biện pháp nâng cao an toàn, tính hợp pháp khi chia sẻ thông tin.

E. Ứng dụng tin học
- Sử dụng chức năng cơ bản của phần mềm thiết kế đồ hoạ; tạo sản phẩm số đơn giản, hữu ích và thực tế.

F. Giải quyết vấn đề với sự trợ giúp của máy tính
- Viết và thực hiện chương trình dùng hằng, biến, cấu trúc điều khiển, toán tử, kiểu dữ liệu chuẩn, mảng, vào-ra.
- Viết chương trình dùng chương trình con/thư viện chuẩn; đọc hiểu, kiểm thử, gỡ lỗi và giải bài toán đơn giản
  có vận dụng kiến thức liên môn.

G. Hướng nghiệp với tin học
- Trình bày nhóm nghề thiết kế và lập trình; tìm kiếm, khai thác thông tin hướng nghiệp và trao đổi qua kênh số.
""".strip()

COGNITIVE_LEVEL_GUIDANCE = """
KHUNG CẤP ĐỘ TƯ DUY BẮT BUỘC
- Trước khi viết mỗi câu/ý, xác định một cấp độ tư duy và dùng động từ phù hợp với đối tượng, yêu cầu cụ thể.
  Không chỉ gắn nhãn cấp độ sau khi đã viết câu hỏi.
- Biết: yêu cầu nhớ/nhận diện/thực hiện trực tiếp, với động từ như kể, nêu, nhận biết, nhận ra, nhận diện,
  chỉ ra, khởi động, kích hoạt, tìm kiếm, thực hiện.
- Hiểu: yêu cầu diễn tả, mô tả, trình bày, giải thích, phân tích, phân biệt, so sánh, đọc hiểu, đánh giá
  dựa trên kiến thức đã học.
- Vận dụng: yêu cầu dùng kiến thức để giải quyết nhiệm vụ/tình huống cụ thể, với động từ như tìm, biên tập,
  chuyển đổi, cài đặt, kết nối, khai thác, tạo, xác định, chọn, thiết lập, sử dụng, vận dụng, bảo vệ,
  kiểm thử, viết, thiết kế, quản lí.
- Mức độ phải khớp động từ trong YCCĐ đang đánh giá. Nếu YCCĐ dùng "nêu/nhận biết" thì không tự nâng thành
  yêu cầu kiến thức ngoài bài; nếu dùng "giải thích/so sánh" phải buộc học sinh thể hiện quan hệ hoặc lí do;
  nếu dùng "vận dụng/xác định/thiết kế/kiểm thử" phải có dữ kiện tình huống cụ thể để áp dụng.
- Với một bộ câu hỏi, phân bố cấp độ theo YCCĐ và nội dung SOURCE: có cả Biết, Hiểu, Vận dụng khi phạm vi cho phép;
  không tạo độ khó bằng mẹo, câu dài hay kiến thức ngoài chương trình.
- Trong explanation, nêu rõ cấp độ tư duy (Biết, Hiểu hoặc Vận dụng) và động từ/YCCĐ được đánh giá.
""".strip()
