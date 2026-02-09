import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 30000
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
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
    'selling_partner': 'Selling Partner',
    'sales_associate': 'Sales Associate',
    'customer': 'Customer'
  };
  return labels[role] || role;
};

export const getRoleColor = (role) => {
  const colors = {
    'super_admin': 'bg-purple-100 text-purple-800',
    'selling_partner': 'bg-blue-100 text-blue-800',
    'sales_associate': 'bg-green-100 text-green-800',
    'customer': 'bg-orange-100 text-orange-800'
  };
  return colors[role] || 'bg-gray-100 text-gray-800';
};
