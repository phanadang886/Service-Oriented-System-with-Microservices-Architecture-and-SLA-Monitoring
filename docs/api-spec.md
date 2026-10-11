# Đặc tả API

> Chốt trước khi code. Cả 3 người đọc file này, không ai tự suy diễn endpoint.
> Nếu cần đổi, báo cả nhóm trước — đừng tự đổi rồi mới nói.

---

## Quy ước chung

**Base URL qua gateway:**

```
http://localhost/api/{service}
```

| Service | Tiền tố | Cổng nội bộ |
|---|---|---|
| Auth | `/api/auth` | 8001 |
| Catalog | `/api/catalog` | 8002 |
| Booking | `/api/booking` | 8003 |
| Notification | `/api/notification` | 8004 |

**Kiểu dữ liệu:** JSON, UTF-8.

**Xác thực:** mọi endpoint (trừ `register` và `login`) cần header:

```
Authorization: Bearer <token>
```

**Mã lỗi chuẩn:**

| Mã | Ý nghĩa |
|---|---|
| 400 | Dữ liệu gửi lên sai định dạng |
| 401 | Chưa đăng nhập, hoặc token hết hạn |
| 403 | Đã đăng nhập nhưng không có quyền |
| 404 | Không tìm thấy |
| 409 | Xung đột dữ liệu — ví dụ khung giờ đã có người đặt |
| 422 | Dữ liệu sai định dạng (FastAPI tự trả về) |
| 500 | Lỗi server |

**Định dạng lỗi trả về — dùng chung cho mọi service:**

```json
{
  "detail": "Khung giờ này đã có người đặt",
  "code": "SLOT_TAKEN"
}
```

Trường `code` là mã ngắn gọn để frontend và test xử lý, không phải đọc chuỗi tiếng Việt.

**Phân trang — mọi endpoint trả về danh sách:**

```
?page=1&limit=20
```

Response:

```json
{
  "items": [...],
  "total": 245,
  "page": 1,
  "limit": 20
}
```

Không phân trang thì sẽ có lúc API trả 5000 bác sĩ một lệnh.

**Mã định danh request:** client gửi kèm header `X-Request-ID`, server ghi lại vào log. Nếu client không gửi thì server tự sinh. Giá trị này đi qua cả 4 service.

---

## Service 1 — Auth

Cổng 8001. Phụ trách: **người Thành**.

### POST `/api/auth/register`

```json
{
  "email": "nam@example.com",
  "password": "matkhau123",
  "full_name": "Nguyễn Văn Nam",
  "role": "PATIENT"
}
```

`role` chỉ nhận `PATIENT` hoặc `DOCTOR`. Không cho tự đặt `ADMIN`.

Response `201`:
```json
{
  "id": "uuid",
  "email": "nam@example.com",
  "full_name": "Nguyễn Văn Nam",
  "role": "PATIENT",
  "created_at": "2026-10-11T08:00:00Z"
}
```

Lỗi `409` nếu email đã tồn tại, code `EMAIL_EXISTS`.

### POST `/api/auth/login`

```json
{
  "email": "nam@example.com",
  "password": "matkhau123"
}
```

Response `200`:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "role": "PATIENT"
  }
}
```

Lỗi `401` code `INVALID_CREDENTIALS`. Cố ý trả chung thông báo cho sai email và sai mật khẩu, không nói rõ cái nào sai — tránh lộ thông tin email nào đã đăng ký.

**Lưu ý demo:** cần có ít nhất 1 tài khoản `DOCTOR` và 1 `ADMIN` tạo sẵn bằng script seed, vì không có API đăng ký vai bác sĩ.

### GET `/api/auth/me`

Response `200`: giống hình người dùng ở `register`.

---

## Service 2 — Catalog

Cổng 8002. Phụ trách: **người Thành**. Đọc nhiều, có cache Redis.

### GET `/api/catalog/departments`

```json
{
  "items": [
    { "id": "uuid", "name": "Nội", "description": "Khoa Nội trưởng" }
  ],
  "total": 8, "page": 1, "limit": 20
}
```

### GET `/api/catalog/doctors`

Tham số lọc:

| Tham số | Kiểu | Ý nghĩa |
|---|---|---|
| `department_id` | uuid | Lọc theo khoa |
| `q` | string | Tìm theo tên |
| `page`, `limit` | int | Phân trang |

```json
{
  "items": [
    {
      "id": "uuid",
      "full_name": "BS. Trần Minh Nam",
      "title": "Tiến sĩ",
      "department": { "id": "uuid", "name": "Nội" },
      "price": 300000
    }
  ],
  "total": 62, "page": 1, "limit": 20
}
```

**Cache:** kết quả cache trong Redis 5 phút. Khi `POST`/`DELETE` bác sĩ hoặc khung giờ, phải xoá cache liên quan — không xoá thì người dùng thấy dữ liệu cũ tối đa 5 phút.

### GET `/api/catalog/doctors/{doctor_id}/slots`

Trả về các khung giờ còn trống.

```json
{
  "items": [
    {
      "id": "uuid",
      "doctor_id": "uuid",
      "start_time": "2026-10-12T09:00:00Z",
      "end_time": "2026-10-12T09:30:00Z",
      "is_available": true
    }
  ],
  "total": 8, "page": 1, "limit": 20
}
```

**Lưu ý thiết kế:** `is_available` ở đây là **gợi ý**, không phải cam kết. Khung giờ có thể còn trống lúc này nhưng người khác đặt mất 1 giây sau. Chỉ `booking` mới quyết định thật. Nói rõ điều này trong tài liệu API để không ai hiểu nhầm.

### POST `/api/catalog/doctors` (chỉ ADMIN)

```json
{
  "full_name": "BS. Lê Thị Hồng",
  "title": "Thạc sĩ",
  "department_id": "uuid",
  "price": 250000
}
```

### POST `/api/catalog/doctors/{doctor_id}/slots` (chỉ ADMIN)

```json
{
  "start_time": "2026-10-12T09:00:00Z",
  "end_time": "2026-10-12T09:30:00Z"
}
```

Lỗi `409` nếu khung giờ chồng lấn, code `SLOT_OVERLAP`.

---

## Service 3 — Booking

Cổng 8003. Phụ trách: **người Panh**. Nghiệp vụ chính, có xử lý tranh chấp.

### POST `/api/booking/appointments`

```json
{
  "doctor_id": "uuid",
  "slot_id": "uuid",
  "note": "Khám tái"
}
```

Response `201`:
```json
{
  "id": "uuid",
  "doctor_id": "uuid",
  "slot": {
    "id": "uuid",
    "start_time": "2026-10-12T09:00:00Z"
  },
  "status": "CONFIRMED",
  "created_at": "2026-10-11T08:00:00Z"
}
```

**Xử lý tranh chấp — phần quan trọng nhất của service này:**

Thứ tự xử lý:
1. Kiểm tra người dùng đã đăng nhập, không phải ADMIN
2. Kiểm tra khung giờ có tồn tại, chưa qua thời gian
3. Thêm dòng `status = 'CONFIRMED'`
4. Nếu bước 3 bị database từ chối (vi phạm unique partial index) → trả `409`, code `SLOT_TAKEN`

**Không** kiểm tra "khung giờ còn trống không" rồi mới thêm. Hai request song song sẽ cùng thấy còn trống và cùng thêm, một cái bị database từ chối — đó là chuyện bình thường, xử lý bằng `409` là xong.

Sau khi tạo thành công thì **đẩy event vào hàng đợi Redis**, không gửi thông báo ngay trong request này. Nếu không có Notification service thì vẫn đặt lịch thành công.

### GET `/api/booking/appointments/my`

Danh sách lịch của người đang đăng nhập. Có phân trang. Lọc theo trạng thái nếu cần.

### GET `/api/booking/appointments/{appointment_id}`

Lỗi `404` nếu không tồn tại hoặc không thuộc về người đang đăng nhập — cả hai trả chung `404`, không phân biệt, tránh lộ việc lịch đó có tồn tại.

### PATCH `/api/booking/appointments/{appointment_id}/cancel`

```json
{ "reason": "Không thể đến" }
```

Chuyển trạng thái sang `CANCELLED`, đẩy event.

Lỗi `409` code `ALREADY_CANCELLED` nếu đã hủy rồi.

### GET `/api/booking/doctors/{doctor_id}/schedule`

Lịch của một bác sĩ, nhóm theo ngày.

---

## Service 4 — Notification

Cổng 8004. Phụ trách: **người Đông**.

Service này **nhận event qua hàng đợi**, không nhận endpoint tạo dữ liệu. Các endpoint dưới chỉ phục vụ **kiểm tra kết quả gửi thông báo**.

### GET `/api/notification/logs`

Danh sách thông báo đã gửi, để kiểm chứng trong lúc demo và test.

Tham số: `page`, `limit`, `event_type`

```json
{
  "items": [
    {
      "event_id": "uuid",
      "event_type": "appointment.created",
      "recipient_role": "PATIENT",
      "recipient_id": "uuid",
      "channel": "log",
      "status": "SENT",
      "attempts": 1,
      "created_at": "2026-10-11T08:00:00Z",
      "sent_at": "2026-10-11T08:00:02Z"
    }
  ],
  "total": 342, "page": 1, "limit": 20
}
```

`status` nhận: `SENT`, `FAILED`.

### GET `/api/notification/queue-health`

Trạng thái hàng đợi — dùng cho giám sát.

```json
{
  "events_in_queue": 0,
  "events_processed_last_hour": 342,
  "dead_letter_count": 2,
  "oldest_event_age_seconds": 0,
  "last_successful_run": "2026-10-11T08:00:02Z",
  "status": "healthy"
}
```

`status` nhận: `healthy`, `delayed` (hàng đợi tích tụ > 2 phút), `failing` (có event rơi vào dead letter).

### DELETE `/api/notification/logs/{event_id}` (chỉ ADMIN)

Xoá một bản ghi thông báo. Dùng để dọn dữ liệu giữa các lần chạy Locust.

---

## Nội bộ — không có endpoint, xử lý qua hàng đợi

**Event nhận từ Redis:**

```json
{
  "event_id": "uuid",
  "event_type": "appointment.created",
  "occurred_at": "2026-10-11T08:00:00Z",
  "payload": {
    "appointment_id": "uuid",
    "patient_id": "uuid",
    "patient_name": "Nguyễn Văn Nam",
    "patient_email": "nam@example.com",
    "doctor_id": "uuid",
    "doctor_name": "BS. Trần Minh Nam",
    "department_name": "Nội",
    "slot_id": "uuid",
    "start_time": "2026-10-12T09:00:00Z",
    "status": "CONFIRMED",
    "price": 300000
  }
}
```

| `event_type` | Khi nào phát ra | Gửi cho ai |
|---|---|---|
| `appointment.created` | Đặt lịch thành công | Bệnh nhân + bác sĩ |
| `appointment.cancelled` | Hủy lịch | Bệnh nhân + bác sĩ |

**Payload mang sẵn tên và email** để Notification không phải gọi sang service khác lấy lại. Đây là tranh chấp giữa tính độc lập của service và độ trễ.

**Quy tắc bắt buộc khi xử lý event:**

| Quy tắc | Cách làm |
|---|---|
| Event đến trùng | Bảng `notifications` có khóa `event_id` + `recipient_id`. Ghi bằng `INSERT ... ON CONFLICT DO NOTHING` |
| Event hỏng không parse được | Ghi vào bảng `dead_letter_events`, không chặn hàng đợi |
| Gửi thông báo lỗi tạm | **Không** xoá event khỏi hàng đợi. Để lần sau lấy lại thử |
| Xử lý xong | Mới xoá event khỏi hàng đợi |

**Vì sao có 2 bản ghi cho 1 event:** một event `appointment.created` gửi cho cả bệnh nhân lẫn bác sĩ. Khóa `event_id` đơn thuần sẽ chặn nhầm bản ghi thứ hai. Khóa phải là cặp `(event_id, recipient_id)`.

**Tầng gửi thông báo:** không tích hợp nhà cung cấp SMS thật. Gửi bằng cách ghi log mức `INFO` và lưu vào bảng `notifications`. Kịch bản Locust kiểm tra bảng này.

---

## Định dạng token

Header JWT chứa:

| Trường | Nội dung |
|---|---|
| `sub` | id người dùng (uuid) |
| `role` | `PATIENT` / `DOCTOR` / `ADMIN` |
| `exp` | hết hạn sau 1 giờ |
| `iat` | thời điểm phát |

Khóa ký đọc từ biến môi trường, không viết trong code.

---

## Thứ tự làm

Làm theo thứ tự này vì sau làm trước sẽ phải sửa:

1. **Auth** — vì mọi service khác đều cần xác thực
2. **Catalog** — vì Booking cần kiểm tra slot có tồn tại không
3. **Booking** — phần tranh chấp, khó nhất trong 3 API service
4. **Notification** — chỉ bắt đầu khi Booking đã đẩy event ổn định
5. Gộp qua gateway, kiểm tra toàn bộ chạy được

**Hạ tầng phải xong trước tuần 2:** docker-compose, Alembic cho cả 4 database, script tạo dữ liệu giả. Không có ba thứ này thì không service nào test được.

---

## Phạm vi phụ trách của người Panh

Ngoài Booking Service, người Panh giữ toàn bộ phần hạ tầng dưới đây. Những phần này ảnh hưởng đến cả 4 service nên phải thống nhất trước khi ai code:

| Hạng mục | Nội dung cần chốt |
|---|---|
| **docker-compose.yml** | 8 container: nginx, 4 service, postgres, redis, prometheus, grafana. Không khai báo `container_name` cho service cần scale |
| **Alembic** | 4 database riêng: `auth_db`, `catalog_db`, `booking_db`, `notification_db`. Mỗi service có thư mục migration riêng |
| **Script seed** | Khoa, bác sĩ, khung giờ, lịch hẹn giả. Có tham số `--reset` để nạp lại |
| **Biến môi trường** | Tên biến cho chuỗi kết nối database, khóa ký JWT, cổng chạy. Không viết cứng trong code |
| **Health check** | Mẫu `/health` để cả 4 service copy, khai báo `depends_on: service_healthy` |
| **Mã định danh request** | Header `X-Request-ID`, middleware ghi vào log, xuyên qua cả 4 service |
| **Cấu hình kết nối database** | `pool_size`, `max_overflow` — ghi rõ số đã chọn và số đã thử |

**Thứ tự ưu tiên trong tuần 1:** compose → Alembic → seed. Ba cái này chặn cả nhóm, làm xong người khác mới test được.

---

## Còn phải chốt

Các mục dưới đây chưa chốt, cần nhóm thống nhất:

| Câu hỏi | Vì sao cần chốt |
|---|---|
| Có cần API thanh toán không, hay bỏ? | Nếu có thì thêm nghiệp vụ, ảnh hưởng timeline |
| Bác sĩ có cần duyệt lịch không, hay đặt là xong? | Ảnh hưởng trạng thái `PENDING` / `CONFIRMED` |
| Token hết hạn 1 giờ có cần làm mới không? | Nếu có thì thêm endpoint refresh token |
| Giá khám có cố định không, hay đổi theo khung giờ? | Ảnh hưởng bảng Catalog |

Với timeline 3–4 tuần, khuyến nghị **bỏ thanh toán** và **đặt là xong** — bỏ bớt nghiệp vụ để kịp đúng hạn.
