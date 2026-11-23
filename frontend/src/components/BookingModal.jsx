import React, { useState, useEffect } from 'react';
import { fetchDoctorSlots, bookAppointment } from '../api';

export default function BookingModal({ doctor, isOpen, onClose, user, onOpenAuth }) {
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    if (isOpen && doctor) {
      loadSlots();
      setSelectedSlot(null);
      setErrorMsg('');
      setSuccessMsg('');
    }
  }, [isOpen, doctor, selectedDate]);

  async function loadSlots() {
    setLoading(true);
    setErrorMsg('');
    try {
      const data = await fetchDoctorSlots(doctor.id, selectedDate);
      setSlots(data.items || []);
    } catch (err) {
      setErrorMsg('Không thể tải danh sách khung giờ: ' + (err.detail || err.message));
    } finally {
      setLoading(false);
    }
  }

  async function handleBook() {
    if (!user) {
      onOpenAuth();
      return;
    }
    if (!selectedSlot) {
      setErrorMsg('Vui lòng chọn một khung giờ khám.');
      return;
    }

    setBookingLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      await bookAppointment(doctor.id, selectedSlot.id, note);
      setSuccessMsg('Đặt lịch thành công! Hệ thống đã ghi nhận lịch hẹn của bạn.');
      setSelectedSlot(null);
      setNote('');
      // Nạp lại danh sách slot để cập nhật trạng thái
      loadSlots();
    } catch (err) {
      // Bắt rõ ràng mã lỗi 409 SLOT_TAKEN theo đúng yêu cầu phân công
      if (err.status === 409 || err.code === 'SLOT_TAKEN') {
        setErrorMsg('KHUNG GIỜ NÀY VỪA CÓ NGƯỜI ĐẶT TRƯỚC! Vui lòng chọn khung giờ khám khác.');
      } else {
        setErrorMsg(err.detail || 'Đặt lịch không thành công, vui lòng thử lại.');
      }
    } finally {
      setBookingLoading(false);
    }
  }

  if (!isOpen || !doctor) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#ffffff', borderRadius: '12px',
        padding: '28px', width: '560px', maxWidth: '95%',
        maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: '700', color: '#0f172a' }}>
              Đặt lịch khám: {doctor.full_name}
            </h2>
            <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>
              {doctor.title} • {doctor.department?.name} • Giá khám: <strong>{doctor.price?.toLocaleString('vi-VN')} đ</strong>
            </p>
          </div>
          <button onClick={onClose} style={{ border: 'none', background: 'transparent', fontSize: '22px', color: '#94a3b8' }}>✕</button>
        </div>

        {errorMsg && (
          <div style={{
            backgroundColor: '#fee2e2', border: '1px solid #ef4444',
            color: '#b91c1c', padding: '12px 16px', borderRadius: '8px',
            fontSize: '14px', marginBottom: '16px', fontWeight: '500'
          }}>
            ⚠️ {errorMsg}
          </div>
        )}

        {successMsg && (
          <div style={{
            backgroundColor: '#dcfce7', border: '1px solid #22c55e',
            color: '#15803d', padding: '12px 16px', borderRadius: '8px',
            fontSize: '14px', marginBottom: '16px', fontWeight: '500'
          }}>
            ✓ {successMsg}
          </div>
        )}

        {/* Chọn ngày */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#334155' }}>
            1. Chọn ngày khám
          </label>
          <input
            type="date"
            value={selectedDate}
            onChange={e => setSelectedDate(e.target.value)}
            style={{
              padding: '10px 14px', borderRadius: '6px',
              border: '1px solid #cbd5e1', fontSize: '14px', width: '220px'
            }}
          />
        </div>

        {/* Danh sách khung giờ */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#334155' }}>
            2. Chọn khung giờ khám (is_available chỉ mang tính gợi ý)
          </label>

          {loading ? (
            <p style={{ fontSize: '14px', color: '#64748b' }}>Đang nạp khung giờ...</p>
          ) : slots.length === 0 ? (
            <div style={{
              backgroundColor: '#f1f5f9', padding: '20px', borderRadius: '8px',
              textAlign: 'center', color: '#64748b', fontSize: '14px'
            }}>
              Chưa có khung giờ khám nào được tạo cho ngày này.
            </div>
          ) : (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))',
              gap: '10px', maxHeight: '180px', overflowY: 'auto', padding: '4px'
            }}>
              {slots.map(slot => {
                const startTime = new Date(slot.start_time).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
                const endTime = new Date(slot.end_time).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
                const isSelected = selectedSlot?.id === slot.id;
                const isAvailable = slot.is_available !== false;

                return (
                  <button
                    key={slot.id}
                    disabled={!isAvailable}
                    onClick={() => setSelectedSlot(slot)}
                    style={{
                      padding: '10px 8px', borderRadius: '6px',
                      border: isSelected ? '2px solid #0284c7' : '1px solid #cbd5e1',
                      backgroundColor: !isAvailable ? '#f1f5f9' : (isSelected ? '#e0f2fe' : '#ffffff'),
                      color: !isAvailable ? '#94a3b8' : (isSelected ? '#0369a1' : '#1e293b'),
                      fontWeight: isSelected ? '700' : '500',
                      fontSize: '13px',
                      cursor: isAvailable ? 'pointer' : 'not-allowed',
                      textAlign: 'center'
                    }}
                  >
                    <div>{startTime} - {endTime}</div>
                    <div style={{ fontSize: '11px', marginTop: '2px', color: !isAvailable ? '#ef4444' : '#10b981' }}>
                      {isAvailable ? 'Còn trống' : 'Đã kín'}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Ghi chú */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#334155' }}>
            3. Triệu chứng hoặc ghi chú (tùy chọn)
          </label>
          <textarea
            rows="2"
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Mô tả sơ qua triệu chứng hoặc lý do khám..."
            style={{
              width: '100%', padding: '10px 12px', borderRadius: '6px',
              border: '1px solid #cbd5e1', fontSize: '14px', resize: 'vertical'
            }}
          />
        </div>

        {/* Nút đặt lịch */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '10px 20px', borderRadius: '6px',
              border: '1px solid #cbd5e1', backgroundColor: '#fff',
              color: '#475569', fontWeight: '500'
            }}
          >
            Đóng
          </button>
          <button
            onClick={handleBook}
            disabled={bookingLoading || !selectedSlot}
            style={{
              padding: '10px 24px', borderRadius: '6px',
              border: 'none', backgroundColor: '#0284c7',
              color: '#fff', fontWeight: '600',
              opacity: (bookingLoading || !selectedSlot) ? 0.6 : 1
            }}
          >
            {bookingLoading ? 'Đang đặt lịch...' : 'Xác nhận Đặt lịch'}
          </button>
        </div>
      </div>
    </div>
  );
}
