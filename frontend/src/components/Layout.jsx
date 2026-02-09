import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Avatar, AvatarFallback } from './ui/avatar';
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
  Bell
} from 'lucide-react';
import { getRoleLabel } from '../utils/api';

const LOGO_URL = "https://customer-assets.emergentagent.com/job_209b3ec1-0b0e-469f-a49b-80bce3fa5de7/artifacts/8t9iukb4_Vyapaar-Logo.png";

const Layout = ({ children }) => {
  const { user, logout, isAdmin, isSellingPartner, isSalesAssociate, isCustomer } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getNavItems = () => {
    const items = [
      { 
        label: 'Dashboard', 
        icon: LayoutDashboard, 
        path: '/dashboard',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'customer']
      },
      { 
        label: 'Leads', 
        icon: FileText, 
        path: '/leads',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'customer']
      },
    ];

    if (isAdmin) {
      items.push(
        { label: 'Users', icon: Users, path: '/users', roles: ['super_admin'] },
        { label: 'Companies', icon: Building2, path: '/companies', roles: ['super_admin'] },
        { label: 'Categories', icon: Tag, path: '/categories', roles: ['super_admin'] },
        { label: 'Commission', icon: Percent, path: '/commission', roles: ['super_admin'] },
      );
    }

    items.push({ 
      label: 'Reports', 
      icon: BarChart3, 
      path: '/reports',
      roles: ['super_admin', 'selling_partner', 'sales_associate']
    });

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
          {!sidebarCollapsed && (
            <Link to="/dashboard" className="flex items-center gap-2">
              <img src={LOGO_URL} alt="Vyapaar Network" className="h-8 w-auto" />
            </Link>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="text-slate-400 hover:text-white hover:bg-slate-800"
            data-testid="sidebar-toggle"
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </Button>
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
            <img src={LOGO_URL} alt="Vyapaar Network" className="h-8 w-auto" />
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
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Header */}
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-30">
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
                <img src={LOGO_URL} alt="Vyapaar Network" className="h-8 w-auto" />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="text-slate-600">
                <Bell className="w-5 h-5" />
              </Button>
              
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

        {/* Page Content */}
        <main className="flex-1 p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
