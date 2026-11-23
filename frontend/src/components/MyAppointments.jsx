import React, { useState, useEffect } from 'react';
import { fetchMyAppointments, cancelAppointment } from '../api';

export default function MyAppointments({ user, onOpenAuth }) {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [msg, setMsg] = useState({ text: '', type: '' });

  useEffect(() => {
    if (user) {
      loadAppointments();
    }
  }, [user]);

  async function loadAppointments() {
    setLoading(true);
    setMsg({ text: '', type: '' });
    try {
      const data = await fetchMyAppointments();
      setAppointments(data.items || data || []);
    } catch (err) {
      setMsg({
        text: 'Chưa thể tải danh sách (Booking Service đang được hoàn thiện bởi bạn Panh): ' + (err.detail || err.message),
        type: 'info'
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel(id) {
    if (!window.confirm('Bạn có chắc chắn muốn hủy lịch khám này không?')) return;
    setActionLoading(true);
    try {
      await cancelAppointment(id);
      setMsg({ text: 'Hủy lịch hẹn thành công!', type: 'success' });
      loadAppointments();
    } catch (err) {
      setMsg({ text: 'Lỗi hủy lịch: ' + (err.detail || err.message), type: 'error' });
    } finally {
      setActionLoading(false);
    }
  }

  if (!user) {
    return (
      <div style={{ maxWidth: '800px', margin: '40px auto', textAlign: 'center', padding: '40px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '12px' }}>Vui lòng đăng nhập</h2>
        <p style={{ color: '#64748b', marginBottom: '20px' }}>Bạn cần đăng nhập tài khoản để xem các lịch khám đã đặt.</p>
        <button
          onClick={onOpenAuth}
          style={{ padding: '10px 24px', backgroundColor: '#0284c7', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '600' }}
        >
          Đăng nhập ngay
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '900px', margin: '32px auto', padding: '0 24px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', marginBottom: '8px' }}>
        Lịch khám của tôi
      </h1>
      <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '24px' }}>
        Theo dõi trạng thái các lịch khám đã xác nhận và hủy lịch khi cần thiết
      </p>

      {msg.text && (
        <div style={{
          padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '14px', fontWeight: '500',
          backgroundColor: msg.type === 'error' ? '#fee2e2' : (msg.type === 'success' ? '#dcfce7' : '#e0f2fe'),
          color: msg.type === 'error' ? '#b91c1c' : (msg.type === 'success' ? '#15803d' : '#0369a1'),
          border: `1px solid ${msg.type === 'error' ? '#ef4444' : (msg.type === 'success' ? '#22c55e' : '#38bdf8')}`
        }}>
          {msg.text}
        </div>
      )}

      {loading ? (
        <p style={{ color: '#64748b' }}>Đang nạp lịch khám...</p>
      ) : appointments.length === 0 ? (
        <div style={{
          backgroundColor: '#fff', padding: '40px', borderRadius: '12px',
          border: '1px solid #e2e8f0', textAlign: 'center', color: '#64748b'
        }}>
          Bạn chưa có lịch hẹn khám nào. Hãy chọn bác sĩ và đặt lịch ngay!
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {appointments.map(item => (
            <div
              key={item.id}
              style={{
                backgroundColor: '#fff', borderRadius: '10px',
                border: '1px solid #e2e8f0', padding: '20px',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <span style={{
                    padding: '3px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '700',
                    backgroundColor: item.status === 'CONFIRMED' ? '#dcfce7' : (item.status === 'CANCELLED' ? '#fee2e2' : '#f1f5f9'),
                    color: item.status === 'CONFIRMED' ? '#15803d' : (item.status === 'CANCELLED' ? '#b91c1c' : '#475569')
                  }}>
                    {item.status}
                  </span>
                  <span style={{ fontSize: '15px', fontWeight: '600', color: '#0f172a' }}>
                    Mã hẹn: #{item.id?.slice(0, 8)}
                  </span>
                </div>
                <p style={{ fontSize: '14px', color: '#475569' }}>
                  Thời gian: {item.slot?.start_time ? new Date(item.slot.start_time).toLocaleString('vi-VN') : 'Theo khung giờ đã chọn'}
                </p>
                {item.note && (
                  <p style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>
                    Ghi chú: {item.note}
                  </p>
                )}
              </div>

              {item.status !== 'CANCELLED' && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleCancel(item.id)}
                  style={{
                    padding: '8px 16px', borderRadius: '6px',
                    border: '1px solid #fca5a5', backgroundColor: '#fff',
                    color: '#ef4444', fontWeight: '600', fontSize: '13px'
                  }}
                >
                  Hủy lịch
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
