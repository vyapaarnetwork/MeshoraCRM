import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 30000,
  // Phase 26: send the httpOnly auth cookie on same-origin/SameSite=None scenarios
  withCredentials: true,
});

// Phase 26.1 (production hot-fix): also attach Authorization: Bearer header from
// localStorage when present. We discovered that some production deployments host the
// frontend on a custom domain (e.g. app.vyapaar.net) while /api lives on a different
// domain, which makes the response a cross-site request. Browsers may then refuse to
// store/send the httpOnly cookie depending on third-party-cookie settings. Falling back
// to a Bearer header guarantees the session works regardless. The backend's
// get_current_user already reads cookie OR Authorization header (whichever is present).
api.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem('access_token');
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (e) { /* ignore */ }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Drop stored token on 401 (token might be expired/invalid)
      try { localStorage.removeItem('access_token'); } catch (e) { /* ignore */ }
      try { localStorage.removeItem('token'); } catch (e) { /* ignore one-time legacy cleanup */ }
      // Public paths that should NOT redirect on 401 (Phase 27.5: guest magic link)
      const p = window.location.pathname;
      const isPublicPath = p === '/login' || p === '/register' || p.startsWith('/deal-room/');
      if (!isPublicPath) {
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
