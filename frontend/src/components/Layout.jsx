import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Button } from './ui/button';
import { Avatar, AvatarFallback } from './ui/avatar';
import { Badge } from './ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { ScrollArea } from './ui/scroll-area';
import NotificationsPanel from './NotificationsPanel';
import { 
  LayoutDashboard, 
  Users, 
  FileText, 
  Settings, 
  LogOut, 
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Building2,
  Tag,
  Percent,
  BarChart3,
  Menu,
  X,
  Bell,
  Send,
  Check,
  Clock,
  ExternalLink,
  Grid3X3,
  Paperclip,
  Mail,
  Network,
  ShoppingCart,
  UserPlus,
  Sun,
  Moon,
  Briefcase,
  TrendingUp,
  Sparkles,
  Trophy,
  HelpCircle,
  Swords,
  Activity,
  Target,
  PieChart,
  CalendarRange,
  ListTodo,
  Save as SaveIcon,
} from 'lucide-react';
import { getRoleLabel } from '../utils/api';
import api from '../utils/api';
import { MeshoraMark, MeshoraLogoOnDark } from './MeshoraLogo';
import RoleContextBanner from './RoleContextBanner';
import CommandBar from './CommandBar';

// Vyapaar small mark for "Powered by" footer
const VYAPAAR_LOGO_URL = "https://customer-assets.emergentagent.com/job_209b3ec1-0b0e-469f-a49b-80bce3fa5de7/artifacts/8t9iukb4_Vyapaar-Logo.png";

const Layout = ({ children }) => {
  const { user, logout, isAdmin, isSellingPartner, isSalesAssociate, isCustomer, isFinance, isDelivery, isVyapaarOps, isVyapaarFinance, canAccessCommercials } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  // Notifications state
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    try {
      const [notifRes, countRes] = await Promise.all([
        api.get('/notifications?limit=10'),
        api.get('/notifications/unread-count')
      ]);
      setNotifications(notifRes.data);
      setUnreadCount(countRes.data.count);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    // Poll for new notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Phase 3: Cmd+K / Ctrl+K opens the AI command bar
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const markAsRead = async (notificationId) => {
    try {
      await api.put(`/notifications/${notificationId}/read`);
      fetchNotifications();
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await api.put('/notifications/mark-all-read');
      fetchNotifications();
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error);
    }
  };

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id);
    // Prefer commercial deep-link for commercials reminders
    if (notification.commercial_id && (notification.type || '').startsWith('commercial_')) {
      navigate(`/commercials/${notification.commercial_id}`);
      setNotificationsOpen(false);
    } else if ((notification.type || '').startsWith('internal_task_') && notification.data?.internal_task_id) {
      // Phase 36 — Internal Task mentions / assignments deep-link to the task page
      navigate(`/internal-tasks?focus=${notification.data.internal_task_id}`);
      setNotificationsOpen(false);
    } else if (notification.lead_id) {
      navigate(`/leads/${notification.lead_id}`);
      setNotificationsOpen(false);
    }
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'new_lead':
      case 'new_referral':
        return <FileText className="w-4 h-4 text-blue-500" />;
      case 'lead_assigned':
        return <Users className="w-4 h-4 text-green-500" />;
      case 'commercial_milestone_due':
      case 'commercial_billing_due':
        return <Briefcase className="w-4 h-4 text-amber-500" />;
      case 'commercial_invoice_overdue':
        return <Briefcase className="w-4 h-4 text-red-500" />;
      case 'commercial_renewal_window':
        return <Briefcase className="w-4 h-4 text-blue-500" />;
      case 'internal_task_mention':
      case 'internal_task_assigned':
        return <ListTodo className="w-4 h-4 text-violet-500" />;
      case 'lead_status_change':
        return <Tag className="w-4 h-4 text-purple-500" />;
      case 'lead_updated':
        return <Clock className="w-4 h-4 text-orange-500" />;
      default:
        return <Bell className="w-4 h-4 text-gray-500" />;
    }
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const getNavItems = () => {
    // Phase 18: vyapaar_ops & vyapaar_finance get the admin surface
    const ADMIN_ROLES = ['super_admin', 'vyapaar_ops', 'vyapaar_finance'];
    const ALL_ROLES = ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner', 'sales_associate', 'customer'];

    const items = [
      {
        label: 'Dashboard',
        icon: LayoutDashboard,
        path: '/dashboard',
        roles: ALL_ROLES
      },
      {
        label: 'Leads',
        icon: FileText,
        path: '/leads',
        roles: ALL_ROLES
      },
    ];

    // Lead Referral menu for Selling Partners AND Sales Associates
    if (isSellingPartner || isSalesAssociate) {
      items.push({
        label: 'Lead Referral',
        icon: Send,
        path: '/lead-referral',
        roles: ['selling_partner', 'sales_associate']
      });
    }

    // Internal Requests - Selling Partners Only
    if (isSellingPartner) {
      items.push({
        label: 'Internal Requests',
        icon: ShoppingCart,
        path: '/internal-requests',
        roles: ['selling_partner']
      });
    }

    // Company Users - Customers Only
    if (isCustomer) {
      items.push({
        label: 'Team Members',
        icon: UserPlus,
        path: '/company-users',
        roles: ['customer']
      });
    }

    if (isAdmin || isVyapaarOps || isVyapaarFinance) {
      items.push(
        { label: 'Users', icon: Users, path: '/users', roles: ADMIN_ROLES },
        { label: 'Companies', icon: Building2, path: '/companies', roles: ADMIN_ROLES },
        { label: 'Categories', icon: Tag, path: '/categories', roles: ADMIN_ROLES },
        { label: 'Partner Mappings', icon: Network, path: '/partner-mappings', roles: ADMIN_ROLES },
        { label: 'Commission', icon: Percent, path: '/commission', roles: ADMIN_ROLES },
        { label: 'Document Tags', icon: Paperclip, path: '/document-tags', roles: ADMIN_ROLES },
        { label: 'Email Templates', icon: Mail, path: '/email-templates', roles: ADMIN_ROLES },
        { label: 'Grid Report', icon: Grid3X3, path: '/grid-report', roles: ADMIN_ROLES },
      );
    }

    // Commercials (Revenue Contracting & Delivery)
    if (canAccessCommercials) {
      items.push({
        label: 'Commercials',
        icon: Briefcase,
        path: '/commercials',
        roles: ALL_ROLES,
      });
      items.push({
        label: 'Commercials Kanban',
        icon: Grid3X3,
        path: '/commercials/kanban',
        roles: ALL_ROLES,
      });
      if (isAdmin || isFinance || isDelivery || isVyapaarOps || isVyapaarFinance) {
        items.push({
          label: 'Revenue Analytics',
          icon: BarChart3,
          path: '/commercials/analytics',
          roles: ALL_ROLES,
        });
      }
    }

    items.push({
      label: 'Reports',
      icon: BarChart3,
      path: '/reports',
      roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner', 'sales_associate']
    });

    // Phase 34.6: Won Leads Report — Vyapaar team only
    if (isAdmin || isVyapaarOps || isVyapaarFinance) {
      items.push({
        label: 'Won Leads',
        icon: Trophy,
        path: '/reports/won-leads',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance'],
      });
    }

    // Phase 29: Weekly War Room — for everyone who works leads
    if (isAdmin || isVyapaarOps || isVyapaarFinance || isSellingPartner || isSalesAssociate) {
      items.push({
        label: 'War Room',
        icon: Swords,
        path: '/war-room',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner', 'sales_associate'],
      });
    }

    // Phase 36: Internal Vyapaar Tasks — internal team only
    if (isAdmin || isVyapaarOps || isVyapaarFinance) {
      items.push({
        label: 'Internal Tasks',
        icon: ListTodo,
        path: '/internal-tasks',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance'],
      });
    }

    // Phase 2: Revenue Intelligence — admin-like roles + selling partners
    if (isAdmin || isFinance || isDelivery || isVyapaarOps || isVyapaarFinance || isSellingPartner) {
      items.push({
        label: 'Revenue Intelligence',
        icon: TrendingUp,
        path: '/revenue-intelligence',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner'],
      });
      items.push({
        label: 'Predictive Forecast',
        icon: Sparkles,
        path: '/predictive-forecast',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner'],
      });
      // Phase 25: Partner Intelligence Layer (admin/ops only — RBAC enforced in backend)
      if (isAdmin || isVyapaarOps || isVyapaarFinance) {
        items.push({
          label: 'Partner Intelligence',
          icon: Trophy,
          path: '/partner-intelligence',
          roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance'],
        });
      }
    }

    return items.filter(item => {
      if (!item.roles.includes(user?.role)) return false;
      // Phase 30: enforce company_role gating for Customer & Selling Partner
      // sub-profiles. Founder = unrestricted; others see only relevant menus.
      const sub = user?.company_role;
      const isCustomerOrPartner = ['customer', 'selling_partner'].includes(user?.role);
      if (!isCustomerOrPartner || !sub || sub === 'founder') return true;
      const path = item.path;
      if (sub === 'sales') {
        return ['/dashboard', '/leads', '/lead-referral', '/internal-requests',
          '/war-room', '/reports'].includes(path);
      }
      if (sub === 'operations') {
        return ['/dashboard', '/leads', '/commercials', '/commercials/kanban',
          '/reports'].includes(path);
      }
      if (sub === 'finance') {
        return ['/dashboard', '/commercials', '/commercials/kanban',
          '/commercials/analytics', '/revenue-intelligence', '/reports'].includes(path);
      }
      return true;
    });
  };

  const navItems = getNavItems();

  // Phase 34.7 — Categorize the flat nav into section groups (CORE / MANAGE / COMMERCIALS / ANALYTICS / INTELLIGENCE).
  // Reports gets a nested submenu showing all the new sub-reports.
  const buildNavGroups = () => {
    const byPath = Object.fromEntries(navItems.map(i => [i.path, i]));
    const has = (p) => Boolean(byPath[p]);

    const reportsSubmenu = [
      { label: 'Won Leads',           icon: Trophy,        path: '/reports/won-leads',           visible: has('/reports/won-leads') },
      { label: 'Pipeline Report',     icon: PieChart,      path: '/reports/pipeline',            visible: has('/reports') },
      { label: 'Lead Activity',       icon: Activity,      path: '/reports/lead-activity',       visible: (isAdmin || isVyapaarOps || isVyapaarFinance) },
      { label: 'Conversion Report',   icon: Target,        path: '/reports/conversion',          visible: has('/reports') },
      { label: 'Partner Performance', icon: Trophy,        path: '/reports/partner-performance', visible: (isAdmin || isVyapaarOps || isVyapaarFinance) },
      { label: 'My Reports',          icon: SaveIcon,      path: '/reports/saved',               visible: has('/reports') },
      { label: 'Scheduled Reports',   icon: CalendarRange, path: '/reports/scheduled',           visible: (isAdmin || isVyapaarOps) },
    ].filter(s => s.visible);

    const groups = [
      {
        title: 'Core',
        items: [
          has('/dashboard') && byPath['/dashboard'],
          has('/leads') && byPath['/leads'],
          has('/internal-tasks') && byPath['/internal-tasks'],
          has('/lead-referral') && byPath['/lead-referral'],
          has('/internal-requests') && byPath['/internal-requests'],
          has('/company-users') && byPath['/company-users'],
        ].filter(Boolean),
      },
      {
        title: 'Manage',
        items: [
          has('/users') && byPath['/users'],
          has('/companies') && byPath['/companies'],
          has('/categories') && byPath['/categories'],
          has('/partner-mappings') && byPath['/partner-mappings'],
          has('/commission') && byPath['/commission'],
          has('/document-tags') && byPath['/document-tags'],
          has('/email-templates') && byPath['/email-templates'],
        ].filter(Boolean),
      },
      {
        title: 'Commercials',
        items: [
          has('/commercials') && byPath['/commercials'],
          has('/commercials/kanban') && byPath['/commercials/kanban'],
          has('/commercials/analytics') && byPath['/commercials/analytics'],
        ].filter(Boolean),
      },
      {
        title: 'Analytics',
        items: [
          has('/reports') && { ...byPath['/reports'], submenu: reportsSubmenu },
          has('/grid-report') && byPath['/grid-report'],
        ].filter(Boolean),
      },
      {
        title: 'Intelligence',
        items: [
          has('/war-room') && byPath['/war-room'],
          has('/revenue-intelligence') && byPath['/revenue-intelligence'],
          has('/predictive-forecast') && byPath['/predictive-forecast'],
          has('/partner-intelligence') && byPath['/partner-intelligence'],
        ].filter(Boolean),
      },
    ];

    return groups.filter(g => g.items.length > 0);
  };

  const navGroups = buildNavGroups();

  // Active-check helper used by both top-level + submenu items
  const isPathActive = (path) =>
    location.pathname === path || location.pathname.startsWith(path + '/');

  // Track which group has its Reports submenu open (auto-open if on a /reports/* path).
  const [openSubmenu, setOpenSubmenu] = useState(() =>
    location.pathname.startsWith('/reports') ? '/reports' : null
  );
  useEffect(() => {
    if (location.pathname.startsWith('/reports')) setOpenSubmenu('/reports');
  }, [location.pathname]);

  const NavLink = useCallback(({ item }) => {
    const isActive = isPathActive(item.path);
    const Icon = item.icon;
    const hasSubmenu = Array.isArray(item.submenu) && item.submenu.length > 0;
    const expanded = openSubmenu === item.path;

    return (
      <div>
        <div className={`flex items-center ${sidebarCollapsed ? 'justify-center' : ''}`}>
          <Link
            to={item.path}
            data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            onClick={() => setMobileMenuOpen(false)}
            className={`
              flex-1 flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200
              ${isActive
                ? 'bg-primary text-white shadow-md'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }
              ${sidebarCollapsed ? 'justify-center' : ''}
            `}
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && (
              <span className="font-medium text-sm">{item.label}</span>
            )}
          </Link>
          {hasSubmenu && !sidebarCollapsed && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setOpenSubmenu(expanded ? null : item.path); }}
              className="ml-1 p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800"
              aria-label={expanded ? 'Collapse submenu' : 'Expand submenu'}
              data-testid={`submenu-toggle-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>
        {hasSubmenu && expanded && !sidebarCollapsed && (
          <div className="mt-1 ml-7 flex flex-col gap-0.5 border-l border-slate-700/60 pl-3">
            {item.submenu.map((sub) => {
              const SubIcon = sub.icon;
              const subActive = isPathActive(sub.path);
              return (
                <Link
                  key={sub.path}
                  to={sub.path}
                  onClick={() => setMobileMenuOpen(false)}
                  data-testid={`nav-sub-${sub.label.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`
                    flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors
                    ${subActive
                      ? 'bg-violet-500/20 text-white'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'}
                  `}
                >
                  <SubIcon className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="truncate">{sub.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    );
  }, [isPathActive, openSubmenu, sidebarCollapsed]);

  const NavSection = useCallback(({ group }) => (
    <div className="mb-3">
      {!sidebarCollapsed && (
        <div className="px-3 pt-1 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">
          {group.title}
        </div>
      )}
      <div className="space-y-1">
        {group.items.map((item) => <NavLink key={item.path} item={item} />)}
      </div>
    </div>
  ), [NavLink, sidebarCollapsed]);

  return (
    <div className="min-h-screen bg-background flex">
      {/* Desktop Sidebar */}
      <aside 
        className={`
          hidden lg:flex flex-col bg-[#0F172A] border-r border-slate-800
          transition-all duration-300 ease-in-out
          ${sidebarCollapsed ? 'w-16' : 'w-64'}
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800">
          {sidebarCollapsed ? (
            <button 
              onClick={() => setSidebarCollapsed(false)}
              className="flex items-center mx-auto"
              title="Expand sidebar"
              data-testid="sidebar-expand-btn"
            >
              <MeshoraMark size={32} />
            </button>
          ) : (
            <>
              <Link to="/dashboard" className="flex items-center" data-testid="sidebar-logo-link">
                <MeshoraLogoOnDark size={32} showTagline={false} />
              </Link>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarCollapsed(true)}
                className="text-slate-400 hover:text-white hover:bg-slate-800"
                data-testid="sidebar-toggle"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
            </>
          )}
        </div>

        {/* Nav Items (Phase 34.7 — grouped by section) */}
        <ScrollArea className="flex-1 py-3 px-3">
          <nav className="space-y-0.5">
            {navGroups.map((g) => (
              <NavSection key={g.title} group={g} />
            ))}
          </nav>
        </ScrollArea>

        {/* User Info */}
        <div className={`p-4 border-t border-slate-800 ${sidebarCollapsed ? 'flex justify-center' : ''}`}>
          {!sidebarCollapsed ? (
            <div className="flex items-center gap-3">
              <Avatar className="h-9 w-9 bg-primary">
                <AvatarFallback className="bg-primary text-white text-sm">
                  {user?.name?.charAt(0)?.toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{user?.name}</p>
                <p className="text-xs text-slate-400 truncate">{getRoleLabel(user?.role)}</p>
              </div>
            </div>
          ) : (
            <Avatar className="h-9 w-9 bg-primary">
              <AvatarFallback className="bg-primary text-white text-sm">
                {user?.name?.charAt(0)?.toUpperCase()}
              </AvatarFallback>
            </Avatar>
          )}
        </div>

        {/* Powered by Vyapaar Network footer */}
        <div
          className={`px-3 py-2 border-t border-slate-800 bg-slate-900/40 ${sidebarCollapsed ? 'flex justify-center' : ''}`}
          data-testid="powered-by-footer"
        >
          {!sidebarCollapsed ? (
            <div className="flex items-center gap-2 text-[10px] text-slate-400 leading-tight">
              <span className="uppercase tracking-wider">Powered by</span>
              <img src={VYAPAAR_LOGO_URL} alt="Vyapaar Network" className="h-4 w-auto" />
              <span className="font-medium text-slate-300">Vyapaar Network</span>
            </div>
          ) : (
            <img src={VYAPAAR_LOGO_URL} alt="Vyapaar Network" title="Powered by Vyapaar Network" className="h-5 w-auto" />
          )}
        </div>
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile Sidebar */}
      <aside 
        className={`
          fixed top-0 left-0 h-full w-64 bg-[#0F172A] z-50 lg:hidden
          transform transition-transform duration-300 ease-in-out
          ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800">
          <Link to="/dashboard" className="flex items-center gap-2" onClick={() => setMobileMenuOpen(false)}>
            <MeshoraLogoOnDark size={32} showTagline={false} />
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileMenuOpen(false)}
            className="text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        <ScrollArea className="flex-1 py-3 px-3 h-[calc(100vh-8rem)]">
          <nav className="space-y-0.5">
            {navGroups.map((g) => (
              <NavSection key={g.title} group={g} />
            ))}
          </nav>
        </ScrollArea>

        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <Avatar className="h-9 w-9 bg-primary">
              <AvatarFallback className="bg-primary text-white text-sm">
                {user?.name?.charAt(0)?.toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.name}</p>
              <p className="text-xs text-slate-400 truncate">{getRoleLabel(user?.role)}</p>
            </div>
          </div>
        </div>

        {/* Powered by Vyapaar Network footer (mobile) */}
        <div className="px-3 py-2 border-t border-slate-800 bg-slate-900/40">
          <div className="flex items-center gap-2 text-[10px] text-slate-400">
            <span className="uppercase tracking-wider">Powered by</span>
            <img src={VYAPAAR_LOGO_URL} alt="Vyapaar Network" className="h-4 w-auto" />
            <span className="font-medium text-slate-300">Vyapaar Network</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Header */}
        <header className="h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 sticky top-0 z-30">
          <div className="h-full px-4 lg:px-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setMobileMenuOpen(true)}
                data-testid="mobile-menu-btn"
              >
                <Menu className="w-5 h-5" />
              </Button>
              <div className="lg:hidden">
                <MeshoraMark size={32} />
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Theme Toggle */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCommandOpen(true)}
                className="hidden md:inline-flex gap-2 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                data-testid="ai-command-btn"
                title="AI Command Bar (Cmd+K)"
              >
                <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                <span className="text-xs">Ask Meshora…</span>
                <kbd className="ml-1 px-1.5 py-0.5 rounded bg-muted text-[9px] uppercase">⌘K</kbd>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCommandOpen(true)}
                className="md:hidden text-slate-600 dark:text-slate-300"
                data-testid="ai-command-btn-mobile"
                aria-label="AI Command"
              >
                <Sparkles className="w-5 h-5 text-violet-500" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="text-slate-600 dark:text-slate-300"
                data-testid="theme-toggle-btn"
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </Button>
              {/* Phase 34.7.3 — Notifications sheet (right slide-over, categorized) */}
              <Button
                variant="ghost"
                size="icon"
                className="text-slate-600 relative"
                data-testid="notifications-btn"
                onClick={() => setNotificationsOpen(true)}
              >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </Button>
              <NotificationsPanel
                open={notificationsOpen}
                onOpenChange={setNotificationsOpen}
                notifications={notifications}
                unreadCount={unreadCount}
                onNotificationClick={handleNotificationClick}
                onMarkAllRead={markAllAsRead}
              />
              
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2" data-testid="user-menu-btn">
                    <Avatar className="h-8 w-8 bg-primary">
                      <AvatarFallback className="bg-primary text-white text-sm">
                        {user?.name?.charAt(0)?.toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <span className="hidden sm:inline text-sm font-medium">{user?.name}</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>
                    <div className="flex flex-col">
                      <span>{user?.name}</span>
                      <span className="text-xs font-normal text-muted-foreground">{user?.email}</span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/settings')} data-testid="settings-menu-item">
                    <Settings className="w-4 h-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/help')} data-testid="help-menu-item">
                    <HelpCircle className="w-4 h-4 mr-2" />
                    Help & Feature Guide
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive" data-testid="logout-btn">
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        {/* Phase 18: Role context banner for Vyapaar Operations / Finance users */}
        {user?.role === 'vyapaar_ops' && <RoleContextBanner role="vyapaar_ops" />}
        {user?.role === 'vyapaar_finance' && <RoleContextBanner role="vyapaar_finance" />}

        {/* Phase 3: AI Command Bar */}
        <CommandBar open={commandOpen} onOpenChange={setCommandOpen} />

        {/* Page Content */}
        <main className="flex-1 p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
