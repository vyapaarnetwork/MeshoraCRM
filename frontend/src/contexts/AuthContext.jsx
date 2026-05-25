import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../utils/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      // ignore — even if backend errors, clear local state
    }
    // One-time cleanup of legacy localStorage token (Phase 26)
    try { localStorage.removeItem('token'); } catch (e) { /* ignore */ }
    setUser(null);
  }, []);

  useEffect(() => {
    // Phase 26: rely on the httpOnly cookie set by login/register. Always try
    // /auth/me on mount; if 401, user just isn't logged in.
    const initAuth = async () => {
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    initAuth();
  }, []);

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    const { user: userData } = response.data;
    // The httpOnly cookie is already set by the backend; we only track user in memory.
    setUser(userData);
    return userData;
  };

  const register = async (userData) => {
    const response = await api.post('/auth/register', userData);
    const { user: newUser } = response.data;
    setUser(newUser);
    return newUser;
  };

  const isAdmin = user?.role === 'super_admin';
  const isSellingPartner = user?.role === 'selling_partner';
  const isSalesAssociate = user?.role === 'sales_associate';
  const isCustomer = user?.role === 'customer';
  const isVyapaarOps = !!user?.is_vyapaar_ops || user?.role === 'vyapaar_ops';
  const isVyapaarFinance = user?.role === 'vyapaar_finance';
  const isFinance = !!user?.is_finance || isVyapaarFinance;
  const isDelivery = !!user?.is_delivery;
  // Vyapaar Ops can edit leads/companies; Finance is read-only outside commercials
  const canEditLeadsCompanies = isAdmin || (isVyapaarOps && !isVyapaarFinance);
  const canAccessCommercials = isAdmin || isSellingPartner || isFinance || isDelivery || isVyapaarOps;
  const canWriteCommercials = isAdmin || isFinance || isDelivery || isVyapaarOps;

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      register,
      logout,
      isAdmin,
      isSellingPartner,
      isSalesAssociate,
      isCustomer,
      isFinance,
      isDelivery,
      isVyapaarOps,
      isVyapaarFinance,
      canEditLeadsCompanies,
      canAccessCommercials,
      canWriteCommercials,
      isAuthenticated: !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
};
