import React, { useState } from 'react';
import { loginUser, registerUser } from '../api';

export default function LoginModal({ isOpen, onClose, onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('PATIENT');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      if (isRegister) {
        await registerUser(email, password, fullName, role);
        // Đăng ký xong tự động đăng nhập
        await loginUser(email, password);
      } else {
        await loginUser(email, password);
      }
      onLoginSuccess();
      onClose();
    } catch (err) {
      if (err.code === 'INVALID_CREDENTIALS') {
        setErrorMsg('Email hoặc mật khẩu không chính xác');
      } else if (err.code === 'EMAIL_EXISTS') {
        setErrorMsg('Email này đã được sử dụng bởi tài khoản khác');
      } else {
        setErrorMsg(err.detail || 'Có lỗi xảy ra, vui lòng thử lại');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#ffffff', borderRadius: '12px',
        padding: '32px', width: '420px', maxWidth: '90%',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '700', color: '#0f172a' }}>
            {isRegister ? 'Đăng ký tài khoản' : 'Đăng nhập'}
          </h2>
          <button onClick={onClose} style={{ border: 'none', background: 'transparent', fontSize: '20px', color: '#94a3b8' }}>✕</button>
        </div>

        {errorMsg && (
          <div style={{
            backgroundColor: '#fee2e2', border: '1px solid #f87171',
            color: '#b91c1c', padding: '10px 14px', borderRadius: '6px',
            fontSize: '14px', marginBottom: '16px'
          }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isRegister && (
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px', color: '#334155' }}>
                Họ và tên
              </label>
              <input
                type="text" required value={fullName} onChange={e => setFullName(e.target.value)}
                placeholder="Nguyễn Văn A"
                style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px', color: '#334155' }}>
              Email
            </label>
            <input
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              placeholder="ten@example.com"
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px', color: '#334155' }}>
              Mật khẩu
            </label>
            <input
              type="password" required value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Tối thiểu 6 ký tự" minLength={6}
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
            />
          </div>

          {isRegister && (
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px', color: '#334155' }}>
                Vai trò
              </label>
              <select
                value={role} onChange={e => setRole(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
              >
                <option value="PATIENT">Bệnh nhân (PATIENT)</option>
                <option value="DOCTOR">Bác sĩ (DOCTOR)</option>
              </select>
            </div>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              padding: '12px', backgroundColor: '#0284c7', color: '#fff',
              border: 'none', borderRadius: '6px', fontWeight: '600',
              marginTop: '8px', opacity: loading ? 0.7 : 1
            }}
          >
            {loading ? 'Đang xử lý...' : (isRegister ? 'Đăng ký ngay' : 'Đăng nhập')}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '14px', color: '#64748b' }}>
          {isRegister ? (
            <span>Đã có tài khoản? <button onClick={() => { setIsRegister(false); setErrorMsg(''); }} style={{ border: 'none', background: 'transparent', color: '#0284c7', fontWeight: '600' }}>Đăng nhập</button></span>
          ) : (
            <span>Chưa có tài khoản? <button onClick={() => { setIsRegister(true); setErrorMsg(''); }} style={{ border: 'none', background: 'transparent', color: '#0284c7', fontWeight: '600' }}>Đăng ký ngay</button></span>
          )}
        </div>
      </div>
    </div>
  );
}
