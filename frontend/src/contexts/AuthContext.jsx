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
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          const response = await api.get('/auth/me');
          setUser(response.data);
        } catch (error) {
          console.error('Auth initialization failed:', error);
          logout();
        }
      }
      setLoading(false);
    };
    initAuth();
  }, [token, logout]);

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('token', access_token);
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const register = async (userData) => {
    const response = await api.post('/auth/register', userData);
    const { access_token, user: newUser } = response.data;
    localStorage.setItem('token', access_token);
    setToken(access_token);
    setUser(newUser);
    return newUser;
  };

  const isAdmin = user?.role === 'super_admin';
  const isSellingPartner = user?.role === 'selling_partner';
  const isSalesAssociate = user?.role === 'sales_associate';
  const isCustomer = user?.role === 'customer';

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      login,
      register,
      logout,
      isAdmin,
      isSellingPartner,
      isSalesAssociate,
      isCustomer,
      isAuthenticated: !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
};
