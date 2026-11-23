# Nguồn dữ liệu danh mục

## Khoa và bác sĩ: dữ liệu thật

Thu thập ngày 2026-11-24 từ trang công khai:

- https://bvdaihoc.com.vn/bac-si

Trang có 144 hồ sơ bác sĩ. Nhóm lấy **60 bác sĩ thuộc 8 khoa** (xem `doctors.csv`).
Cột `source_url` giữ đường dẫn hồ sơ gốc để đối chiếu từng người.

Nếu trang đổi nội dung, `source_url` vẫn là chỗ kiểm tra lại.

## Dữ liệu mô phỏng — phải ghi rõ khi báo cáo

| Trường | Cách sinh | Vì sao |
|---|---|---|
| `doctors.price` | Theo học hàm/học vị (250.000 – 450.000) | Website không công bố giá từng bác sĩ |
| `departments.description` | Nhóm tự viết một dòng | Chỉ để hiển thị |
| `time_slots` | Sinh theo quy tắc 8:00–11:30 và 14:00–17:30, thứ 2–6 | Không có lịch làm việc thật của từng bác sĩ |
| `users` | Tài khoản thử nghiệm | Không dùng dữ liệu bệnh nhân thật |
| `appointments` | Sinh cho kiểm thử | Không dùng lịch hẹn thật |

**Câu nói khi vấn đáp:** danh mục khoa và bác sĩ lấy từ nguồn công khai;
giá, lịch và tài khoản là mô phỏng để kiểm thử, ghi rõ trong báo cáo.
