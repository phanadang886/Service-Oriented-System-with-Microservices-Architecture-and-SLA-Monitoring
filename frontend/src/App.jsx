import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import DoctorList from './components/DoctorList';
import BookingModal from './components/BookingModal';
import LoginModal from './components/LoginModal';
import MyAppointments from './components/MyAppointments';
import { getStoredUser, getCurrentUser, logoutUser } from './api';

export default function App() {
  const [user, setUser] = useState(() => getStoredUser());
  const [activeTab, setActiveTab] = useState('doctors');
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState(null);

  useEffect(() => {
    // Tự động kiểm tra token khi load trang
    getCurrentUser()
      .then(userData => setUser(userData))
      .catch(() => {
        // Token hết hạn hoặc không hợp lệ
        logoutUser();
        setUser(null);
      });
  }, []);

  function handleLogout() {
    logoutUser();
    setUser(null);
    setActiveTab('doctors');
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        user={user}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenAuth={() => setIsAuthOpen(true)}
        onLogout={handleLogout}
      />

      <main style={{ flex: 1 }}>
        {activeTab === 'doctors' && (
          <DoctorList onSelectDoctor={doc => setSelectedDoctor(doc)} />
        )}
        {activeTab === 'my-appointments' && (
          <MyAppointments user={user} onOpenAuth={() => setIsAuthOpen(true)} />
        )}
      </main>

      <BookingModal
        doctor={selectedDoctor}
        isOpen={!!selectedDoctor}
        onClose={() => setSelectedDoctor(null)}
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
      />

      <LoginModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onLoginSuccess={() => {
          getCurrentUser().then(userData => setUser(userData)).catch(() => {});
        }}
      />

      <footer style={{
        textAlign: 'center', padding: '24px',
        borderTop: '1px solid #e2e8f0', color: '#94a3b8', fontSize: '13px'
      }}>
        Hệ thống đặt lịch khám bệnh trực tuyến • Đồ án Khoa học Dịch vụ • Kiến trúc Vi dịch vụ
      </footer>
    </div>
  );
}
