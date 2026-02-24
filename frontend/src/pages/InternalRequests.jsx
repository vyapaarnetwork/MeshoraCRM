import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
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
  Plus, 
  ShoppingCart, 
  FileText, 
  Loader2, 
  User, 
  Mail, 
  Phone, 
  Building2, 
  Tag,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertCircle,
  Eye
} from 'lucide-react';
import api, { formatDate, formatCurrency } from '../utils/api';
import { toast } from 'sonner';

const InternalRequests = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    customer_name: user?.name || '',
    customer_email: user?.email || '',
    customer_phone: '',
    customer_company: '',
    primary_category_id: '',
    secondary_category_id: '',
    estimated_deal_value: '',
    referral_notes: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    // Auto-fill user info when dialog opens
    if (dialogOpen && user) {
      setFormData(prev => ({
        ...prev,
        customer_name: user.name || '',
        customer_email: user.email || '',
        customer_company: user.company_name || ''
      }));
    }
  }, [dialogOpen, user]);

  const fetchData = async () => {
    try {
      const [requestsRes, categoriesRes] = await Promise.all([
        api.get('/leads/internal-requests'),
        api.get('/master/primary-categories')
      ]);
      setRequests(requestsRes.data);
      setCategories(categoriesRes.data.filter(c => c.is_active));
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchSecondaryCategories = async (primaryId) => {
    try {
      const response = await api.get(`/master/secondary-categories?primary_category_id=${primaryId}`);
      setSecondaryCategories(response.data.filter(c => c.is_active));
    } catch (error) {
      console.error('Failed to fetch secondary categories');
    }
  };

  const handlePrimaryCategoryChange = (value) => {
    setFormData({ ...formData, primary_category_id: value, secondary_category_id: '' });
    fetchSecondaryCategories(value);
  };

  const handleSubmit = async () => {
    if (!formData.title || !formData.customer_name || !formData.customer_email || !formData.primary_category_id) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/leads/referral', {
        ...formData,
        estimated_deal_value: formData.estimated_deal_value ? parseFloat(formData.estimated_deal_value) : null,
        is_internal_request: true
      });
      toast.success('Internal service request submitted successfully');
      setDialogOpen(false);
      setFormData({
        title: '',
        description: '',
        customer_name: user?.name || '',
        customer_email: user?.email || '',
        customer_phone: '',
        customer_company: user?.company_name || '',
        primary_category_id: '',
        secondary_category_id: '',
        estimated_deal_value: '',
        referral_notes: ''
      });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    if (!status) return <Badge variant="secondary">Unknown</Badge>;
    return (
      <Badge style={{ backgroundColor: `${status.status_color}20`, color: status.status_color, borderColor: status.status_color }} variant="outline">
        {status.status_name}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="internal-requests-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Internal Requests</h1>
          <p className="text-muted-foreground mt-1">
            Request services from other Vyapaar Network partners
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)} data-testid="new-request-btn">
          <Plus className="w-4 h-4 mr-2" />
          New Service Request
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <ShoppingCart className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Requests</p>
                <p className="text-2xl font-bold">{requests.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-amber-100 rounded-lg">
                <Clock className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold">
                  {requests.filter(r => r.status_name?.toLowerCase() === 'draft' || r.status_name?.toLowerCase() === 'new').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircle2 className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Completed</p>
                <p className="text-2xl font-bold">
                  {requests.filter(r => r.status_name?.toLowerCase() === 'won').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Requests Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShoppingCart className="w-5 h-5 text-primary" />
            My Service Requests
          </CardTitle>
          <CardDescription>
            Services you've requested from other partners in the network
          </CardDescription>
        </CardHeader>
        <CardContent>
          {requests.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Request</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Est. Value</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Assigned To</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((request) => (
                  <TableRow key={request.id} data-testid={`request-row-${request.id}`}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{request.title}</p>
                        {request.description && (
                          <p className="text-sm text-muted-foreground line-clamp-1">{request.description}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm">{request.primary_category_name}</span>
                        {request.secondary_category_name && (
                          <span className="text-xs text-muted-foreground">{request.secondary_category_name}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {request.deal_value > 0 ? formatCurrency(request.deal_value) : '-'}
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(request)}
                    </TableCell>
                    <TableCell>
                      {request.selling_partner_name || (
                        <span className="text-muted-foreground text-sm">Not assigned</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{formatDate(request.created_at)}</span>
                    </TableCell>
                    <TableCell>
                      <Button 
                        size="icon" 
                        variant="ghost"
                        onClick={() => navigate(`/leads/${request.id}`)}
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <ShoppingCart className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="font-semibold mb-1">No service requests yet</h3>
              <p className="text-muted-foreground text-sm mb-4">
                Request services from other partners in the Vyapaar Network
              </p>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create First Request
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* New Request Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" />
              New Internal Service Request
            </DialogTitle>
            <DialogDescription>
              Request a service from another partner in the Vyapaar Network. Your details will be pre-filled as the customer.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label>Service Title *</Label>
              <Input
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Website Development, Digital Marketing Campaign"
                data-testid="request-title-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe the service you need..."
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Category *</Label>
                <Select value={formData.primary_category_id} onValueChange={handlePrimaryCategoryChange}>
                  <SelectTrigger data-testid="category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Sub-category</Label>
                <Select 
                  value={formData.secondary_category_id} 
                  onValueChange={(v) => setFormData({ ...formData, secondary_category_id: v })}
                  disabled={!formData.primary_category_id}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select sub-category" />
                  </SelectTrigger>
                  <SelectContent>
                    {secondaryCategories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Estimated Budget</Label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="number"
                  value={formData.estimated_deal_value}
                  onChange={(e) => setFormData({ ...formData, estimated_deal_value: e.target.value })}
                  placeholder="0.00"
                  className="pl-10"
                />
              </div>
            </div>

            <div className="border-t pt-4 mt-2">
              <p className="text-sm font-medium mb-3 flex items-center gap-2">
                <User className="w-4 h-4" />
                Your Details (as customer)
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Your Name *</Label>
                  <Input
                    value={formData.customer_name}
                    onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Your Email *</Label>
                  <Input
                    type="email"
                    value={formData.customer_email}
                    onChange={(e) => setFormData({ ...formData, customer_email: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Your Phone</Label>
                  <Input
                    value={formData.customer_phone}
                    onChange={(e) => setFormData({ ...formData, customer_phone: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Your Company</Label>
                  <Input
                    value={formData.customer_company}
                    onChange={(e) => setFormData({ ...formData, customer_company: e.target.value })}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Additional Notes</Label>
              <Textarea
                value={formData.referral_notes}
                onChange={(e) => setFormData({ ...formData, referral_notes: e.target.value })}
                placeholder="Any additional requirements or preferences..."
                rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="submit-request-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <ShoppingCart className="w-4 h-4 mr-2" />
                  Submit Request
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default InternalRequests;
