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
    // Phase 26.1: clear both legacy and new keys
    try { localStorage.removeItem('access_token'); } catch (e) { /* ignore */ }
    try { localStorage.removeItem('token'); } catch (e) { /* ignore */ }
    setUser(null);
  }, []);

  useEffect(() => {
    // Phase 26.1: try /auth/me with whatever auth we have (cookie via withCredentials,
    // OR Authorization header from localStorage via request interceptor).
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
    const { access_token, user: userData } = response.data;
    // Phase 26.1: store token in localStorage as Bearer fallback for cross-domain prod
    // (the backend also sets an httpOnly cookie — whichever the browser accepts).
    if (access_token) {
      try { localStorage.setItem('access_token', access_token); } catch (e) { /* ignore */ }
    }
    setUser(userData);
    return userData;
  };

  const register = async (userData) => {
    const response = await api.post('/auth/register', userData);
    const { access_token, user: newUser } = response.data;
    if (access_token) {
      try { localStorage.setItem('access_token', access_token); } catch (e) { /* ignore */ }
    }
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
