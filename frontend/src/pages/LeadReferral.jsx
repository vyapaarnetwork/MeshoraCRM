import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
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
  Send, 
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
  AlertCircle
} from 'lucide-react';
import api, { formatDate, formatCurrency } from '../utils/api';
import { toast } from 'sonner';

const LeadReferral = () => {
  const { user } = useAuth();
  const [referrals, setReferrals] = useState([]);
  const [primaryCategories, setPrimaryCategories] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    customer_name: '',
    customer_email: '',
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

  const fetchData = async () => {
    try {
      const [referralsRes, primaryRes, secondaryRes] = await Promise.all([
        api.get('/leads/my-referrals'),
        api.get('/master/primary-categories'),
        api.get('/master/secondary-categories')
      ]);
      setReferrals(referralsRes.data);
      setPrimaryCategories(primaryRes.data);
      setSecondaryCategories(secondaryRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = () => {
    setFormData({
      title: '',
      description: '',
      customer_name: '',
      customer_email: '',
      customer_phone: '',
      customer_company: '',
      primary_category_id: '',
      secondary_category_id: '',
      estimated_deal_value: '',
      referral_notes: ''
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.title || !formData.customer_name || !formData.customer_email || !formData.primary_category_id) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        title: formData.title,
        description: formData.description || null,
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        customer_phone: formData.customer_phone || null,
        customer_company: formData.customer_company || null,
        primary_category_id: formData.primary_category_id,
        secondary_category_id: formData.secondary_category_id || null,
        estimated_deal_value: formData.estimated_deal_value ? parseFloat(formData.estimated_deal_value) : null,
        referral_notes: formData.referral_notes || null
      };

      await api.post('/leads/referral', payload);
      toast.success('Lead referral submitted successfully! It will be reviewed by the admin.');
      fetchData();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit referral');
    } finally {
      setSubmitting(false);
    }
  };

  // Filter secondary categories by selected primary
  const filteredSecondaryCategories = formData.primary_category_id
    ? secondaryCategories.filter(c => c.primary_category_id === formData.primary_category_id)
    : [];

  // Stats
  const stats = {
    total: referrals.length,
    draft: referrals.filter(r => r.status_name === 'Draft').length,
    assigned: referrals.filter(r => r.status_name !== 'Draft').length,
    won: referrals.filter(r => r.status_name === 'Won').length
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Draft':
        return <Clock className="w-4 h-4" />;
      case 'Won':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'Lost':
        return <AlertCircle className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  if (loading) return <LeadReferralSkeleton />;

  return (
    <div className="space-y-6" data-testid="lead-referral-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Lead Referrals</h1>
          <p className="text-muted-foreground mt-1">
            Refer leads to Vyapaar Network for assignment
          </p>
        </div>
        <Button onClick={openDialog} data-testid="new-referral-btn">
          <Plus className="w-4 h-4 mr-2" />
          New Referral
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Referrals</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
              <div className="p-3 rounded-lg bg-primary/10 text-primary">
                <Send className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Review</p>
                <p className="text-2xl font-bold text-amber-600">{stats.draft}</p>
              </div>
              <div className="p-3 rounded-lg bg-amber-100 text-amber-600">
                <Clock className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Assigned</p>
                <p className="text-2xl font-bold text-blue-600">{stats.assigned}</p>
              </div>
              <div className="p-3 rounded-lg bg-blue-100 text-blue-600">
                <User className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Won Deals</p>
                <p className="text-2xl font-bold text-green-600">{stats.won}</p>
              </div>
              <div className="p-3 rounded-lg bg-green-100 text-green-600">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Info Card */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">How Lead Referrals Work</p>
              <ul className="list-disc list-inside space-y-1 text-blue-700">
                <li>Submit a lead referral with basic customer and project details</li>
                <li>Your referral will be saved in <strong>Draft</strong> status</li>
                <li>Super Admin will review and assign it to the right Selling Partner</li>
                <li>Once assigned, the lead status changes to <strong>New</strong></li>
                <li>You can track the progress of your referrals here</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Referrals Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            My Referrals ({referrals.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {referrals.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Lead</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Est. Value</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead>Submitted</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {referrals.map((referral) => (
                    <TableRow key={referral.id} data-testid={`referral-row-${referral.id}`}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{referral.title}</p>
                          {referral.description && (
                            <p className="text-xs text-muted-foreground line-clamp-1">
                              {referral.description}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1 text-sm">
                            <User className="w-3 h-3 text-muted-foreground" />
                            {referral.customer_name}
                          </div>
                          <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Mail className="w-3 h-3" />
                            {referral.customer_email}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{referral.primary_category_name}</Badge>
                      </TableCell>
                      <TableCell>
                        {referral.deal_value > 0 ? (
                          <span className="font-medium">{formatCurrency(referral.deal_value)}</span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge 
                          style={{ backgroundColor: referral.status_color + '20', color: referral.status_color, borderColor: referral.status_color }}
                          className="flex items-center gap-1 w-fit"
                        >
                          {getStatusIcon(referral.status_name)}
                          {referral.status_name}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {referral.selling_partner_name ? (
                          <span className="text-sm">{referral.selling_partner_name}</span>
                        ) : (
                          <span className="text-muted-foreground text-sm">Pending Assignment</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(referral.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <Send className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="font-semibold mb-1">No referrals yet</h3>
              <p className="text-muted-foreground text-sm mb-4">
                Submit your first lead referral to get started
              </p>
              <Button onClick={openDialog}>
                <Plus className="w-4 h-4 mr-2" />
                New Referral
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* New Referral Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Submit Lead Referral</DialogTitle>
            <DialogDescription>
              Refer a potential lead for assignment to the right selling partner
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Lead Info */}
            <div className="space-y-2">
              <Label>Lead Title *</Label>
              <Input
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Website Development for ABC Corp"
                data-testid="referral-title-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of the requirement..."
                rows={2}
              />
            </div>

            {/* Customer Info */}
            <div className="border-t pt-4">
              <Label className="text-base font-semibold flex items-center gap-2 mb-3">
                <User className="w-4 h-4" />
                Customer Details
              </Label>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Customer Name *</Label>
                  <Input
                    value={formData.customer_name}
                    onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                    placeholder="John Doe"
                    data-testid="referral-customer-name"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Company</Label>
                  <Input
                    value={formData.customer_company}
                    onChange={(e) => setFormData({ ...formData, customer_company: e.target.value })}
                    placeholder="ABC Corporation"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-3">
                <div className="space-y-2">
                  <Label>Email *</Label>
                  <Input
                    type="email"
                    value={formData.customer_email}
                    onChange={(e) => setFormData({ ...formData, customer_email: e.target.value })}
                    placeholder="john@abc.com"
                    data-testid="referral-customer-email"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Phone</Label>
                  <Input
                    value={formData.customer_phone}
                    onChange={(e) => setFormData({ ...formData, customer_phone: e.target.value })}
                    placeholder="+91 98765 43210"
                  />
                </div>
              </div>
            </div>

            {/* Category & Value */}
            <div className="border-t pt-4">
              <Label className="text-base font-semibold flex items-center gap-2 mb-3">
                <Tag className="w-4 h-4" />
                Category & Value
              </Label>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Primary Category *</Label>
                  <Select 
                    value={formData.primary_category_id} 
                    onValueChange={(v) => setFormData({ ...formData, primary_category_id: v, secondary_category_id: '' })}
                  >
                    <SelectTrigger data-testid="referral-primary-category">
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {primaryCategories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
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
                      {filteredSecondaryCategories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2 mt-3">
                <Label>Estimated Deal Value (₹)</Label>
                <Input
                  type="number"
                  value={formData.estimated_deal_value}
                  onChange={(e) => setFormData({ ...formData, estimated_deal_value: e.target.value })}
                  placeholder="50000"
                />
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-2 border-t pt-4">
              <Label>Referral Notes</Label>
              <Textarea
                value={formData.referral_notes}
                onChange={(e) => setFormData({ ...formData, referral_notes: e.target.value })}
                placeholder="Any additional notes for the admin reviewing this referral..."
                rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="submit-referral-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Submit Referral
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const LeadReferralSkeleton = () => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <div>
        <Skeleton className="h-8 w-40 mb-2" />
        <Skeleton className="h-4 w-60" />
      </div>
      <Skeleton className="h-10 w-32" />
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
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default LeadReferral;
