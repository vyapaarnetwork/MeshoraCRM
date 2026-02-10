import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import LeadForm from './pages/LeadForm';
import LeadImport from './pages/LeadImport';
import Categories from './pages/Categories';
import Commission from './pages/Commission';
import Reports from './pages/Reports';
import Users from './pages/Users';
import Companies from './pages/Companies';
import Settings from './pages/Settings';
import './App.css';

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { isAuthenticated, loading, user } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Layout>{children}</Layout>;
};

// Public Route Component (redirects to dashboard if authenticated)
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

      {/* Protected Routes - All Roles */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      } />
      
      <Route path="/leads" element={
        <ProtectedRoute>
          <Leads />
        </ProtectedRoute>
      } />
      
      <Route path="/leads/new" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'customer']}>
          <LeadForm />
        </ProtectedRoute>
      } />
      
      <Route path="/leads/:id" element={
        <ProtectedRoute>
          <LeadDetail />
        </ProtectedRoute>
      } />
      
      <Route path="/leads/:id/edit" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'customer']}>
          <LeadForm />
        </ProtectedRoute>
      } />
      
      <Route path="/leads/import" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'customer']}>
          <LeadImport />
        </ProtectedRoute>
      } />

      {/* Admin Only Routes */}
      <Route path="/users" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <Users />
        </ProtectedRoute>
      } />
      
      <Route path="/companies" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <Companies />
        </ProtectedRoute>
      } />
      
      <Route path="/categories" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <Categories />
        </ProtectedRoute>
      } />
      
      <Route path="/commission" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <Commission />
        </ProtectedRoute>
      } />

      {/* Reports - Admin, Selling Partner, Sales Associate */}
      <Route path="/reports" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <Reports />
        </ProtectedRoute>
      } />

      {/* Settings placeholder */}
      <Route path="/settings" element={
        <ProtectedRoute>
          <div className="p-6">
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-muted-foreground mt-2">Settings page coming soon...</p>
          </div>
        </ProtectedRoute>
      } />

      {/* Redirect root to dashboard or login */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      
      {/* 404 - Redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
