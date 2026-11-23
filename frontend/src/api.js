const API_BASE = '/api';

export function getStoredToken() {
  return localStorage.getItem('access_token');
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem('access_token', token);
  } else {
    localStorage.removeItem('access_token');
  }
}

export function getStoredUser() {
  const user = localStorage.getItem('current_user');
  return user ? JSON.parse(user) : null;
}

export function setStoredUser(user) {
  if (user) {
    localStorage.setItem('current_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('current_user');
  }
}

export async function apiRequest(endpoint, options = {}) {
  const token = getStoredToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(data?.detail || 'Đã có lỗi xảy ra');
    error.status = response.status;
    error.code = data?.code || 'UNKNOWN_ERROR';
    error.detail = data?.detail || 'Lỗi hệ thống';
    throw error;
  }

  return data;
}

// ---------------------------------------------
// Auth API
// ---------------------------------------------
export async function loginUser(email, password) {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
  setStoredToken(data.access_token);
  setStoredUser(data.user);
  return data;
}

export async function registerUser(email, password, full_name, role = 'PATIENT') {
  return await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name, role })
  });
}

export async function getCurrentUser() {
  return await apiRequest('/auth/me');
}

export function logoutUser() {
  setStoredToken(null);
  setStoredUser(null);
}

// ---------------------------------------------
// Catalog API
// ---------------------------------------------
export async function fetchDepartments(page = 1, limit = 50) {
  return await apiRequest(`/catalog/departments?page=${page}&limit=${limit}`);
}

export async function fetchDoctors({ department_id, q, page = 1, limit = 20 } = {}) {
  const params = new URLSearchParams({ page, limit });
  if (department_id) params.append('department_id', department_id);
  if (q) params.append('q', q);
  return await apiRequest(`/catalog/doctors?${params.toString()}`);
}

export async function fetchDoctorSlots(doctor_id, date = '') {
  const params = new URLSearchParams({ page: 1, limit: 100 });
  if (date) params.append('date', date);
  return await apiRequest(`/catalog/doctors/${doctor_id}/slots?${params.toString()}`);
}

// ---------------------------------------------
// Booking API (Nối khi Panh hoàn thành hoặc gọi qua gateway)
// ---------------------------------------------
export async function bookAppointment(doctor_id, slot_id, note = '') {
  return await apiRequest('/booking/appointments', {
    method: 'POST',
    body: JSON.stringify({ doctor_id, slot_id, note })
  });
}

export async function fetchMyAppointments() {
  return await apiRequest('/booking/appointments/my');
}

export async function cancelAppointment(appointment_id) {
  return await apiRequest(`/booking/appointments/${appointment_id}/cancel`, {
    method: 'PATCH'
  });
}
