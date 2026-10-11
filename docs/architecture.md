# Kiến trúc và quyết định thiết kế

> Sơ đồ và lý do. Dùng khi GV hỏi "vì sao làm thế", hoặc khi thành viên mới cần hiểu hệ thống.

---

## 1. Sơ đồ tổng thể

```
╔══════════════════════════════════════════════════════════════════╗
║                        NGOÀI HỆ THỐNG                            ║
║   Người dùng / Swagger UI / Locust                              ║
╚═════════════════════════════╤════════════════════════════════════╝
                              │ HTTP :80
╔═════════════════════════════▼════════════════════════════════════╗
║                      API GATEWAY (Nginx)                         ║
║   • Định tuyến /api/auth/*, /api/catalog/*, ...                  ║
║   • Rate limiting theo IP                                        ║
║   • KHÔNG verify JWT (Nginx không làm được sẵn)                 ║
╚═══╤═════════════╤═════════════╤═════════════╤════════════════╝
    │             │             │             │
╔═══▼═════════╗ ╔═▼══════════╗ ╔▼═══════════╗ ╔▼═══════════════╗
║    AUTH      ║ ║  CATALOG   ║ ║  BOOKING   ║ ║  NOTIFICATION  ║
║             ║ ║            ║ ║            ║ ║                 ║
║ • register  ║ ║ • khoa     ║ ║ • đặt lịch ║ ║ • đọc event    ║
║ • login     ║ ║ • bác sĩ    ║ ║ • hủy lịch ║ ║ • gửi thông    ║
║ • phát JWT  ║ ║ • khung giờ║ ║ • chặn trùng║ ║   báo          ║
║             ║ ║            ║ ║            ║ ║ • retry lỗi    ║
║ →Redis cache ║ ║           ║ ║            ║ ║                 ║
╚═══╤═════════╝ ╚═╤══════════╝ ╚╤═══════════╝ ╚╤═══════════════╝
    │             │             │                │
╔═══▼═══════╗ ╔══▼═══════╗ ╔══▼════════╗      │
║ auth_db   ║ ║ catalog_db║ ║ booking_db║      │
╚═══════════╝ ╚═══════════╝ ╚═══════════╝      │
                                            │ đặt/hủy lịch
                                            │ đẩy event
                                    ╔══════════▼════════╗
                                    │   REDIS           ║
                                    │   hàng đợi        ║
                                    └══════════╤════════╘
                                               │
                                    ╔══════════▼═════════╗
                                    ║   NOTIFICATION     ║
                                    │                    ║
                                    │  ghi log + bảng    ║
                                    │  notifications     ║
                                    └──────────┬─────────┘
                                               │
                                    ┌──────────▼─────────┐
                                    │ notification_db    │
                                    │ notifications      │
                                    │ dead_letter_events │
                                    └────────────────────┘

╔══════════════════════════════════════════════════════════════════╗
║                   GIÁM SÁT (chạy độc lập)                        ║
║   Prometheus  ──scrape /metrics──►  cả 4 service                ║
║      │                                                            ║
║      ▼                                                            ║
║   Grafana (dashboard SLO)                                         ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 2. Vì sao tách thành 4 service

Đề bài yêu cầu tối thiểu 4 service. Trong 4 service, chọn chia theo **ranh giới nghiệp vụ** thay vì chia cho đủ số:

| Service | Lý do tách riêng |
|---|---|
| **Auth** | Mọi service khác đều cần xác thực. Tách ra để logic băm mật khẩu và phát token chỉ nằm ở một chỗ |
| **Catalog** | Dữ liệu tĩnh, đọc nhiều, không thay đổi trong ngày. Tách ra để cache riêng và không ảnh hưởng khi tải đặt lịch tăng |
| **Booking** | Ghi dữ liệu, có tranh chấp, cần cô lập để tải ghi không làm chập các service chỉ đọc |
| **Notification** | Chạy nền, ghi nhiều, không nên trong đường đi của request đặt lịch |

**Điểm quan trọng:** Notification tách riêng vì nó **viết và xử lý lâu**. Nếu gửi thông báo ngay trong request đặt lịch, người dùng phải chờ, và khi bên gửi lỗi thì việc đặt lịch cũng chậm theo.

---

## 3. Database-per-service

Mỗi service một database riêng, không service nào truy cập database của service khác.

**Lợi ích:**
- Service này chết thì service kia không chết theo
- Truy vấn nặng ở service này không khóa bảng của service kia
- Mỗi service tự tối ưu schema của mình

**Hệ quả bắt buộc phải xử lý:** dữ liệu cần chuyển giữa các service thì phải qua hàng đợi, không truy cập chéo database.

| Dữ liệu cần chuyển | Cách chuyển |
|---|---|
| Booking → Notification | Đẩy event vào Redis |

**Điểm cần nói rõ:** Catalog và Booking không gọi nhau trực tiếp. Khi đặt lịch, client gửi kèm `doctor_id` và `slot_id`; Booking tin rằng client đã lấy danh sách từ Catalog, và **ràng buộc khóa ngoại ở tầng database là thứ bảo vệ thật**.

**Cách này có đánh đổi:** Booking không tự kiểm tra được slot có hợp lệ không. Nếu GV hỏi sâu, trả lời thẳng đây là đánh đổi giữa tính nhất quán tức thời và độ độc lập của service — hai thứ không thể có cùng lúc trong kiến trúc vi dịch vụ.

---

## 4. Hàng đợi Redis

### 4.1 Vì sao dùng hàng đợi

Nếu Booking tự gửi thông báo trong request, thì khi Notification chậm 3 giây, người dùng đặt lịch phải chờ 3 giây mới thấy "thành công" — trong khi việc đặt lịch đã xong từ trước.

Có hàng đợi thì:
- Booking đẩy event xong đi tiếp, trả về cho người dùng ngay
- Notification lấy event ra xử lý sau
- Notification chết thì việc đặt lịch vẫn chạy bình thường

### 4.2 Vì sao chọn Redis Streams, không phải Pub/Sub

| | Pub/Sub | Streams |
|---|---|---|
| Message đã gửi mà chưa ai nhận | Mất luôn | Còn trong danh sách chờ |
| Đọc lại message cũ | Không được | Được, có index |
| Xác nhận đã xử lý | Không có | Có |
| Nhiều consumer cùng đọc | Mỗi cái nhận 1 bản | Có thể chọn nhóm consumer |

**Lý do chính: Pub/Sub mất message nếu Notification đang tắt.** Khi Notification khởi động lại, những lịch hẹn xảy ra lúc đó sẽ biến mất — không có thông báo, và không ai biết là đã mất.

Streams giữ message cho tới khi consumer xác nhận đã xử lý.

### 4.3 Nguyên tắc xử lý

```
Booking: tạo appointment thành công → đẩy event vào stream → trả về người dùng
Notification: đọc event → gửi thông báo → XỬ LÝ THÀNH CÔNG thì mới xác nhận (ack)
```

**Quy tắc bất di bất dịch: chỉ ack khi xử lý thành công.**

| Tình huống | Xử lý |
|---|---|
| Xử lý xong | Ack |
| Gửi lỗi tạm (mất mạng) | **Không ack.** Để lần sau lấy lại thử. Vì đã idempotent nên thử lại không sinh kết quả sai |
| Event hỏng không parse được | Ghi vào `dead_letter_events`, ack để không chặn cả hàng đợi |
| Notification chết giữa chừng | Không ack → event được giao lại cho instance khác xử lý |

### 4.4 Idempotent — vì sao bắt buộc

Vì nguyên tắc at-least-once, event chắc chắn sẽ có lúc bị xử lý nhiều lần. Không có idempotent thì sẽ gửi trùng thông báo cho người dùng.

Cách làm: bảng `notifications` có khóa phức hợp `(event_id, recipient_id)`, ghi bằng:

```sql
INSERT INTO notifications (event_id, recipient_id, ...)
VALUES (...)
ON CONFLICT (event_id, recipient_id) DO NOTHING;
```

**Vì sao khóa phức hợp chứ không phải `event_id` đơn thuần:** một event `appointment.created` gửi cho cả bệnh nhân lẫn bác sĩ — tức là 2 bản ghi. Nếu khóa chỉ `event_id`, bản ghi thứ hai sẽ bị coi là trùng và bị bỏ qua. Khóa phải phân biệt được từng người nhận.

---

## 5. Cache Redis cho Catalog

### 5.1 Vì sao cache

Danh sách bác sĩ và khung giờ được đọc nhiều (mọi người mở trang đặt lịch đều cần) nhưng thay đổi ít. Cache giảm tải cho database.

### 5.2 Rủi ro — dữ liệu cũ

Cache TTL 5 phút nghĩa là dữ liệu có thể cũ tối đa 5 phút. Đây là đánh đổi được chấp nhận: danh sách bác sĩ không cần cập nhật tức thời.

**Điều bắt buộc:** khi thêm/xoá bác sĩ hoặc khung giờ, phải xoá cache liên quan. Nếu không, người dùng thấy danh sách cũ tới hết TTL — GV có thể hỏi và bắt lỗi này.

### 5.3 Cần cache không?

Nếu làm xong mà thấy Locust đo Catalog vẫn đạt P95 < 80ms dễ dàng thì bỏ cache cũng được. Nhưng Redis vốn đã dùng cho hàng đợi nên giữ, và nói rõ trong báo cáo: cache dùng để đạt SLO dưới tải cao, không phải để cho có.

---

## 6. Chặn tranh chấp — vì sao ở tầng database

### 6.1 Vấn đề

Hai người cùng đặt khung giờ 9:00. Phải chỉ một trong hai thành công.

### 6.2 Cách làm

```sql
CREATE UNIQUE INDEX uniq_active_slot ON appointments(slot_id)
WHERE status = 'CONFIRMED';
```

### 6.3 Vì sao đặt ở database, không ở code

| Kiểm tra ở code | Ràng buộc ở database |
|---|---|
| "Slot còn trống không? → thêm" | "Thêm, để database quyết định" |
| 2 request cùng đọc "còn trống" rồi cùng thêm | Một cái bị từ chối, không cần logic nào |
| Ai viết code mới cũng phải nhớ kiểm tra | Ai viết gì cũng không bỏ qua được |
| Kiểm tra và thêm không cùng lúc được thì sai | Luôn đúng |

Cách làm ở code chỉ đúng khi kiểm tra và ghi nằm trong cùng một transaction khoá dòng. Nhưng khi đó bị chậm, và phải nhớ khoá đúng thứ tự.

### 6.4 Xử lý trong API

```python
try:
    appointment = create_appointment(...)
except IntegrityError:
    raise HTTPException(409, detail="Khung giờ này đã có người đặt",
                        headers={"X-Error-Code": "SLOT_TAKEN"})
```

Không cần bắt lỗi `UniqueViolation` cụ thể — bắt rộng hơn cũng được, nhưng bắt cụ thể thì dễ đọc hơn.

---

## 7. Sơ đồ database Notification

```
notification_db
├── notifications            ← mỗi dòng là 1 lần gửi cho 1 người nhận
│   ├── (event_id, recipient_id)  PK    khóa phức hợp, chống gửi trùng
│   ├── event_type            created / cancelled
│   ├── recipient_role        PATIENT / DOCTOR
│   ├── recipient_id
│   ├── recipient_contact     email, đã copy trong event
│   ├── channel               "log"
│   ├── status                SENT / FAILED
│   ├── attempts              số lần đã thử gửi
│   ├── payload_snapshot      lưu lại nội dung đã gửi
│   ├── created_at            thời điểm nhận event
│   └── sent_at               thời điểm gửi thành công
│
└── dead_letter_events        ← event hỏng, chờ xử lý tay
    ├── event_id
    ├── raw_payload
    ├── error_message
    └── failed_at
```

### 7.1 Vì sao lưu `payload_snapshot`

Sau khi gửi, nội dung thông báo có thể cần đối chiếu: ai nhận, nhận nội dung gì, lúc nào. Lưu lại snapshot giúp trả lời được mà không cần tìm lại event đã bị xoá khỏi hàng đợi.

### 7.2 Vì sao có `attempts`

Để thấy event nào phải thử gửi nhiều lần. Chỉ số này cho thấy tỷ lệ lỗi tạm trong lúc chạy — là căn cứ để nói "cơ chế retry hoạt động".

---

## 8. Giám sát

### 8.1 Luồng

```
4 service ──GET /metrics──► Prometheus ──query──► Grafana
```

`prometheus-fastapi-instrumentator` tự động xuất: số request, độ trễ (theo bucket), tỷ lệ lỗi theo mã.

### 8.2 Bucket tùy chỉnh

```python
buckets = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)
```

Mốc tập trung quanh 200ms vì đó là ngưỡng SLO của Booking. Mốc mặc định (0.005 → 10s) quá thô, tính P95 sẽ cho kết quả không phản ánh thật.

### 8.3 Chỉ số riêng cho hàng đợi

| Chỉ số | Nguồn | Ý nghĩa |
|---|---|---|
| `notification_events_processed_total` | Đếm trong code | Tổng event đã xử lý |
| `notification_dead_letter_total` | Đếm trong code | Event hỏng |
| `notification_attempts_total` | Đếm trong code | Tổng số lần thử gửi |
| `redis_queue_length` | Query Redis | Hàng đợi có đang tích tụ không |

Hàng đợi tích tụ liên tục là dấu hiệu Notification chậm hơn Booking — cần cảnh báo.

### 8.4 Điểm mù cần tránh

Nếu giám sát 4 service mà không đo Nginx thì sẽ không thấy được:
- Timeout do Nginx đặt ra
- Hết worker
- Hết connection

Nginx là nơi **toàn bộ** request đi qua. Nếu nó là nút thắt mà không đo thì sẽ mất thời gian tìm nhầm ở service khác.

Thêm exporter cho Nginx. Vài dòng cấu hình.

---

## 9. Sơ đồ Docker Compose

```
docker-network
├── nginx            (8080 → 80)   reverse proxy
├── auth-service     (8001)
├── catalog-service  (8002)
├── booking-service  (8003)
├── notification-service (8004)
├── redis            (6379)        cache + hàng đợi
├── postgres         (5432)        4 database
├── prometheus       (9090)
└── grafana          (3000)
```

**Lưu ý:** đề bài nói database-per-service. Dùng **1 instance Postgres + mỗi service 1 database**. Vừa đúng đề bài, vừa đỡ tốn RAM khi demo.

Nếu GV hỏi về độc lập thực sự, trả lời: trong thực tế mỗi service một instance Postgres riêng, đồ án gộp để tiết kiệm tài nguyên máy — đánh đổi đã biết trước.

**Không khai báo `container_name`** cho các service cần scale, nếu không `--scale` sẽ báo lỗi.

---

## 10. Quyết định từ chối

Ghi lại để không ai đề xuất lại:

| Đề xuất | Lý do từ chối |
|---|---|
| Verify JWT ở Nginx | Cần `njs`/`lua`, compose thuần không có. Verify ở service chấp nhận lặp |
| `SELECT ... FOR UPDATE` | Chậm hơn, dễ viết sai thứ tự. Unique index đơn giản và chắc |
| `deploy: replicas` | Cú pháp Swarm, compose bỏ qua |
| Pub/Sub thay Streams | Mất message khi consumer tắt |
| Gửi SMS thật | Cần tài khoản nhà cung cấp và có phí. Mô phỏng bằng ghi log |
| Next.js cho frontend | Đề bài không yêu cầu, timeline không đủ |
| Phân tích dữ liệu / báo cáo tổng hợp | Không thuộc 9 yêu cầu bắt buộc, mất ít nhất 1 tuần |
| Airflow, Kafka, Spark | Quá nặng cho quy mô này |
| Máy học trong báo cáo tải | Chỉ cần tổng hợp và so sánh, không cần dự báo |
