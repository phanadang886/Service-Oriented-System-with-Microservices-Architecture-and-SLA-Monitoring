import React, { useState, useEffect } from 'react';
import { fetchDepartments, fetchDoctors } from '../api';

export default function DoctorList({ onSelectDoctor }) {
  const [departments, setDepartments] = useState([]);
  const [selectedDept, setSelectedDept] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [doctors, setDoctors] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [limit] = useState(12);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadDepartments();
  }, []);

  useEffect(() => {
    loadDoctors();
  }, [selectedDept, page]);

  async function loadDepartments() {
    try {
      const data = await fetchDepartments(1, 100);
      setDepartments(data.items || []);
    } catch (err) {
      console.error('Lỗi tải danh sách khoa:', err);
    }
  }

  async function loadDoctors(searchParam = searchQuery) {
    setLoading(true);
    try {
      const data = await fetchDoctors({
        department_id: selectedDept || undefined,
        q: searchParam || undefined,
        page,
        limit
      });
      setDoctors(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Lỗi tải danh sách bác sĩ:', err);
    } finally {
      setLoading(false);
    }
  }

  function handleSearchSubmit(e) {
    e.preventDefault();
    setPage(1);
    loadDoctors(searchQuery);
  }

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div style={{ maxWidth: '1200px', margin: '32px auto', padding: '0 24px' }}>
      {/* Tiêu đề & Bộ lọc */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', flexWrap: 'wrap', gap: '16px',
        marginBottom: '28px'
      }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a' }}>
            Đặt khám cùng Bác sĩ Chuyên khoa
          </h1>
          <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>
            Tìm kiếm bác sĩ theo khoa và đặt lịch khám nhanh chóng
          </p>
        </div>

        {/* Form tìm kiếm & Lọc khoa */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <select
            value={selectedDept}
            onChange={e => { setSelectedDept(e.target.value); setPage(1); }}
            style={{
              padding: '10px 14px', borderRadius: '8px',
              border: '1px solid #cbd5e1', backgroundColor: '#fff',
              fontSize: '14px', color: '#334155'
            }}
          >
            <option value="">Tất cả các khoa</option>
            {departments.map(dept => (
              <option key={dept.id} value={dept.id}>{dept.name}</option>
            ))}
          </select>

          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              placeholder="Tìm theo tên bác sĩ..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                padding: '10px 14px', borderRadius: '8px',
                border: '1px solid #cbd5e1', fontSize: '14px', width: '220px'
              }}
            />
            <button
              type="submit"
              style={{
                padding: '10px 18px', backgroundColor: '#0284c7',
                color: '#fff', border: 'none', borderRadius: '8px',
                fontWeight: '600', fontSize: '14px'
              }}
            >
              Tìm
            </button>
          </form>
        </div>
      </div>

      {/* Lưới danh sách Bác sĩ */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#64748b' }}>
          Đang nạp danh sách bác sĩ...
        </div>
      ) : doctors.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px', backgroundColor: '#fff',
          borderRadius: '12px', border: '1px solid #e2e8f0', color: '#64748b'
        }}>
          Không tìm thấy bác sĩ phù hợp với tiêu chí lọc.
        </div>
      ) : (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '24px', marginBottom: '32px'
        }}>
          {doctors.map(doctor => (
            <div
              key={doctor.id}
              style={{
                backgroundColor: '#ffffff', borderRadius: '12px',
                border: '1px solid #e2e8f0', padding: '20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{
                  display: 'inline-block', padding: '4px 8px', borderRadius: '4px',
                  backgroundColor: '#f1f5f9', color: '#475569',
                  fontSize: '12px', fontWeight: '600', marginBottom: '12px'
                }}>
                  {doctor.department?.name || 'Đa khoa'}
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a', marginBottom: '4px' }}>
                  {doctor.full_name}
                </h3>
                <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '16px' }}>
                  {doctor.title}
                </p>
              </div>

              <div>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  paddingTop: '16px', borderTop: '1px solid #f1f5f9', marginBottom: '16px'
                }}>
                  <span style={{ fontSize: '13px', color: '#64748b' }}>Phí khám:</span>
                  <span style={{ fontSize: '16px', fontWeight: '700', color: '#0284c7' }}>
                    {doctor.price?.toLocaleString('vi-VN')} đ
                  </span>
                </div>
                <button
                  onClick={() => onSelectDoctor(doctor)}
                  style={{
                    width: '100%', padding: '10px', borderRadius: '6px',
                    border: 'none', backgroundColor: '#0284c7',
                    color: '#fff', fontWeight: '600', fontSize: '14px'
                  }}
                >
                  Chọn khung giờ khám
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Phân trang */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', marginTop: '24px' }}>
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            style={{
              padding: '8px 16px', borderRadius: '6px',
              border: '1px solid #cbd5e1', backgroundColor: '#fff',
              color: page <= 1 ? '#94a3b8' : '#334155', fontWeight: '500'
            }}
          >
            Trang trước
          </button>
          <span style={{ fontSize: '14px', color: '#475569' }}>
            Trang {page} / {totalPages} (Tổng {total} bác sĩ)
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            style={{
              padding: '8px 16px', borderRadius: '6px',
              border: '1px solid #cbd5e1', backgroundColor: '#fff',
              color: page >= totalPages ? '#94a3b8' : '#334155', fontWeight: '500'
            }}
          >
            Trang sau
          </button>
        </div>
      )}
    </div>
  );
}
