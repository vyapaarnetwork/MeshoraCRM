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
import { Search, Users, Filter, Mail, Phone, Building2, Calendar, Plus, Loader2, UserPlus, Edit, Trash2 } from 'lucide-react';
import api, { formatDate, getRoleLabel, getRoleColor } from '../utils/api';
import { toast } from 'sonner';

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
    is_vyapaar_ops: false
  });

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

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
          is_vyapaar_ops: formData.is_vyapaar_ops
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
          is_vyapaar_ops: formData.is_vyapaar_ops
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
          {filteredUsers.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
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
                    <TableRow key={user.id} data-testid={`user-row-${user.id}`}>
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
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Edit User' : 'Add New User'}</DialogTitle>
            <DialogDescription>
              {editingUser ? 'Update user details and settings' : 'Create a new user account. All user types can be created here.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Full Name *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="John Doe"
                  data-testid="user-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Role *</Label>
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

            <div className="space-y-2">
              <Label>Email *</Label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="user@example.com"
                data-testid="user-email-input"
              />
            </div>

            <div className="space-y-2">
              <Label>{editingUser ? 'New Password (leave blank to keep current)' : 'Password *'}</Label>
              <Input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder={editingUser ? '••••••••' : 'Minimum 6 characters'}
                data-testid="user-password-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Phone (Optional)</Label>
              <Input
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+91 98765 43210"
                data-testid="user-phone-input"
              />
            </div>

            {/* Phase 2 + Phase 17: Vyapaar team role flags */}
            <div className="space-y-2 border rounded-md p-3 bg-muted/30">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">Vyapaar Team Roles (optional)</Label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_vyapaar_ops}
                  onChange={(e) => setFormData({ ...formData, is_vyapaar_ops: e.target.checked })}
                  className="w-4 h-4"
                  data-testid="user-is-vyapaar-ops"
                />
                <span><strong>Vyapaar Operations</strong> — full app access except user/company/category creation</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_finance}
                  onChange={(e) => setFormData({ ...formData, is_finance: e.target.checked })}
                  className="w-4 h-4"
                  data-testid="user-is-finance"
                />
                <span><strong>Vyapaar Finance</strong> — raise invoices, record payments, see analytics</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_delivery}
                  onChange={(e) => setFormData({ ...formData, is_delivery: e.target.checked })}
                  className="w-4 h-4"
                  data-testid="user-is-delivery"
                />
                <span><strong>Delivery Lead</strong> — update milestone status, manage commercials</span>
              </label>
            </div>

            {needsCompany && (
              <>
                <div className="space-y-2">
                  <Label>Assign to Company {formData.role === 'sales_associate' ? '(Optional)' : ''}</Label>
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
                  <div className="space-y-2">
                    <Label>Or Create New Company</Label>
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
              </>
            )}
          </div>

          <DialogFooter>
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
