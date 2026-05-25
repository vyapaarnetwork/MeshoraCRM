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
import { 
  LayoutDashboard, 
  Users, 
  FileText, 
  Settings, 
  LogOut, 
  ChevronLeft,
  ChevronRight,
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
  Sparkles
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

  const handleLogout = () => {
    logout();
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

    // Phase 2: Revenue Intelligence — admin-like roles + selling partners
    if (isAdmin || isFinance || isDelivery || isVyapaarOps || isVyapaarFinance || isSellingPartner) {
      items.push({
        label: 'Revenue Intelligence',
        icon: TrendingUp,
        path: '/revenue-intelligence',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance', 'selling_partner'],
      });
    }

    return items.filter(item => item.roles.includes(user?.role));
  };

  const navItems = getNavItems();

  const NavLink = ({ item }) => {
    const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + '/');
    const Icon = item.icon;
    
    return (
      <Link
        to={item.path}
        data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
        onClick={() => setMobileMenuOpen(false)}
        className={`
          flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200
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
    );
  };

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

        {/* Nav Items */}
        <ScrollArea className="flex-1 py-4 px-3">
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink key={item.path} item={item} />
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

        <ScrollArea className="flex-1 py-4 px-3 h-[calc(100vh-8rem)]">
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink key={item.path} item={item} />
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
              {/* Notifications Dropdown */}
              <DropdownMenu open={notificationsOpen} onOpenChange={setNotificationsOpen}>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="text-slate-600 relative" data-testid="notifications-btn">
                    <Bell className="w-5 h-5" />
                    {unreadCount > 0 && (
                      <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-80">
                  <DropdownMenuLabel className="flex items-center justify-between">
                    <span>Notifications</span>
                    {unreadCount > 0 && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-xs h-auto py-1"
                        onClick={markAllAsRead}
                      >
                        <Check className="w-3 h-3 mr-1" />
                        Mark all read
                      </Button>
                    )}
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <ScrollArea className="h-[300px]">
                    {notifications.length > 0 ? (
                      notifications.map((notification) => (
                        <DropdownMenuItem
                          key={notification.id}
                          className={`flex items-start gap-3 p-3 cursor-pointer ${!notification.is_read ? 'bg-blue-50' : ''}`}
                          onClick={() => handleNotificationClick(notification)}
                        >
                          <div className="mt-0.5">
                            {getNotificationIcon(notification.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm ${!notification.is_read ? 'font-semibold' : ''}`}>
                              {notification.title}
                            </p>
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {notification.message}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {formatTimeAgo(notification.created_at)}
                            </p>
                          </div>
                          {notification.lead_id && (
                            <ExternalLink className="w-3 h-3 text-muted-foreground" />
                          )}
                        </DropdownMenuItem>
                      ))
                    ) : (
                      <div className="p-4 text-center text-muted-foreground text-sm">
                        No notifications
                      </div>
                    )}
                  </ScrollArea>
                </DropdownMenuContent>
              </DropdownMenu>
              
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
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive" data-testid="logout-menu-item">
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
