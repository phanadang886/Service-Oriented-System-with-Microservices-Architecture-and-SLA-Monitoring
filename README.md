# Hệ thống đặt lịch khám — Vi dịch vụ và giám sát SLO

> Môn: Khoa học Dịch vụ
> Hướng: Backend / Platform
> Nhóm: 3 người
> Thời gian: 3–4 tuần

**Tên đề tài chính thức — dùng đúng chuỗi này, không đổi:**

> Thiết kế hệ thống dịch vụ theo kiến trúc microservices kèm giám sát SLA

**Tên tiếng Anh — dùng trong CV và khi trình bày bằng tiếng Anh:**

> Designing a Service-Oriented System with Microservices Architecture and SLA Monitoring

Nghiệp vụ "đặt lịch khám" là ví dụ triển khai, chỉ dùng để minh hoạ trong phần mở đầu.

---

## 1. Bài toán

Hệ thống đặt lịch khám bệnh trực tuyến: bệnh nhân xem bác sĩ, chọn khung giờ, đặt lịch, hủy lịch. Bác sĩ xem lịch của mình. Hệ thống gửi thông báo cho cả hai bên.

**Vì sao chọn nghiệp vụ này:** nó có bài toán tranh chấp dữ liệu thật — hai bệnh nhân cùng đặt một khung giờ — để kiểm chứng khả năng bảo đảm tính đúng đắn của hệ thống. Mấy bài toán tối ưu khác trong đề không có.

Có 3 bài toán khó thật, mỗi bài gắn với 1 phần kỹ thuật cần học:

| Bài toán | Vì sao khó | Kỹ thuật dùng để giải |
|---|---|---|
| 2 người cùng đặt 1 khung giờ | Phải chặn được, không được cả hai đều thành công | Ràng buộc unique partial index ở tầng database |
| Thông báo gửi lỗi, hoặc event đến trùng | Xử lý lỗi mà không mất dữ liệu, không gửi trùng | Hàng đợi Redis, retry, xử lý idempotent |
| Báo cáo vị trí nghẽn khi tải lên | Phải đo được chứ không ước lượng | Prometheus + Grafana, kiểm thử chịu tải bằng Locust |

Chọn nghiệp vụ này vì nó có bài toán thật để giải. Khi bảo vệ đồ án, có câu chuyện để nói thay vì chỉ khoe biết lắp tool.

---

## 2. Kiến trúc

```
     [Người dùng / Swagger UI / Locust]
                    │
                    ▼  (cổng 80)
            ┌───────────────┐
            │  API Gateway  │   Nginx
            │  định tuyến + │
            │  chống spam   │
            └───────┬───────┘
    ┌─────────────────┼─────────────────┐
    ▼                 ▼                 ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│  Auth     │   │  Catalog  │   │  Booking  │
│  Service  │   │  Service  │   │  Service  │
└─────┬─────┘   └─────┬─────┘   └─────┬─────┘
      │               │               │
[Postgres Auth] [Postgres Cat] [Postgres Book]
                              đặt/hủy lịch
                                    │
                              đẩy event
                                    ▼
                              ┌──────────┐
                              │  Redis   │  hàng đợi
                              └────┬─────┘
                                   │
                                   ▼
                            ┌─────────────┐
                            │ Notification│
                            │  Service    │
                            └──────┬──────┘
                                   │
                          [Postgres Notification]

[Giám sát - chạy độc lập]:
Prometheus (đọc /metrics của 4 service) ──► Grafana
```

### Giải thích các từ

- **Vi dịch vụ (microservice)**: tách hệ thống thành nhiều chương trình nhỏ, mỗi cái một việc, chạy độc lập. Ở đây 4 chương trình.
- **API Gateway (cổng vào)**: một cửa duy nhất cho mọi request từ bên ngoài. Nó dẫn đường `/api/auth/...` về đúng service. Người dùng không thấy 4 service riêng biệt.
- **Database-per-service**: mỗi service có database riêng, không dùng chung. Service A chết thì service B không bị ảnh hưởng.
- **Hàng đợi (queue)**: danh sách chờ. Booking đẩy thông tin vào đó rồi đi tiếp việc khác, không chờ. Notification lấy ra xử lý sau.
- **Idempotent**: làm lại nhiều lần thì kết quả y hệt lần đầu, không nhân bản dữ liệu.
- **SLO**: con số hứa trước về chất lượng dịch vụ, ví dụ "95% request dưới 200ms".

---

## 3. 4 service

### Service 1 — Auth

Xử lý tài khoản và xác thực người dùng.

- Đăng ký, đăng nhập
- Mật khẩu lưu dạng băm (bcrypt), không lưu dạng gốc
- Phát token JWT sau khi đăng nhập thành công
- Database `auth_db`: bảng `users`, `roles`

### Service 2 — Catalog

Danh mục dữ liệu tĩnh, đọc nhiều ít thay đổi: khoa, bác sĩ, khung giờ, bảng giá.

- Danh sách bác sĩ, lọc theo khoa
- Khung giờ khám của bác sĩ
- Database `catalog_db`: bảng `departments`, `doctors`, `time_slots`

Phần này được cache bằng **Redis** (mục 5.2) vì cùng một danh sách bác sĩ được hỏi nhiều lần mà ít khi thay đổi.

### Service 3 — Booking

Nghiệp vụ chính: đặt lịch, hủy lịch, xem lịch đã đặt.

- Database `booking_db`: bảng `appointments` với trạng thái `PENDING` / `CONFIRMED` / `CANCELLED`
- **Chặn đặt trùng bằng ràng buộc ở tầng database** (mục 5.1)
- Đặt lịch thành công thì **đẩy event vào Redis**, không gửi thông báo ngay

### Service 4 — Notification

Nhận event từ Redis và gửi thông báo cho bệnh nhân và bác sĩ.

- Database `notification_db`: bảng `notifications`, `dead_letter_events`
- Xử lý event đến trùng, event hỏng, gửi lỗi tạm
- Tầng gửi thông báo được **mô phỏng**: ghi log và lưu bảng, không dùng dịch vụ SMS thật (mục 5.3)

**Vì sao chọn Notification thay vì làm báo cáo tổng hợp:** với 3–4 tuần, phải dồn thời gian cho 4 service cùng phần giám sát. Báo cáo tổng hợp không thuộc 9 yêu cầu bắt buộc của đề bài. Notification học được kỹ năng xử lý lỗi thật — thứ sinh viên ít được học vì đồ án thường làm đúng một lần rồi xong.

---

## 4. Công nghệ

### 4.1 FastAPI

Chọn vì:
- Nhanh, xử lý nhiều request cùng lúc tốt
- Hỗ trợ `async/await` — khi một service chờ đọc database thì vẫn nhận request khác được, không đứng yên
- Tự sinh trang tài liệu API (Swagger UI) — khi bảo vệ, mở ra là thầy thấy hết endpoint, không cần slide riêng

### 4.2 Nginx

- Đóng vai cổng vào, dẫn đúng đường về đúng service
- Giới hạn số request từ 1 IP để chống spam

### 4.3 Redis — 2 việc khác nhau, đều dùng thật

**Việc 1: cache cho Catalog Service.**
Danh sách bác sĩ, khoa, khung giờ được cache trong Redis với thời hạn sống 5 phút. Hết hạn thì lấy lại từ database và cập nhật cache.

Điều kiện để cache đúng: khi bác sĩ thêm/xoá khung giờ thì phải xoá cache liên quan, nếu không người dùng sẽ thấy dữ liệu cũ.

**Việc 2: hàng đợi cho Booking → Notification.**
Booking đặt lịch xong đẩy event vào Redis. Notification lấy event ra xử lý.

Nếu không dùng hàng đợi, mỗi lần đặt lịch phải chờ gửi thông báo xong mới trả về. Khi bên gửi lỗi, người dùng đặt lịch cũng chậm theo.

### 4.4 PostgreSQL

4 database riêng: `auth_db`, `catalog_db`, `booking_db`, `notification_db`.

Dùng **Alembic** để quản lý cấu trúc bảng. Lý do: nếu không có migration, database chỉ tồn tại trên máy bạn — GV muốn chạy lại hệ thống thì không có cách nào tạo được bảng. Câu hỏi vấn đáp "cấu trúc bảng do ai định nghĩa?" rất hay gặp.

### 4.5 Docker & Docker Compose

- Mỗi service 1 `Dockerfile`
- 1 `docker-compose.yml` bật toàn bộ hệ thống bằng một lệnh
- Tránh lỗi "chạy được trên máy anh chứ không chạy trên máy em"

### 4.6 Prometheus + Grafana

Dùng `prometheus-fastapi-instrumentator` để mỗi service tự xuất số liệu ở `/metrics`.

**Cấu hình bucket — bắt buộc, không có thì phần SLO là đo bằng mắt:**

Mặc định Prometheus có mốc đo độ trễ thô, mốc cuối cùng là 10 giây. Với ngưỡng SLO 200ms thì các mốc đó quá thô, không biết chính xác request có nhanh hơn 200ms không.

```python
buckets = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)
```

### 4.7 Locust

`locustfile.py` giả lập hàng trăm đến hàng nghìn người dùng, tăng dần để tìm điểm hệ thống chậm.

---

## 5. Ba bài toán khó và cách giải

### 5.1 Chặn đặt trùng khung giờ

**Bài toán:** 2 bệnh nhân cùng bấm đặt vào khung giờ 9:00 của bác sĩ Nam.

**Cách giải:** ràng buộc do database tự canh, không phải do code canh.

```sql
CREATE UNIQUE INDEX uniq_active_slot ON appointments(slot_id)
WHERE status = 'CONFIRMED';
```

**Đọc câu lệnh này:** trong bảng lịch hẹn, với mỗi khung giờ chỉ được có **tối đa một** dòng đang ở trạng thái `CONFIRMED`. Hai người cùng thêm thì một trong hai bị database từ chối.

**Vì sao tốt hơn `SELECT ... FOR UPDATE`:**

| | `FOR UPDATE` | Unique partial index |
|---|---|---|
| Có khoá dòng dữ liệu không | Có, chặn request khác cùng dòng | Không |
| Tốc độ | Chậm hơn khi tranh chấp nhiều | Nhanh hơn |
| Có cửa sổ thời gian mà 2 request cùng đọc trạng thái cũ không | Có, nếu viết sai thứ tự | Không, database tự chặn |
| Ai bảo vệ | Code | Database, ai viết code mới cũng không bỏ qua |

Cách này còn dùng để **demo**: cho 50 người cùng đặt 1 slot, số booking thành công đúng bằng 1.

Code phía API bắt lỗi `IntegrityError` rồi trả về `409 Conflict`.

### 5.2 Xử lý event lỗi, event trùng

**Bài toán:** Booking đẩy event vào hàng đợi. Notification lấy ra xử lý. Có ba chuyện có thể xảy ra:

1. Notification xử lý xong thì **chưa kịp xác nhận**, và bị khởi động lại → lấy lại event cũ, gửi 2 lần
2. Event bị hỏng (JSON sai, thiếu trường) → nếu xử lý hỏng thì hàng đợi bị chặn, không event nào chạy được nữa
3. Ghi vào database lỗi tạm (mất mạng) → không nên mất event

**Cách giải:**

| Tình huống | Xử lý |
|---|---|
| Event đến 2 lần | Bảng `notifications` có khóa chính `(event_id, recipient_id)`. Ghi bằng `INSERT ... ON CONFLICT DO NOTHING` — đến lần 2 thì bỏ qua |
| Event hỏng không đọc được | Tách ra ghi vào bảng `dead_letter_events`, không chặn cả hàng đợi |
| Ghi database lỗi tạm | Không xác nhận event. Lần sau lấy lại thử ghi lại — vì đã chốt idempotent nên ghi lại nhiều lần cũng không sao |

**Vì sao khóa là cặp `(event_id, recipient_id)` chứ không chỉ `event_id`:** một sự kiện đặt lịch gửi thông báo cho **hai người** — bệnh nhân và bác sĩ. Nếu khóa chỉ `event_id`, bản ghi của bác sĩ sẽ bị coi là trùng và bị bỏ qua. Khóa phải phân biệt được từng người nhận.

**Điểm cốt lõi:** chỉ cần xử lý thành công mới xác nhận event. Đây là nguyên tắc "at-least-once" — hệ thống đảm bảo event được xử lý ít nhất một lần, và bạn làm idempotent để xử lý nhiều lần không sinh ra kết quả sai.

Câu này dùng được khi phỏng vấn hỏi "làm sao đảm bảo không mất dữ liệu khi hệ thống chết giữa chừng?"

### 5.3 Tìm ra vị trí nghẽn khi tải lên

**Bài toán:** khi chạy thật, hệ thống chậm ở đâu?

**Cách giải:** đo trước, không ước lượng.

- Prometheus thu số liệu từ cả 4 service: độ trễ, số request, tỷ lệ lỗi
- Grafana hiển thị theo cam kết SLO
- Locust tăng tải dần cho tới khi thấy ngưỡng bị phá
- So sánh trước và sau khi mở rộng

Nếu làm xong mà thấy Catalog vẫn đạt P95 < 80ms dễ dàng thì cache Redis ở mục 4.3 có thể bỏ. Nhưng đừng bỏ trước khi đo.

---

## 6. Cam kết SLO

| Service | Chỉ số | Ngưỡng |
|---|---|---|
| Auth | Tỷ lệ thành công, P95 | ≥ 99.5%, P95 < 150ms |
| Catalog | Độ trễ P95 | P95 < 80ms |
| Booking | Độ trễ P95, tỷ lệ lỗi 5xx | P95 < 200ms, lỗi < 1% |
| Notification | Độ trễ P95, độ mới thông báo | P95 < 400ms, xử lý ≤ 30 giây |

**Giải thích:**

- **P95**: sắp xếp tất cả request theo độ trễ, lấy số thứ 95 — nghĩa là 95% request nhanh hơn mốc đó. Dùng P95 thay vì trung bình vì trung bình bị che mất bởi vài request quá chậm.
- **Lỗi 5xx**: lỗi do server (500, 502, 503). Lỗi do người dùng gửi sai (4xx) không tính.
- **Độ mới thông báo**: từ lúc đặt lịch xong, bao lâu thì thông báo được gửi. Chỉ số này riêng cho phần xử lý nền.

Dashboard Grafana gồm 4 biểu đồ:
- Độ trễ: P50 / P90 / P95 / P99
- Lưu lượng: số request mỗi giây
- Lỗi: tỷ lệ lỗi 5xx
- Bão hòa: mức dùng CPU và RAM của từng container

---

## 7. Kiểm thử chịu tải

### 7.1 Kịch bản Locust — 3 đoạn

1. **Tăng tải**: từ 50 người lên dần
2. **Giữ tải**: giữ nguyên một mức trong 5 phút để quan sát ổn định
3. **Tăng tiếp**: tăng tiếp để xác định điểm gãy

Chỉ làm đoạn 1 thì chưa đủ. Lúc vừa tăng tải luôn có hiện tượng "khởi động chậm" (connection chưa ấn, cache chưa đầy) — đó chưa phải giới hạn thật.

### 7.2 Lỗi phải tránh — 2 lần chạy không so sánh được

Kịch bản đặt lịch vào các khung giờ thật trong database.

- **Lần 1**: đặt hết khung giờ còn trống → tạo tải ghi thật
- **Lần 2** (để so sánh trước/sau khi mở rộng): mọi khung giờ đã có người đặt → tất cả request bị từ chối, **không còn ghi database**

Hai lần đo là hai tình huống khác nhau. Kết luận "sau khi thêm container, P95 còn 180ms" là sai về mặt phương pháp dù số ghi ra đúng.

**Cách sửa:** mỗi lần chạy phải sinh dữ liệu khung giờ mới, hoặc nạp lại dữ liệu giữa 2 lần. Ghi rõ cách làm này vào báo cáo.

### 7.3 Nói rõ giới hạn của phép đo

Máy chạy Locust cũng là máy đang chạy hệ thống. Khi biểu đồ vọt lên phải phân biệt:
- Hệ thống thật nghẽn ở đâu?
- Hay máy đo đã hết tài nguyên trước?

Nêu rõ điều này trong báo cáo. Câu này gần như chắc chắn bị hỏi khi vấn đáp.

### 7.4 Báo cáo

Chỉ ghi số đo thật sau khi chạy, không dùng số ví dụ. Nếu GV hỏi "số này lấy ở đâu" mà không trả lời được thì mất trắng cả phần giám sát.

Nội dung báo cáo: tại mức tải nào P95 vượt ngưỡng, tỷ lệ lỗi tăng bao nhiêu, nguyên nhân ở đâu.

### 7.5 Test chặn đặt trùng

Kịch bản riêng: 50 người cùng đặt 1 `slot_id`, kiểm tra số booking thành công đúng bằng 1.

Cách demo này chứng minh hệ thống **đúng**, không chỉ **nhanh**.

---

## 8. Mở rộng hệ thống

Sau khi tìm ra điểm gãy SLO, thử nghiệm:

- Chạy 3 bản container Booking: `docker compose --scale booking-service=3`
- **Phải bỏ `container_name` cố định** trong compose, vì Docker không cho nhân bản service có tên cố định
- **Không dùng** `deploy: replicas: 3` — đó là cú pháp của Docker Swarm, bản compose thường bỏ qua và không scale được gì
- Nginx chia tải với `least_conn` (đưa request tới container rảnh nhất)

Chỉ nói "hệ thống đã hồi phục về vùng đạt SLO" khi đã đo thật sau khi scale.

---

## 9. Phần bắt buộc có để hệ thống chạy ổn định

Không nằm trong đề bài, nhưng thiếu thì demo dễ hỏng giữa chừng.

### 9.1 Health check

Mỗi service có `/health` trả về "tôi còn sống". Docker Compose khai báo `healthcheck` và `depends_on: condition: service_healthy` để service sau chỉ khởi động khi service trước đã sẵn sàng.

Không có phần này, hệ thống có thể khởi động sai thứ tự và báo lỗi lúc demo.

### 9.2 Cấu hình qua biến môi trường

Chuỗi kết nối database, khóa ký JWT, cổng chạy — đọc từ biến môi trường, không viết cứng trong code.

Khóa bí mật viết cứng rồi đẩy lên Git là lỗi bảo mật bị phát hiện đầu tiên. Đây cũng là nguyên tắc "12-factor app" hay gặp trong vấn đáp.

### 9.3 Log có mã định danh request

Mỗi request sinh một mã duy nhất, ghi mã đó vào log của **tất cả** service nó đi qua. Khi có lỗi, tìm mã là biết nó đi qua đâu, mất bao lâu ở đâu.

Phân biệt rõ:
- **Metrics** (Prometheus) trả lời: *cái gì* đang hỏng
- **Log** trả lời: *tại sao* hỏng

Thiếu log thì phần giám sát chỉ mới đúng một nửa.

### 9.4 Tắt service êm ái

Khi Docker dừng container nó gửi tín hiệu dừng. FastAPI mặc định dừng ngay, có thể cắt ngang request đang xử lý dở → sinh lỗi 500 giả.

Xử lý tín hiệu này để ngập ngày làm xong request hiện tại rồi mới tắt. Nếu không, lúc chạy Locust giữa 2 lần thu đo sẽ xuất hiện lỗi không có nguyên nhân thật.

### 9.5 Kiểm thử tự động

`pytest` cho logic chính: đăng nhập, đặt lịch, chặn trùng.

### 9.6 Giám sát cả cổng vào

Nếu giám sát 4 service mà không đo Nginx thì sẽ không thấy được timeout do Nginx đặt ra, hay hết worker. Nginx là nơi **toàn bộ** request đi qua — nếu nó là nút thắt mà không đo thì sẽ mất thời gian tìm nhầm ở service khác.

---

## 10. Phần không làm

### 10.1 Không làm phân tích dữ liệu

Đề bài không yêu cầu. Với 3–4 tuần phải dồn cho 4 service cùng phần giám sát, thêm pipeline là mất ít nhất 1 tuần.

Phần này dành cho hướng Data Engineering. Nếu sau này chuyển hướng đó, học Airflow và dbt **ngoài dự án này**, trên một dataset thật. Đừng ôm vào đồ án.

### 10.2 Giao diện — làm nhưng không tính vào phần bắt buộc

Đề bài không yêu cầu giao diện. Phần này là tự thêm, dùng để demo đẹp hơn.

**Chừa sẵn 2 thứ trong API từ tuần 1**, nếu không sẽ phải sửa lại:

1. **CORS** — cấu hình sẵn trong FastAPI. Không có thì trình duyệt chặn gọi API. Câu trả lời khi GV hỏi "vì sao cần": đây là chính sách bảo mật của trình duyệt.
2. **Phân trang** — `?page=1&limit=20`. API trả cả 5000 bác sĩ một lệnh thì giao diện không làm được gì.

**4 màn hình:**

| Màn hình | Người làm |
|---|---|
| Đăng nhập | Thành |
| Danh sách bác sĩ (có lọc theo khoa) | Thành |
| Đặt lịch (chọn khung giờ, xử lý 409) | Thành |
| Xem lịch của tôi | Đông |

**Framework:** React + Vite. Không dùng Next.js — nó có phần render phía máy chủ và định tuyến phức tạp, nặng hơn thứ cần.

**Nếu kẹt thời gian, cắt theo thứ tư:** xem lịch của tôi → đặt lịch → danh sách bác sĩ. Trang đăng nhập giữ lại vì không có nó thì demo qua trình duyệt bị khó.

Demo qua Swagger UI vẫn đủ nếu không làm giao diện — FastAPI tự sinh trang tài liệu đầy đủ từ code.

---

## 11. Phân công 3 người

| | Thành | Panh | Đông |
|---|---|---|---|
| **Docker** | — | docker-compose, scale, health check, pool | — |
| **Database** | — | Alembic (tất cả DB), script seed | — |
| **Service** | Auth + Catalog + cache Redis | Booking: đặt lịch, chặn trùng, hủy | Notification + retry + idempotent |
| **Đo lường** | Nginx, rate limit, CORS | bucket Prometheus, chỉ số SLO, log mã định danh | prometheus.yml, Grafana, exporter |
| **Kiểm thử** | — | Locust, tìm điểm gãy, mở rộng | pytest, test event trùng |
| **Giao diện** | 3 màn hình: đăng nhập, danh sách bác sĩ, đặt lịch | — | 1 màn hình: xem lịch của tôi |
| **Tài liệu** | README cách chạy | đoạn kết quả + mở rộng trong báo cáo | viết phần chính của báo cáo |

**Cân bằng:** cả ba người có cùng số nhóm việc chính — mỗi người một phần viết service, một phần vận hành, một phần kiểm thử. Không ai giữ cả 2 phần dễ và cả 2 phần khó.

Hai service CRUD của Thành nhẹ hơn một service tranh chấp của Panh và một service bất đồng bộ của Đông. Panh đổi lại gánh Docker cho cả nhóm.

**Vì sao gộp phần hạ tầng về một người:** hạ tầng là phần chặn tiến độ của cả nhóm — tuần 1 nếu compose không chạy được thì không ai test được gì. Chia ra sẽ tạo 3 phiên bản khác nhau rồi mất thời gian ghép, tốn hơn là dồn.

**Vì sao không chia phần Notification:** người Đông giữ trọn luồng xử lý event — đọc hàng đợi, xử lý trùng, xử lý lỗi, cho tới metrics. CV đánh giá dựa trên hiểu sâu một luồng trọn vẹn.

### Khối lượng ước lượng

Ước lượng theo 8 giờ/ngày, 5 ngày/tuần, cho người làm lần đầu:

| Người | Khoảng giờ | Phần nặng nhất | Mức rủi ro trượt |
|---|---|---|---|
| Thành | ~75h | Giao diện 3 màn hình (~30h) | Trung bình. Người chưa viết React có thể mất 40h |
| Panh | ~67h | Không có khối nào lớn — nhiều việc nhỏ, đều phải hiểu sâu | Thấp nhất. Không có phần nào may mắn mới xong |
| Đông | ~60h | Grafana + viết báo cáo | Cao. Tuần 3 dễ trượt vì Prometheus và biểu đồ lạ |

**Rủi ro của phần hạ tầng:** tuần 1 nếu kẹt thì cả nhóm đứng yên. Làm khung compose xong trước ngày hết tuần 1, nếu không kịp thì báo ngay.

**Nếu thấy Thành kẹt:** chia một màn hình giao diện sang cho Đông. Đó là cách rẻ nhất, không đụng phần lõi.

### Chia câu hỏi khi vấn đáp

Chuẩn bị trước, đừng để đến lúc vấn đáp mới đứa nhau:

| GV hỏi về | Người trả lời |
|---|---|
| Tranh chấp, transaction, tính đúng đắn | **Panh** |
| Hàng đợi, retry, event trùng, xử lý lỗi | **Đông** |
| Docker, mở rộng, cách đo SLO | **Panh** |
| API, caching, Nginx, xác thực | **Thành** |
| Grafana, biểu đồ, báo cáo số liệu | **Đông** |

Chi tiết theo tuần: xem `PHAN-CONG.xlsx`.

---

## 12. Kế hoạch 4 tuần

| Tuần | Công việc |
|---|---|
| 1 | docker-compose + Alembic + script seed + Auth + Catalog + schema Booking + prometheus.yml |
| 2 | Booking + chặn trùng + test tranh chấp + Notification + Nginx + cache Redis + khung giao diện (mock) |
| 3 | bucket Prometheus + chỉ số SLO + Locust + Notification retry/idempotent + Grafana + giao diện nối API |
| 4 | Tìm điểm gãy + mở rộng + pytest + báo cáo + giao diện + vấn đáp |

**Giao diện làm ở tuần 2–3, không đụng tuần 4.** Vì `docs/api-spec.md` đã chốt đủ đầy đủ nên dựng giao diện với dữ liệu giả được ngay ở tuần 2, không phải chờ API xong.

**Tuần 3 là tuần khó nhất** — nhiều thứ lạ lẽn cùng lúc (Prometheus query, Grafana dashboard, metrics).

Nếu 3 người đều đã quen Docker và Linux thì rút còn 3 tuần. Nếu chưa quen, cần đủ 4 tuần.

---

## 13. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Khởi động sai thứ tự, demo fail | Health check từ sớm (mục 9.1) |
| Số đo trong báo cáo không tái tạo được | Dùng Alembic + script seed, không tạo bảng tay |
| Chạy Locust 2 lần không so sánh được | Sinh dữ liệu mới mỗi lần chạy (mục 7.2) |
| Đoán nguyên nhân nghẽn mà không có số liệu | Cấu hình rõ kích thước connection pool, ghi lại giá trị đã thử |
| Không đo Nginx nên tìm nhầm chỗ nghẽn | Thêm exporter cho Nginx (mục 9.6) |
| Máy hết RAM khi chạy 3 bản container | Giảm số người ảo, hoặc chạy tuần tự từng phần |
| Ổ C đầy, Docker không khởi động được | **Cấm ghi vào ổ C.** Đã trỏ Docker sang ổ D — kiểm tra lại trước khi chạy thử |
| Hết thời gian vì làm thêm phần tự thêm | Cắt phân tích dữ liệu và giao diện (mục 10) |

---

## 14. Ghi vào CV

**Tên dự án**

> Hệ thống đặt lịch khám trực tuyến — kiến trúc vi dịch vụ và giám sát SLO

*Dự án môn Khoa học Dịch vụ — yêu cầu: thiết kế và triển khai hệ thống dịch vụ theo kiến trúc microservices kèm giám sát SLA.*

**Công nghệ**

Python, FastAPI, PostgreSQL, Redis, Nginx, Docker, Prometheus, Grafana, Locust, Alembic

**Mô tả — chỉ ghi những phần thực sự đã làm**

- Thiết kế 4 vi dịch vụ độc lập (FastAPI + PostgreSQL riêng từng service) sau một cổng vào Nginx, xác thực JWT, cache danh mục bằng Redis, đóng gói Docker Compose.
- Xử lý tranh chấp đặt lịch tại tầng database bằng ràng buộc unique partial index, kèm kiểm thử 50 request đồng thời trên cùng một khung giờ chứng minh không xảy ra đặt trùng.
- Xây luồng xử lý bất đồng bộ bằng hàng đợi Redis, xử lý idempotent theo khóa `(event_id, recipient_id)`, cơ chế thử lại khi ghi dữ liệu lỗi và bảng dead letter cho event hỏng.
- Thiết lập Prometheus + Grafana giám sát theo cam kết SLO, dùng Locust dò tải xác định điểm gãy, thử nghiệm phương án mở rộng ngang.

**Về định hướng**

Dự án thuộc hướng **Backend / Platform**. Nếu muốn hướng Data Engineering thì cần học thêm Airflow, dbt, Spark và cách làm việc với dữ liệu lớn — dự án này chưa đủ phạm vi đó.

---

## 15. Các tài liệu khác

| File | Nội dung |
|---|---|
| `SRS.docx` | Yêu cầu hệ thống phải làm gì, đạt tiêu chuẩn gì — mở rộng của mục 5–6 |
| `HUONG-DAN-NEWBIE.docx` | Bản đồ bộ tài liệu: đọc gì trước, khi nào mở file nào + checklist trước khi nộp |
| `PHAN-CONG.xlsx` | Chia việc theo tuần, danh mục API, câu hỏi cần hỏi GV |
| `docs/api-spec.md` | Đặc tả endpoint từng service — đọc trước khi code |
| `docs/architecture.md` | Sơ đồ kiến trúc chi tiết + quyết định thiết kế |
| `docs/ghi-chu-quyet-dinh.md` | 11 quyết định kỹ thuật và lý do |
| `AGENT.md` | Context dự án cho AI hỗ trợ |

> Chưa có mã nguồn. Phần hướng dẫn cài đặt và cấu trúc thư mục sẽ viết sau khi có code — xem `HUONG-DAN-NEWBIE.docx` phụ lục C mục C.4.
