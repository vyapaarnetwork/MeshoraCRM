import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 30000,
  // Phase 26: send the httpOnly auth cookie with every request
  withCredentials: true,
});

// Phase 26: JWT is now in an httpOnly cookie. We no longer attach Authorization
// headers from localStorage. (Auth interceptor removed.)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Drop legacy token if present (one-time cleanup) and bounce to login
      try { localStorage.removeItem('token'); } catch (e) { /* ignore */ }
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// Helper functions
export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(amount);
};

export const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

export const formatDateTime = (dateString) => {
  return new Date(dateString).toLocaleString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const getRoleLabel = (role) => {
  const labels = {
    'super_admin': 'Super Admin',
    'vyapaar_ops': 'Vyapaar Operations',
    'vyapaar_finance': 'Vyapaar Finance',
    'selling_partner': 'Selling Partner',
    'sales_associate': 'Sales Associate',
    'customer': 'Customer'
  };
  return labels[role] || role;
};

export const getRoleColor = (role) => {
  const colors = {
    'super_admin': 'bg-purple-100 text-purple-800',
    'vyapaar_ops': 'bg-indigo-100 text-indigo-800',
    'vyapaar_finance': 'bg-amber-100 text-amber-800',
    'selling_partner': 'bg-blue-100 text-blue-800',
    'sales_associate': 'bg-green-100 text-green-800',
    'customer': 'bg-orange-100 text-orange-800'
  };
  return colors[role] || 'bg-gray-100 text-gray-800';
};
