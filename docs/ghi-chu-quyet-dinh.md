# Ghi chú quyết định kỹ thuật

> Ghi lại quyết định và lý do. Mục đích: khi GV hỏi "vì sao làm thế" thì trả lời được, và khi tự sửa code sau này thì biết mình đã thử gì.
>
> Cách dùng: thêm mục mới **ngay khi có quyết định**, không để đến cuối. Viết lúc đó còn nhớ lý do.

---

## Cấu trúc mỗi quyết định

```markdown
## Q<x>. <Tên ngắn>

**Ngày:** 2026-10-11
**Trạng thái:** đã chốt / đang thử / đã bỏ

**Vấn đề:** cần làm gì, ràng buộc ra sao

**Phương án đã cân nhắc:**
| Cách | Ưu | Nhược |
|---|---|---|

**Quyết định:** chọn gì

**Lý do:** tại sao chọn, dựa trên gì

**Hệ quả:** cái nào bị ảnh hưởng, đánh đổi gì
```

---

## Q1. Chặn đặt trùng bằng ràng buộc unique partial index

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** 2 bệnh nhân cùng đặt 1 khung giờ phải chỉ 1 người thành công.

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Kiểm tra `is_available` rồi insert | Dễ hiểu | Sai. 2 request cùng đọc "còn trống" rồi cùng insert |
| `SELECT ... FOR UPDATE` | Chặn được | Khoá dòng dữ liệu, chậm khi tranh chấp nhiều, dễ viết sai thứ tự |
| `SERIALIZABLE` isolation | Chặn được | Tốn tài nguyên, không cần thiết |
| **Unique partial index** | Không cần lock, database tự chặn, ai viết code cũng không bỏ qua | Phải bắt lỗi `IntegrityError` trong API |

**Quyết định:** unique partial index trên `appointments(slot_id) WHERE status='CONFIRMED'`.

**Lý do:** ràng buộc đặt ở tầng database là thứ chắc chắn không bị bỏ qua. Các cách khác đều phụ thuộc code viết đúng.

**Hệ quả:** phải bắt lỗi `IntegrityError` và trả `409 SLOT_TAKEN`. Đây là hành vi đúng, không phải lỗi.

---

## Q2. Xác thực JWT trong service, không ở Nginx

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** có nên verify token một lần ở gateway rồi forward xuống không?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Verify ở Nginx (`auth_request`) | Một chỗ, service bên dưới không cần xử lý | Cần module `njs` hoặc `lua-resty-jwt`, compose thuần không có sẵn |
| Verify ở từng service | Không cần hạ tầng phụ | Lặp 4 lần, tốn CPU |
| Middleware ở service Auth rồi forward header đã tin cậy | Một chỗ, service bên dưới rẻ | Phải tin các service nội bộ, thêm độ phức tạp |

**Quyết định:** verify bằng `python-jose` trong FastAPI dependency, ở cả 4 service. Nginx chỉ định tuyến + rate limit.

**Lý do:** không cần cấu hình thêm, dễ chạy ở bất kỳ đâu, và overhead nhân 4 lần là không đáng kể so với độ trễ database.

**Hệ quả:** code xác thực lặp ở 4 chỗ. Chấp nhận. Nếu tối ưu sau thì chuyển sang middleware ở service Auth.

**Cách trả lời khi GV hỏi "verify một lần ở gateway có tốt hơn không":** về lý thuyết thì có, giảm tải CPU. Nhưng cần thêm hạ tầng Nginx không có sẵn trong compose, và phần tiết kiệm không đáng để đổi lấy độ phức tạp vận hành.

---

## Q3. Redis Streams, không phải Pub/Sub

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** dùng cách nào để Booking đẩy event sang Notification?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Pub/Sub của Redis | Đơn giản, nhẹ | **Mất message nếu Notification đang tắt.** Lịch hẹn trong khoảng đó sẽ không có thông báo, mà không ai biết |
| **Redis Streams** | Giữ message tới khi consumer xác nhận. Có thể đọc lại | Phức tạp hơn một chút |
| RabbitMQ | Chuẩn ngành, có nhiều tính năng | Thêm một service nữa vào compose, nặng hơn |
| Kafka | Chuẩn cho dữ liệu lớn | Quá nặng cho khối lượng này |

**Quyết định:** Redis Streams.

**Lý do:** quyết định này dựa trên yêu cầu "không mất dữ liệu". Pub/Sub không đáp ứng — Notification tắt 1 phút là mất event trong phút đó. Streams giữ lại.

**Hệ quả:** phải xử lý idempotent, vì Streams giao lại event khi consumer chết trước khi ack. Xem Q4.

---

## Q4. Xử lý event idempotent, khóa phức hợp

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** Streams đảm bảo "xử lý ít nhất một lần" (at-least-once), nên event chắc chắn có lúc bị xử lý nhiều lần. Nếu không xử lý, người dùng sẽ nhận thông báo trùng.

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Dựa vào logic code ("nếu đã gửi rồi thì bỏ qua") | Không cần hạ tầng | Rủi ro race — 2 worker cùng kiểm tra, cùng thấy chưa gửi |
| Khóa chính chỉ `event_id` | Đơn giản | **Sai.** 1 event gửi cho cả bệnh nhân và bác sĩ = 2 bản ghi. Khóa `event_id` sẽ khóa nhầm bản ghi thứ hai |
| **Khóa phức hợp `(event_id, recipient_id)` + `ON CONFLICT DO NOTHING`** | Chặn đúng từng người nhận, ở tầng database | Phải thiết kế khóa từ đầu |

**Quyết định:** khóa chính phức hợp `(event_id, recipient_id)`, ghi bằng `INSERT ... ON CONFLICT DO NOTHING`.

**Lý do:** database chặn ở tầng thấp nhất, không thể vòng qua. Và khóa phức hợp phân biệt được từng người nhận — nếu chỉ khóa `event_id`, bác sĩ sẽ không bao giờ nhận được thông báo.

**Hệ quả:** xử lý lại nhiều lần không gửi trùng. Nhờ đó có thể an toàn không ack event khi gửi lỗi tạm.

**Cách trả lời khi GV hỏi "event đến trùng xử lý thế nào":** khóa chính là cặp `(event_id, recipient_id)` vì một sự kiện gửi cho hai người nhận khác nhau. Insert với `ON CONFLICT DO NOTHING` — database tự bỏ qua lần thứ hai. Không có race vì việc chặn ở tầng database, không phải kiểm tra rồi mới ghi.

---

## Q5. Mô phỏng tầng gửi thông báo, không dùng dịch vụ thật

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** gửi thông báo qua nhà cung cấp nào?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Twilio / nhà cung cấp SMS thật | Sát thực tế | Cần tài khoản, có phí, cần internet ổn định khi demo |
| Email qua SMTP thật | Miễn phí | Cũng cần cấu hình tài khoản, và không kiểm chứng được bằng mắt nhanh |
| **Ghi log mức `INFO` + lưu bảng `notifications`** | Không cần tài khoản, kiểm chứng ngay trong database, chạy offline | Không gửi ra ngoài thật |

**Quyết định:** mô phỏng. Ghi log và lưu vào bảng `notifications` với cột `status`, `attempts`, `sent_at`.

**Lý do:** phần cần đánh giá là cơ chế xử lý event và lỗi, không phải tích hợp nhà cung cấp. Mô phởng giữ được phần đó mà không rủi ro demo hỏng vì mạng.

**Hệ quả:** kịch bản Locust kiểm tra bảng `notifications` thay vì kiểm tra hộp thư.

**Cách trả lời khi GV hỏi "có gửi thông báo thật không":** em mô phỏng tầng gửi vì cần tài khoản nhà cung cấp và có phí. Phần em muốn kiểm chứng là cơ chế nhận event, xử lý trùng và thử lại khi lỗi — những phần đó không phụ thuộc vào việc dùng kênh gửi nào.

---

## Q6. Không làm phân tích dữ liệu trong đồ án này

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** service thứ 4 nên là phân tích dữ liệu (báo cáo tổng hợp) hay làm gì khác?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| **Notification Service** | Học được xử lý lỗi, retry, idempotent. Không cần thư viện ngoài. Code gọn | Không phải hướng Data Engineering |
| Phân tích dữ liệu (Insight) | Học được SQL nâng cao, ETL, tách OLTP/OLAP | Mất ít nhất 1 tuần. Không thuộc 9 yêu cầu bắt buộc. Dữ liệu do chính mình sinh ra nên không có bài toán dữ liệu bẩn |

**Quyết định:** Notification Service.

**Lý do:** timeline 3–4 tuần phải dồn cho 4 service + Docker + giám sát + kiểm thử tải. Phân tích dữ liệu là phần tự thêm, cắt nó đi thì chắc chắn kịp 9 yêu cầu bắt buộc.

**Hệ quả:** đồ án này thuần Backend/Platform, không có pipeline dữ liệu. Nếu sau này chuyển hướng Data Engineering thì học Airflow và dbt ngoài dự án này, trên một dataset thật.

**Cách trả lời khi GV hỏi "có làm phân tích dữ liệu không":** phần đó không thuộc yêu cầu của đề bài, và em cần dồn thời gian cho 4 service cùng phần giám sát. Em chọn làm đủ phần bắt buộc trước. Nếu còn thời gian em sẽ bổ sung.

---

## Q7. Giao diện dùng React + Vite, làm ở tuần 2–3

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** có làm giao diện không, dùng gì, làm khi nào?

**Đã cân nhắc (về công cụ):**

| Cách | Ưu | Nhược |
|---|---|---|
| HTML + fetch thuần | Ít code nhất | Khó mở rộng, không tách component |
| **React + Vite** | Nhẹ, quen thuộc, đủ cho 4 màn hình | Cần học React |
| Next.js | Chuẩn web hiện đại | Render phía máy chủ, định tuyến phức tạp — nặng hơn thứ cần |

**Quyết định:** làm giao diện bằng React + Vite, thực hiện ở tuần 2–3.

**Lý do về công cụ:** 4 màn hình thì React + Vite là đủ. Next.js thêm render phía máy chủ và định tuyến phức tạp mà không dùng tới — chỉ tăng thời gian học.

**Lý do về thứ tự — đây là điểm mấu chốt:** làm sớm ở tuần 2, **không phải để cuối**, dù đề bài không yêu cầu.

Vì `docs/api-spec.md` đã chốt đủ đầy đủ trước khi code, nên dựng giao diện với **dữ liệu giả** được ngay ở tuần 2, không phải chờ API xong. Sang tuần 3 nối vào API thật.

Nếu để cuối sẽ hỏng đúng tuần 3–4 — đó là phần đo lường và kiểm thử, phần được chấm nhiều nhất.

**Hệ quả:**
- Chừa sẵn CORS và phân trang trong API ngay từ tuần 1, nếu không sau này phải sửa lại.
- Chia 4 màn hình: người Thành làm 3 (đăng nhập, danh sách bác sĩ, đặt lịch), người Đông làm 1 (xem lịch của tôi).
- Vì là phần tự thêm nên cắt được. Thứ tự cắt: xem lịch của tôi → đặt lịch → danh sách bác sĩ. Trang đăng nhập giữ lại vì không có nó thì demo qua trình duyệt rất khó.
- Không đụng tuần 4.

**Cách trả lời khi GV hỏi "tại sao làm giao diện khi đề bài không yêu cầu":** đề bài không yêu cầu phần này, nên em coi đó là phần bổ sung cho sản phẩm chứ không tính vào phần bắt buộc. Em làm ở tuần 2 vì đặc tả API đã chốt xong nên dựng được giao diện với dữ liệu giả ngay, không phải chờ API. Nếu thiếu thời gian thì bỏ được mà không ảnh hưởng phần bắt buộc.

---

## Q8. Bucket Prometheus khai báo tay

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** đo P95 latency có đáng tin không?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Dùng bucket mặc định | Không cần cấu hình | Bucket cuối 10 giây, quá thô so với ngưỡng SLO 200ms. P95 tính ra không phản ánh thật |
| **Khai báo bucket tùy chỉnh quanh 200ms** | Đo đúng vùng quan tâm | Phải chọn mốc cẩn thận |

**Quyết định:** `buckets = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)`

**Lý do:** các mốc tập trung quanh 0.2s vì đó là ngưỡng SLO của Booking. Đo được chi tiết ở đúng vùng cần kiểm tra.

**Hệ quả:** nếu sau này SLO đổi, phải khai báo lại bucket. Nhớ cập nhật cả 4 service cho khớp.

**Cách trả lời khi GV hỏi:** Prometheus tính P95 bằng cách cộng dồn số request vào các bucket. Bucket mặc định thô quá so với ngưỡng 200ms nên phải khai báo mốc tùy chỉnh, nếu không con số P95 không phản ánh thật.

---

## Q9. Một instance PostgreSQL, mỗi service một database

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** đề bài yêu cầu database-per-service. Hiểu thế nào cho đúng?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| 4 instance PostgreSQL | Độc lập thật | Tốn 4× RAM, nặng khi demo trên laptop |
| **1 instance, mỗi service 1 database** | Đúng nghĩa đề bài, tốn 1× RAM | Một instance chết thì tất cả chết |
| 1 instance, mỗi service 1 schema | Nhẹ nhất | Vi phạm nghĩa database-per-service |

**Quyết định:** 1 instance, mỗi service 1 database (không phải schema).

**Lý do:** đúng nghĩa đề bài mà vẫn tiết kiệm tài nguyên.

**Hệ quả:** không đạt độc lập thật sự. Đây là đánh đổi biết trước.

**Cách trả lời khi GV hỏi:** trong thực tế mỗi service một instance riêng, đồ án gộp để chạy được trên laptop. Đây là đánh đổi giữa tính đúng đắn của kiến trúc và khả năng demo trong điều kiện đồ án.

---

## Q10. Không dùng Airflow

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** có nên dùng Airflow để quản lý job định kỳ không?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| Cron của hệ điều hành | Không tốn tài nguyên | Không biết job chạy xong chưa, không retry, không quan sát được |
| **APScheduler trong service** | Nhẹ, đủ dùng, không thêm service | Không quản lý được quan hệ phụ thuộc giữa các job |
| Airflow | Quản lý dependency, retry, backfill, có giao diện web | Cần vài GB RAM, 1 job thì quá nặng |

**Quyết định:** không cần job định kỳ nào. Notification xử lý event liên tục từ hàng đợi, không có job theo lịch.

**Lý do:** quyết định này rút gọn hơn dự kiến — không có bài toán "nhiều pipeline phụ thuộc nhau" để giải, nên Airflow không có lý do tồn tại trong dự án này.

**Hệ quả:** nếu sau này thêm báo cáo định kỳ thì mới cần cân nhắc. Lúc đó bắt đầu bằng APScheduler trong service, chuyển Airflow khi có nhiều pipeline.

---

## Q11. Toàn bộ phần hạ tầng do một người giữ

**Ngày:** 2026-10-11 · **Trạng thái:** đã chốt

**Vấn đề:** chia docker-compose, Alembic, script seed cho 3 người hay gộp lại một người?

**Đã cân nhắc:**

| Cách | Ưu | Nhược |
|---|---|---|
| **Một người giữ hết** | Thống nhất, không lệch phiên bản. Làm sớm xong sớm | Người đó bị chặn, phải biết Docker trước cả nhóm |
| Chia 3 người | Không ai gánh nhiều | 3 bản compose khác nhau, ghép không nổi. Hoặc 1 người viết 2 phần, còn 2 người sửa của người đó |

**Quyết định:** một người giữ toàn bộ: docker-compose, Alembic cho cả 4 database, script seed, biến môi trường, health check, mã định danh request, cấu hình connection pool.

**Lý do:** đây là phần **chặn tiến độ của cả nhóm**. Tuần 1 nếu compose không chạy được thì không ai test được gì. Chia ra sẽ tạo 3 phiên bản khác nhau rồi mất thời gian ghép — tốn hơn là dồn.

**Hệ quả và rủi ro:**
- Phần hạ tầng phải xong **trước ngày hết tuần 1**, nếu không cả nhóm trễ.
- Nếu không kịp, báo nhóm sớm để giảm phần khác — đừng im lặng giữ mình.
- Bù lại, người giữ hạ tầng thì hai người còn lại nhận thêm phần khác để cân bằng.

**Cách trả lời khi GV hỏi về cách chia việc:** phần hạ tầng do một người phụ trách vì đây là phần chặn tiến độ chung — tuần đầu nếu phần đóng gói chưa chạy được thì các thành phần khác đều không kiểm thử được. Tập trung một người làm giúp mọi thứ dùng chung nhất quán, tránh mỗi người một phiên bản khác nhau.

---

## Mẫu ghi chú mới

Khi có quyết định mới, thêm theo mẫu trên vào cuối file.

Hai loại đáng ghi nhất:

- **Đã chốt** — có lý do để giải thích với GV
- **Đã thử rồi bỏ** — để không ai thử lại lần nữa. Rất có giá trị khi GV hỏi "em có thử cách khác không"

Sau khi demo xong, bổ sung phần kết quả thực tế:

```markdown
## Q<n>. Kết quả thực tế sau khi đo

**Điểm gãy SLO Booking:** ... RPS (thay vì ước lượng ...)
**Nguyên nhân:** hết connection pool
**Sau khi scale 3 bản:** ...
**Có gì ngoài dự kiến:** ...
```

Phần này giá trị cao nhất khi bảo vệ đồ án, vì cho thấy số liệu là đo thật chứ không phải ước lượng.
