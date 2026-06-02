import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Search, Users, Filter, Mail, Phone, Building2, Calendar, Plus, Loader2, UserPlus, Edit, Trash2, Bell, Check, ChevronDown } from 'lucide-react';
import api, { formatDate, getRoleLabel, getRoleColor } from '../utils/api';
import { toast } from 'sonner';
import NotificationPreferences from '../components/NotificationPreferences';
import { Checkbox } from '../components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';

// Phase 34: notification preset templates for bulk-apply.
// Each entry sets EVERY notification key explicitly so the merge produces a clean state.
const NOTIF_TEMPLATES = [
  {
    id: 'sales_default',
    name: 'Sales team default',
    description: 'Lead activity, follow-ups, deal-room invites, war-room digest',
    preferences: {
      lead_assigned: true, lead_status_changed: true, lead_won: true,
      follow_up_reminder: true, follow_up_overdue: true,
      milestone_due: false, invoice_overdue: false, payment_received: false,
      commercial_created: false, comment_mention: true, weekly_war_room_digest: true,
    },
  },
  {
    id: 'operations_default',
    name: 'Operations team',
    description: 'Won deals, milestones, follow-ups, comment mentions',
    preferences: {
      lead_assigned: false, lead_status_changed: false, lead_won: true,
      follow_up_reminder: true, follow_up_overdue: true,
      milestone_due: true, invoice_overdue: false, payment_received: false,
      commercial_created: true, comment_mention: true, weekly_war_room_digest: false,
    },
  },
  {
    id: 'finance_default',
    name: 'Finance team',
    description: 'Commercials, invoices, milestones, payments',
    preferences: {
      lead_assigned: false, lead_status_changed: false, lead_won: true,
      follow_up_reminder: false, follow_up_overdue: false,
      milestone_due: true, invoice_overdue: true, payment_received: true,
      commercial_created: true, comment_mention: false, weekly_war_room_digest: false,
    },
  },
  {
    id: 'follow_ups_only',
    name: 'Only follow-up reminders',
    description: 'Mute everything except follow-up nudges',
    preferences: {
      lead_assigned: false, lead_status_changed: false, lead_won: false,
      follow_up_reminder: true, follow_up_overdue: true,
      milestone_due: false, invoice_overdue: false, payment_received: false,
      commercial_created: false, comment_mention: false, weekly_war_room_digest: false,
    },
  },
  {
    id: 'enable_all',
    name: 'Enable all notifications',
    description: 'Turn every email type ON',
    preferences: {
      lead_assigned: true, lead_status_changed: true, lead_won: true,
      follow_up_reminder: true, follow_up_overdue: true,
      milestone_due: true, invoice_overdue: true, payment_received: true,
      commercial_created: true, comment_mention: true, weekly_war_room_digest: true,
    },
  },
  {
    id: 'mute_all',
    name: 'Mute all emails',
    description: 'Turn every email type OFF (in-app bell still works)',
    preferences: {
      lead_assigned: false, lead_status_changed: false, lead_won: false,
      follow_up_reminder: false, follow_up_overdue: false,
      milestone_due: false, invoice_overdue: false, payment_received: false,
      commercial_created: false, comment_mention: false, weekly_war_room_digest: false,
    },
  },
];

const UsersList = () => {
  const { isAdmin, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  
  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: '',
    company_id: '',
    company_name: '',
    phone: '',
    is_finance: false,
    is_delivery: false,
    is_vyapaar_ops: false,
    company_role: '',
    notification_preferences: null,
  });

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Phase 34: Bulk-update selection state
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkApplying, setBulkApplying] = useState(false);
  const [bulkConfirm, setBulkConfirm] = useState(null); // {template, count}

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, companiesRes] = await Promise.all([
        api.get('/users'),
        api.get('/companies').catch(() => ({ data: [] }))
      ]);
      setUsers(usersRes.data);
      setCompanies(companiesRes.data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (user = null) => {
    setEditingUser(user);
    if (user) {
      setFormData({
        name: user.name,
        email: user.email,
        password: '',
        role: user.role,
        company_id: user.company_id || '',
        company_name: '',
        phone: user.phone || '',
        is_finance: !!user.is_finance,
        is_delivery: !!user.is_delivery,
        is_vyapaar_ops: !!user.is_vyapaar_ops
      });
    } else {
      setFormData({
        name: '',
        email: '',
        password: '',
        role: '',
        company_id: '',
        company_name: '',
        phone: '',
        is_finance: false,
        is_delivery: false,
        is_vyapaar_ops: false
      });
    }
    setDialogOpen(true);
  };

  // Phase 34 — Bulk selection helpers
  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allFilteredSelected = (filteredIds) =>
    filteredIds.length > 0 && filteredIds.every((id) => selectedIds.has(id));

  const toggleSelectAll = (filteredIds) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (filteredIds.every((id) => next.has(id))) {
        filteredIds.forEach((id) => next.delete(id));
      } else {
        filteredIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const applyBulkTemplate = async (template) => {
    if (selectedIds.size === 0) {
      toast.error('Select at least one user first.');
      return;
    }
    setBulkApplying(true);
    try {
      const res = await api.post('/users/bulk-notification-preferences', {
        user_ids: Array.from(selectedIds),
        notification_preferences: template.preferences,
        merge: true,
      });
      const { requested, updated } = res.data || {};
      toast.success(`Applied "${template.name}" to ${updated} of ${requested} users.`);
      setSelectedIds(new Set());
      setBulkConfirm(null);
      // Refresh so the updated prefs reflect immediately in edit dialog
      await fetchData();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk update failed');
    } finally {
      setBulkApplying(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.email || !formData.role) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (!editingUser && !formData.password) {
      toast.error('Password is required for new users');
      return;
    }

    if (formData.password && formData.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    // Validate company for roles that need it
    if (['selling_partner', 'customer', 'sales_associate'].includes(formData.role)) {
      if (!formData.company_id && !formData.company_name && formData.role !== 'sales_associate') {
        // For selling_partner and customer, either company_id or company_name is needed
        // Sales associate can optionally be assigned to a company
      }
    }

    setSubmitting(true);
    try {
      if (editingUser) {
        // Update existing user
        const payload = {
          name: formData.name,
          email: formData.email,
          role: formData.role,
          phone: formData.phone || null,
          company_id: formData.company_id || null,
          is_finance: formData.is_finance,
          is_delivery: formData.is_delivery,
          is_vyapaar_ops: formData.is_vyapaar_ops,
          company_role: formData.company_role || null,
          notification_preferences: formData.notification_preferences || {},
        };
        if (formData.password) {
          payload.password = formData.password;
        }
        await api.put(`/users/${editingUser.id}`, payload);
        toast.success('User updated successfully');
      } else {
        // Create new user
        const payload = {
          name: formData.name,
          email: formData.email,
          password: formData.password,
          role: formData.role,
          phone: formData.phone || null,
          company_id: formData.company_id || null,
          company_name: formData.company_id ? null : formData.company_name || null,
          is_finance: formData.is_finance,
          is_delivery: formData.is_delivery,
          is_vyapaar_ops: formData.is_vyapaar_ops,
          company_role: formData.company_role || null,
          notification_preferences: formData.notification_preferences || {},
        };
        await api.post('/users', payload);
        toast.success('User created successfully');
      }
      fetchData();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClick = (user) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;
    
    setDeleting(true);
    try {
      await api.delete(`/users/${userToDelete.id}`);
      toast.success('User deleted successfully');
      fetchData();
      setDeleteDialogOpen(false);
      setUserToDelete(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete user');
    } finally {
      setDeleting(false);
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = 
      user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (user.company_name && user.company_name.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    
    return matchesSearch && matchesRole;
  });

  const roleStats = {
    super_admin: users.filter(u => u.role === 'super_admin').length,
    selling_partner: users.filter(u => u.role === 'selling_partner').length,
    sales_associate: users.filter(u => u.role === 'sales_associate').length,
    customer: users.filter(u => u.role === 'customer').length
  };

  // All companies can be assigned to users
  const getAllCompanies = () => {
    return companies;
  };

  // Check if role needs company
  const needsCompany = ['selling_partner', 'customer', 'sales_associate'].includes(formData.role);
  const canCreateCompany = ['selling_partner', 'customer'].includes(formData.role);

  if (loading) return <UsersSkeleton />;

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground mt-1">
            Manage all platform users and their roles
          </p>
        </div>
        {isAdmin && (
          <Button onClick={() => openDialog()} data-testid="add-user-btn">
            <UserPlus className="w-4 h-4 mr-2" />
            Add User
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Super Admins" value={roleStats.super_admin} color="purple" />
        <StatCard label="Selling Partners" value={roleStats.selling_partner} color="blue" />
        <StatCard label="Sales Associates" value={roleStats.sales_associate} color="green" />
        <StatCard label="Customers" value={roleStats.customer} color="orange" />
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search users..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="user-search-input"
              />
            </div>
            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="w-full sm:w-[180px]" data-testid="role-filter">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="super_admin">Super Admin</SelectItem>
                <SelectItem value="vyapaar_ops">Vyapaar Operations</SelectItem>
                <SelectItem value="vyapaar_finance">Vyapaar Finance</SelectItem>
                <SelectItem value="selling_partner">Selling Partner</SelectItem>
                <SelectItem value="sales_associate">Sales Associate</SelectItem>
                <SelectItem value="customer">Customer</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            All Users ({filteredUsers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Phase 34 — Bulk update toolbar (only when admin + selections present) */}
          {isAdmin && selectedIds.size > 0 && (
            <div
              className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border bg-primary/5 px-4 py-3"
              data-testid="bulk-toolbar"
            >
              <Bell className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium" data-testid="bulk-count">
                {selectedIds.size} user{selectedIds.size === 1 ? '' : 's'} selected
              </span>
              <span className="text-xs text-muted-foreground hidden sm:inline">
                Apply a notification preference template:
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="default" disabled={bulkApplying} data-testid="bulk-template-trigger">
                    {bulkApplying ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Bell className="w-4 h-4 mr-2" />
                    )}
                    Apply template
                    <ChevronDown className="w-4 h-4 ml-1" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-72">
                  <DropdownMenuLabel className="text-xs">Notification presets</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {NOTIF_TEMPLATES.map((t) => (
                    <DropdownMenuItem
                      key={t.id}
                      onClick={() => setBulkConfirm({ template: t, count: selectedIds.size })}
                      data-testid={`bulk-template-${t.id}`}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{t.name}</span>
                        <span className="text-xs text-muted-foreground">{t.description}</span>
                      </div>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedIds(new Set())}
                data-testid="bulk-clear-btn"
              >
                Clear selection
              </Button>
            </div>
          )}

          {filteredUsers.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {isAdmin && (
                      <TableHead className="w-10">
                        <Checkbox
                          checked={allFilteredSelected(filteredUsers.map((u) => u.id))}
                          onCheckedChange={() => toggleSelectAll(filteredUsers.map((u) => u.id))}
                          aria-label="Select all visible users"
                          data-testid="bulk-select-all"
                        />
                      </TableHead>
                    )}
                    <TableHead>User</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Joined</TableHead>
                    {isAdmin && <TableHead className="w-[100px]">Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => (
                    <TableRow key={user.id} data-testid={`user-row-${user.id}`} className={selectedIds.has(user.id) ? 'bg-primary/5' : ''}>
                      {isAdmin && (
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.has(user.id)}
                            onCheckedChange={() => toggleSelect(user.id)}
                            aria-label={`Select ${user.name}`}
                            data-testid={`bulk-select-${user.id}`}
                          />
                        </TableCell>
                      )}
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center">
                            <span className="text-sm font-medium text-primary">
                              {user.name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium">{user.name}</p>
                            <p className="text-xs text-muted-foreground">{user.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={getRoleColor(user.role)}>
                          {getRoleLabel(user.role)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.company_name ? (
                          <div className="flex items-center gap-1 text-sm">
                            <Building2 className="w-3 h-3 text-muted-foreground" />
                            {user.company_name}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {user.phone && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Phone className="w-3 h-3" />
                            {user.phone}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? 'default' : 'secondary'}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <Calendar className="w-3 h-3" />
                          {formatDate(user.created_at)}
                        </div>
                      </TableCell>
                      {isAdmin && (
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button 
                              size="icon" 
                              variant="ghost"
                              onClick={() => openDialog(user)}
                              data-testid={`edit-user-${user.id}`}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            {user.id !== currentUser?.id && (
                              <Button 
                                size="icon" 
                                variant="ghost"
                                className="text-destructive hover:text-destructive"
                                onClick={() => handleDeleteClick(user)}
                                data-testid={`delete-user-${user.id}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <Users className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="font-semibold mb-1">No users found</h3>
              <p className="text-muted-foreground text-sm">
                Try adjusting your search or filter
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit User Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-4xl w-[95vw] max-h-[92vh] flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b">
            <DialogTitle>{editingUser ? 'Edit User' : 'Add New User'}</DialogTitle>
            <DialogDescription>
              {editingUser ? 'Update user details, role assignments, and notification preferences.' : 'Create a new user account. All user types can be created here.'}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-5">

              {/* ============ LEFT COLUMN — Identity & access ============ */}
              <div className="space-y-5">
                <div>
                  <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3">Identity</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-sm">Full Name *</Label>
                      <Input
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="John Doe"
                        data-testid="user-name-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-sm">Role *</Label>
                      <Select
                        value={formData.role}
                        onValueChange={(v) => setFormData({ ...formData, role: v, company_id: '', company_name: '' })}
                      >
                        <SelectTrigger data-testid="user-role-select">
                          <SelectValue placeholder="Select role" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="super_admin">Super Admin</SelectItem>
                          <SelectItem value="vyapaar_ops">Vyapaar Operations</SelectItem>
                          <SelectItem value="vyapaar_finance">Vyapaar Finance</SelectItem>
                          <SelectItem value="selling_partner">Selling Partner</SelectItem>
                          <SelectItem value="sales_associate">Sales Associate</SelectItem>
                          <SelectItem value="customer">Customer</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div className="space-y-1.5">
                      <Label className="text-sm">Email *</Label>
                      <Input
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="user@example.com"
                        data-testid="user-email-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-sm">Phone (Optional)</Label>
                      <Input
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        placeholder="+91 98765 43210"
                        data-testid="user-phone-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5 mt-3">
                    <Label className="text-sm">{editingUser ? 'New Password (leave blank to keep current)' : 'Password *'}</Label>
                    <Input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      placeholder={editingUser ? '••••••••' : 'Minimum 6 characters'}
                      data-testid="user-password-input"
                    />
                  </div>
                </div>

                {/* Vyapaar team flags */}
                <div>
                  <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3">Vyapaar Team Roles (optional)</h3>
                  <div className="space-y-2 border rounded-md p-3 bg-muted/30">
                    <label className="flex items-start gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.is_vyapaar_ops}
                        onChange={(e) => setFormData({ ...formData, is_vyapaar_ops: e.target.checked })}
                        className="w-4 h-4 mt-0.5"
                        data-testid="user-is-vyapaar-ops"
                      />
                      <span><strong>Vyapaar Operations</strong> — full app access except user/company/category creation</span>
                    </label>
                    <label className="flex items-start gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.is_finance}
                        onChange={(e) => setFormData({ ...formData, is_finance: e.target.checked })}
                        className="w-4 h-4 mt-0.5"
                        data-testid="user-is-finance"
                      />
                      <span><strong>Vyapaar Finance</strong> — raise invoices, record payments, see analytics</span>
                    </label>
                    <label className="flex items-start gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.is_delivery}
                        onChange={(e) => setFormData({ ...formData, is_delivery: e.target.checked })}
                        className="w-4 h-4 mt-0.5"
                        data-testid="user-is-delivery"
                      />
                      <span><strong>Delivery Lead</strong> — update milestone status, manage commercials</span>
                    </label>
                  </div>
                </div>

                {/* Company assignment */}
                {needsCompany && (
                  <div>
                    <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3">Company</h3>
                    <div className="space-y-3">
                      <div className="space-y-1.5">
                        <Label className="text-sm">Assign to Company {formData.role === 'sales_associate' ? '(Optional)' : ''}</Label>
                        <Select
                          value={formData.company_id || '__none__'}
                          onValueChange={(v) => setFormData({ ...formData, company_id: v === '__none__' ? '' : v, company_name: '' })}
                        >
                          <SelectTrigger data-testid="user-company-select">
                            <SelectValue placeholder="Select company" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">None</SelectItem>
                            {getAllCompanies().map((company) => (
                              <SelectItem key={company.id} value={company.id}>
                                {company.name} ({company.type === 'selling_partner' ? 'Partner' : 'Customer'})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {canCreateCompany && !formData.company_id && !editingUser && (
                        <div className="space-y-1.5">
                          <Label className="text-sm">Or Create New Company</Label>
                          <Input
                            value={formData.company_name}
                            onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                            placeholder="New company name"
                            data-testid="user-new-company-input"
                          />
                          <p className="text-xs text-muted-foreground">
                            A new {formData.role === 'selling_partner' ? 'selling partner' : 'customer'} company will be created
                          </p>
                        </div>
                      )}

                      {['selling_partner', 'customer'].includes(formData.role) && (
                        <div className="space-y-1.5">
                          <Label className="text-sm">Profile within Company</Label>
                          <Select
                            value={formData.company_role || '__unset__'}
                            onValueChange={(v) => setFormData({ ...formData, company_role: v === '__unset__' ? '' : v })}
                          >
                            <SelectTrigger data-testid="user-company-role-select">
                              <SelectValue placeholder="Select profile" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__unset__">Not specified</SelectItem>
                              <SelectItem value="founder">Founder / CXO — full company access</SelectItem>
                              <SelectItem value="sales">Sales — leads, war room, deal rooms</SelectItem>
                              <SelectItem value="operations">Operations — post-closure leads, follow-ups, delivery</SelectItem>
                              <SelectItem value="finance">Finance — commercials, invoices, payments</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-muted-foreground">
                            Controls what menus &amp; data this user can access. Founder = unrestricted.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* ============ RIGHT COLUMN — Email notifications ============ */}
              <div className="lg:border-l lg:pl-8">
                <NotificationPreferences
                  compact
                  value={formData.notification_preferences || {}}
                  onChange={(next) => setFormData({ ...formData, notification_preferences: next })}
                  testIdPrefix="user-notif"
                />
              </div>

            </div>
          </div>

          <DialogFooter className="px-6 py-4 border-t bg-muted/30">
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="user-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {editingUser ? 'Updating...' : 'Creating...'}
                </>
              ) : (
                <>
                  {editingUser ? <Edit className="w-4 h-4 mr-2" /> : <UserPlus className="w-4 h-4 mr-2" />}
                  {editingUser ? 'Update User' : 'Create User'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{userToDelete?.name}</strong>? 
              This action will deactivate the user account.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDeleteConfirm}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Phase 34 — Bulk template apply confirmation */}
      <AlertDialog open={!!bulkConfirm} onOpenChange={(o) => { if (!o) setBulkConfirm(null); }}>
        <AlertDialogContent data-testid="bulk-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Apply "{bulkConfirm?.template?.name}"?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm">
                <p>
                  This will update the notification preferences for <strong>{bulkConfirm?.count}</strong> selected
                  user{bulkConfirm?.count === 1 ? '' : 's'}.
                </p>
                {bulkConfirm?.template?.description && (
                  <p className="text-muted-foreground">{bulkConfirm.template.description}</p>
                )}
                <div className="rounded-md border bg-muted/40 p-3">
                  <p className="text-xs font-semibold mb-2">Template enables:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(bulkConfirm?.template?.preferences || {})
                      .filter(([, v]) => v)
                      .map(([k]) => (
                        <span key={k} className="text-xs bg-green-100 text-green-700 rounded px-1.5 py-0.5">
                          {k.replace(/_/g, ' ')}
                        </span>
                      ))}
                    {Object.values(bulkConfirm?.template?.preferences || {}).every((v) => !v) && (
                      <span className="text-xs text-muted-foreground">Nothing — everything will be muted</span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Existing preferences for other notification types (if any) will be preserved.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkApplying}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => applyBulkTemplate(bulkConfirm.template)}
              disabled={bulkApplying}
              data-testid="bulk-confirm-apply"
            >
              {bulkApplying ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Applying...</>
              ) : (
                <><Check className="w-4 h-4 mr-2" />Apply</>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const StatCard = ({ label, value, color }) => {
  const colorClasses = {
    purple: 'bg-purple-100 text-purple-600',
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    orange: 'bg-orange-100 text-orange-600'
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
          </div>
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Users className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const UsersSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-32 mb-2" />
      <Skeleton className="h-4 w-48" />
    </div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardContent className="pt-6">
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default UsersList;
