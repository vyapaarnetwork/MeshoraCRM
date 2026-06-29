import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { Toaster } from './components/ui/sonner';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import LeadForm from './pages/LeadForm';
import LeadImport from './pages/LeadImport';
import LeadReferral from './pages/LeadReferral';
import InternalRequests from './pages/InternalRequests';
import CompanyUsers from './pages/CompanyUsers';
import Categories from './pages/Categories';
import Commission from './pages/Commission';
import Reports from './pages/Reports';
import WonLeadsReport from './pages/WonLeadsReport';
import PipelineReport from './pages/PipelineReport';
import ConversionReport from './pages/ConversionReport';
import PartnerPerformance from './pages/PartnerPerformance';
import LeadActivityReport from './pages/LeadActivityReport';
import SavedReports from './pages/SavedReports';
import ScheduledReports from './pages/ScheduledReports';
import RevenueIntelligence from './pages/RevenueIntelligence';
import PredictiveForecast from './pages/PredictiveForecast';
import PartnerIntelligence from './pages/PartnerIntelligence';
import GuestDealRoom from './pages/GuestDealRoom';
import Help from './pages/Help';
import WarRoom from './pages/WarRoom';
import GridReport from './pages/GridReport';
import Users from './pages/Users';
import Companies from './pages/Companies';
import Settings from './pages/Settings';
import DocumentTags from './pages/DocumentTags';
import EmailTemplates from './pages/EmailTemplates';
import PartnerMappings from './pages/PartnerMappings';
import CommercialsList from './pages/CommercialsList';
import CommercialDetail from './pages/CommercialDetail';
import CommercialsAnalytics from './pages/CommercialsAnalytics';
import CommercialsKanban from './pages/CommercialsKanban';
import InternalTasks from './pages/InternalTasks';
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

  // Phase 18: vyapaar_ops & vyapaar_finance get the same surface as super_admin
  const ADMIN_LIKE_ROLES = ['super_admin', 'vyapaar_ops', 'vyapaar_finance'];
  const effectiveAllowed = allowedRoles.includes('super_admin')
    ? Array.from(new Set([...allowedRoles, ...ADMIN_LIKE_ROLES]))
    : allowedRoles;

  if (effectiveAllowed.length > 0 && !effectiveAllowed.includes(user?.role)) {
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

      {/* Phase 27.5: Guest Deal Room via magic link — no auth required */}
      <Route path="/deal-room/:token" element={<GuestDealRoom />} />

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

      {/* Lead Referral - Selling Partners and Sales Associates */}
      <Route path="/lead-referral" element={
        <ProtectedRoute allowedRoles={['selling_partner', 'sales_associate']}>
          <LeadReferral />
        </ProtectedRoute>
      } />

      {/* Internal Requests - Selling Partners Only */}
      <Route path="/internal-requests" element={
        <ProtectedRoute allowedRoles={['selling_partner']}>
          <InternalRequests />
        </ProtectedRoute>
      } />

      {/* Company Users - Customers Only */}
      <Route path="/company-users" element={
        <ProtectedRoute allowedRoles={['customer']}>
          <CompanyUsers />
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

      <Route path="/document-tags" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <DocumentTags />
        </ProtectedRoute>
      } />

      <Route path="/email-templates" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <EmailTemplates />
        </ProtectedRoute>
      } />

      <Route path="/partner-mappings" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <PartnerMappings />
        </ProtectedRoute>
      } />

      {/* Commercials (Revenue Contracting & Delivery) */}
      <Route path="/commercials" element={
        <ProtectedRoute>
          <CommercialsList />
        </ProtectedRoute>
      } />
      <Route path="/commercials/analytics" element={
        <ProtectedRoute>
          <CommercialsAnalytics />
        </ProtectedRoute>
      } />
      <Route path="/commercials/kanban" element={
        <ProtectedRoute>
          <CommercialsKanban />
        </ProtectedRoute>
      } />
      <Route path="/commercials/:id" element={
        <ProtectedRoute>
          <CommercialDetail />
        </ProtectedRoute>
      } />

      {/* Phase 36 — Internal Vyapaar Tasks (Vyapaar internal only) */}
      <Route path="/internal-tasks" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <InternalTasks />
        </ProtectedRoute>
      } />
      <Route path="/internal-tasks/:id" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <InternalTasks />
        </ProtectedRoute>
      } />

      {/* Reports - Admin, Selling Partner, Sales Associate */}
      <Route path="/reports" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <Reports />
        </ProtectedRoute>
      } />

      {/* Revenue Intelligence - Admin + Vyapaar Ops + Vyapaar Finance + Selling Partner */}
      <Route path="/revenue-intelligence" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner']}>
          <RevenueIntelligence />
        </ProtectedRoute>
      } />

      {/* Predictive Revenue Forecasting - Admin + Ops + Finance + Selling Partner */}
      <Route path="/predictive-forecast" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner']}>
          <PredictiveForecast />
        </ProtectedRoute>
      } />

      {/* Partner Intelligence - Admin/Ops only (Selling Partner also reads via API RBAC) */}
      <Route path="/partner-intelligence" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner']}>
          <PartnerIntelligence />
        </ProtectedRoute>
      } />

      {/* Help & Feature Guide - all authenticated users */}
      <Route path="/help" element={
        <ProtectedRoute>
          <Help />
        </ProtectedRoute>
      } />

      {/* Phase 29: Weekly War Room - admin/ops/finance/selling partner/sales associate */}
      <Route path="/war-room" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <WarRoom />
        </ProtectedRoute>
      } />

      {/* Phase 34.6: Won Leads Report - Vyapaar team only (admin/ops/finance) */}
      <Route path="/reports/won-leads" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <WonLeadsReport />
        </ProtectedRoute>
      } />

      {/* Phase 34.7: New report pages */}
      <Route path="/reports/pipeline" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <PipelineReport />
        </ProtectedRoute>
      } />
      <Route path="/reports/conversion" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <ConversionReport />
        </ProtectedRoute>
      } />
      <Route path="/reports/partner-performance" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <PartnerPerformance />
        </ProtectedRoute>
      } />
      <Route path="/reports/lead-activity" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <LeadActivityReport />
        </ProtectedRoute>
      } />
      <Route path="/reports/saved" element={
        <ProtectedRoute allowedRoles={['super_admin', 'selling_partner', 'sales_associate']}>
          <SavedReports />
        </ProtectedRoute>
      } />
      <Route path="/reports/scheduled" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <ScheduledReports />
        </ProtectedRoute>
      } />

      {/* Grid Report - Admin Only */}
      <Route path="/grid-report" element={
        <ProtectedRoute allowedRoles={['super_admin']}>
          <GridReport />
        </ProtectedRoute>
      } />

      {/* Settings placeholder */}
      <Route path="/settings" element={
        <ProtectedRoute>
          <Settings />
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
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
