import React from 'react';

export default function Navbar({ user, onOpenAuth, onLogout, activeTab, setActiveTab }) {
  return (
    <header style={{
      backgroundColor: '#ffffff',
      borderBottom: '1px solid #e2e8f0',
      padding: '16px 32px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }} onClick={() => setActiveTab('doctors')}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '8px',
            backgroundColor: '#0284c7', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: '#fff', fontWeight: 'bold', fontSize: '20px'
          }}>+</div>
          <span style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
            MedBooking
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '16px' }}>
          <button
            onClick={() => setActiveTab('doctors')}
            style={{
              padding: '8px 16px', borderRadius: '6px', border: 'none',
              backgroundColor: activeTab === 'doctors' ? '#e0f2fe' : 'transparent',
              color: activeTab === 'doctors' ? '#0369a1' : '#64748b',
              fontWeight: activeTab === 'doctors' ? '600' : '500'
            }}
          >
            Danh sách Bác sĩ
          </button>
          {user && (
            <button
              onClick={() => setActiveTab('my-appointments')}
              style={{
                padding: '8px 16px', borderRadius: '6px', border: 'none',
                backgroundColor: activeTab === 'my-appointments' ? '#e0f2fe' : 'transparent',
                color: activeTab === 'my-appointments' ? '#0369a1' : '#64748b',
                fontWeight: activeTab === 'my-appointments' ? '600' : '500'
              }}
            >
              Lịch khám của tôi
            </button>
          )}
        </nav>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '14px', color: '#475569' }}>
              Xin chào, <strong>{user.full_name || user.email || 'Bệnh nhân'}</strong> ({user.role})
            </span>
            <button
              onClick={onLogout}
              style={{
                padding: '8px 16px', borderRadius: '6px',
                border: '1px solid #cbd5e1', backgroundColor: '#fff',
                color: '#ef4444', fontWeight: '500'
              }}
            >
              Đăng xuất
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            style={{
              padding: '8px 20px', borderRadius: '6px',
              border: 'none', backgroundColor: '#0284c7',
              color: '#fff', fontWeight: '600', boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
            }}
          >
            Đăng nhập / Đăng ký
          </button>
        )}
      </div>
    </header>
  );
}
