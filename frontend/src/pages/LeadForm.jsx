import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { ArrowLeft, Loader2, Save, AlertCircle } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import SearchableUserSelect from '../components/SearchableUserSelect';

const LeadForm = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin, isSellingPartner, isCustomer } = useAuth();
  const isEditing = !!id;

  const [loading, setLoading] = useState(isEditing);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    customer_company: '',
    selling_partner_id: '',
    sales_associate_id: '',
    primary_category_id: '',
    secondary_category_id: '',
    deal_value: '',
    commission_override: '',
    sales_associate_commission: '',
    status_id: ''
  });

  const [options, setOptions] = useState({
    statuses: [],
    primaryCategories: [],
    secondaryCategories: [],
    sellingPartners: [],
    salesAssociates: []
  });
  const [loadingPartners, setLoadingPartners] = useState(false);

  useEffect(() => {
    fetchOptions();
    if (isEditing) {
      fetchLead();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Refetch selling partners filtered by selected sub-category
  useEffect(() => {
    const fetchPartnersForSubcategory = async () => {
      if (!formData.secondary_category_id) {
        setOptions(prev => ({ ...prev, sellingPartners: [] }));
        return;
      }
      setLoadingPartners(true);
      try {
        const res = await api.get('/users/selling-partners', {
          params: { subcategory_id: formData.secondary_category_id }
        });
        let partners = res.data;
        // In edit mode, if the current partner isn't in the filtered list
        // (e.g., the company is no longer mapped to this sub-category),
        // fetch and append them so the dropdown still shows the selected value.
        if (formData.selling_partner_id && !partners.some(p => p.id === formData.selling_partner_id)) {
          try {
            const userRes = await api.get(`/users/${formData.selling_partner_id}`);
            partners = [...partners, { ...userRes.data, _unmapped: true }];
          } catch (err) {
            // Partner user not accessible or deleted - keep dropdown without it.
            console.warn('Could not fetch unmapped partner', formData.selling_partner_id, err);
          }
        }
        setOptions(prev => ({ ...prev, sellingPartners: partners }));
      } catch (e) {
        setOptions(prev => ({ ...prev, sellingPartners: [] }));
      } finally {
        setLoadingPartners(false);
      }
    };
    fetchPartnersForSubcategory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData.secondary_category_id]);

  const fetchOptions = async () => {
    try {
      const [statusesRes, primaryRes, secondaryRes, associatesRes] = await Promise.all([
        api.get('/master/lead-status'),
        api.get('/master/primary-categories'),
        api.get('/master/secondary-categories'),
        api.get('/users/referrers').catch(() => ({ data: [] }))
      ]);

      setOptions(prev => ({
        ...prev,
        statuses: statusesRes.data,
        primaryCategories: primaryRes.data,
        secondaryCategories: secondaryRes.data,
        salesAssociates: associatesRes.data
      }));
    } catch (error) {
      console.error('Failed to fetch options:', error);
    }
  };

  const fetchLead = async () => {
    try {
      const response = await api.get(`/leads/${id}`);
      const lead = response.data;
      setFormData({
        title: lead.title || '',
        description: lead.description || '',
        customer_name: lead.customer_name || '',
        customer_email: lead.customer_email || '',
        customer_phone: lead.customer_phone || '',
        customer_company: lead.customer_company || '',
        selling_partner_id: lead.selling_partner_id || '',
        sales_associate_id: lead.sales_associate_id || '',
        primary_category_id: lead.primary_category_id || '',
        secondary_category_id: lead.secondary_category_id || '',
        deal_value: lead.deal_value?.toString() || '',
        commission_override: lead.commission_override?.toString() || '',
        sales_associate_commission: lead.sales_associate_commission?.toString() || '',
        status_id: lead.status_id || ''
      });
    } catch (error) {
      toast.error('Failed to load lead');
      navigate('/leads');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSelectChange = (name, value) => {
    setFormData(prev => {
      const next = { ...prev, [name]: value };
      // Cascade: clear sub-category & selling partner when primary changes
      if (name === 'primary_category_id') {
        next.secondary_category_id = '';
        next.selling_partner_id = '';
      }
      // Cascade: clear selling partner when sub-category changes
      if (name === 'secondary_category_id') {
        next.selling_partner_id = '';
      }
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const payload = {
        ...formData,
        deal_value: parseFloat(formData.deal_value) || 0,
        commission_override: formData.commission_override ? parseFloat(formData.commission_override) : null,
        sales_associate_commission: formData.sales_associate_commission ? parseFloat(formData.sales_associate_commission) : null,
        selling_partner_id: formData.selling_partner_id || null,
        sales_associate_id: formData.sales_associate_id || null,
        secondary_category_id: formData.secondary_category_id || null
      };

      // If user is selling partner, auto-assign themselves
      if (isSellingPartner && !payload.selling_partner_id) {
        payload.selling_partner_id = user.id;
      }

      if (isEditing) {
        await api.put(`/leads/${id}`, payload);
        toast.success('Lead updated successfully');
      } else {
        await api.post('/leads', payload);
        toast.success('Lead created successfully');
      }

      navigate('/leads');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save lead');
    } finally {
      setSubmitting(false);
    }
  };

  // Filter secondary categories based on selected primary
  const filteredSecondaryCategories = options.secondaryCategories.filter(
    cat => cat.primary_category_id === formData.primary_category_id
  );

  if (loading) {
    return <LeadFormSkeleton />;
  }

  return (
    <div className="space-y-6" data-testid="lead-form-page">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button 
          variant="ghost" 
          onClick={() => navigate('/leads')}
          data-testid="back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isEditing ? 'Edit Lead' : 'Create New Lead'}
          </h1>
          <p className="text-muted-foreground">
            {isEditing ? 'Update lead information' : 'Fill in the details to create a new lead'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Lead title and description</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Lead Title *</Label>
                <Input
                  id="title"
                  name="title"
                  value={formData.title}
                  onChange={handleChange}
                  placeholder="e.g., Website Development Project"
                  required
                  data-testid="lead-title-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  placeholder="Describe the lead..."
                  rows={4}
                  data-testid="lead-description-input"
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="primary_category_id">Category *</Label>
                  <Select 
                    value={formData.primary_category_id} 
                    onValueChange={(v) => handleSelectChange('primary_category_id', v)}
                    required
                  >
                    <SelectTrigger data-testid="primary-category-select">
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {options.primaryCategories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>
                          {cat.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="secondary_category_id">Sub-category</Label>
                  <Select 
                    value={formData.secondary_category_id} 
                    onValueChange={(v) => handleSelectChange('secondary_category_id', v)}
                    disabled={!formData.primary_category_id}
                  >
                    <SelectTrigger data-testid="secondary-category-select">
                      <SelectValue placeholder="Select sub-category" />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredSecondaryCategories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>
                          {cat.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="status_id">Status</Label>
                <Select 
                  value={formData.status_id} 
                  onValueChange={(v) => handleSelectChange('status_id', v)}
                >
                  <SelectTrigger data-testid="status-select">
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.statuses.map((status) => (
                      <SelectItem key={status.id} value={status.id}>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-2 h-2 rounded-full" 
                            style={{ backgroundColor: status.color }}
                          />
                          {status.name}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Customer Information */}
          <Card>
            <CardHeader>
              <CardTitle>Customer Information</CardTitle>
              <CardDescription>Details about the customer</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="customer_name">Customer Name *</Label>
                <Input
                  id="customer_name"
                  name="customer_name"
                  value={formData.customer_name}
                  onChange={handleChange}
                  placeholder="John Doe"
                  required
                  data-testid="customer-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="customer_email">Customer Email *</Label>
                <Input
                  id="customer_email"
                  name="customer_email"
                  type="email"
                  value={formData.customer_email}
                  onChange={handleChange}
                  placeholder="john@company.com"
                  required
                  data-testid="customer-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="customer_phone">Customer Phone</Label>
                <Input
                  id="customer_phone"
                  name="customer_phone"
                  value={formData.customer_phone}
                  onChange={handleChange}
                  placeholder="+91 98765 43210"
                  data-testid="customer-phone-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="customer_company">Customer Company</Label>
                <Input
                  id="customer_company"
                  name="customer_company"
                  value={formData.customer_company}
                  onChange={handleChange}
                  placeholder="Company Name"
                  data-testid="customer-company-input"
                />
              </div>
            </CardContent>
          </Card>

          {/* Deal & Assignment */}
          <Card>
            <CardHeader>
              <CardTitle>Deal Information</CardTitle>
              <CardDescription>Value and assignment details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="deal_value">Deal Value (₹)</Label>
                <Input
                  id="deal_value"
                  name="deal_value"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.deal_value}
                  onChange={handleChange}
                  placeholder="0"
                  data-testid="deal-value-input"
                />
              </div>
              {isAdmin && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="selling_partner_id">Selling Partner</Label>
                    <SearchableUserSelect
                      value={formData.selling_partner_id}
                      onChange={(v) => handleSelectChange('selling_partner_id', v)}
                      users={options.sellingPartners}
                      disabled={!formData.secondary_category_id || loadingPartners}
                      placeholder={
                        !formData.secondary_category_id
                          ? 'Select sub-category first'
                          : loadingPartners
                            ? 'Loading partners...'
                            : options.sellingPartners.length === 0
                              ? 'No partners for this sub-category'
                              : 'Search and select partner...'
                      }
                      emptyText="No matching partners."
                      testId="selling-partner-select"
                      secondaryRender={(p) => {
                        const parts = [];
                        if (p.company_name) parts.push(p.company_name);
                        if (p._unmapped) parts.push('not mapped to this sub-category');
                        return parts.join(' · ');
                      }}
                    />
                    {formData.secondary_category_id && !loadingPartners && options.sellingPartners.length === 0 && (
                      <p className="text-xs text-muted-foreground" data-testid="no-partners-msg">
                        No active selling partners for this sub-category. Either no companies are mapped to it,
                        or the mapped companies have no active selling-partner users yet. Visit{' '}
                        <a href="/partner-mappings" className="text-primary underline">Partner Mappings</a> to map
                        a company, then click "Add User" if that company has no users.
                      </p>
                    )}
                    {!isEditing && !formData.selling_partner_id && (
                      <Alert className="border-amber-200 bg-amber-50 text-amber-800">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription className="text-xs">
                          Without a selling partner, this lead will be saved as <strong>Draft</strong>.
                          It will move to "New" status when a partner is assigned.
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="sales_associate_id">Referred By (Sales Associate / Selling Partner)</Label>
                    <SearchableUserSelect
                      value={formData.sales_associate_id}
                      onChange={(v) => handleSelectChange('sales_associate_id', v)}
                      users={options.salesAssociates}
                      placeholder="Search and select referrer..."
                      emptyText="No matching referrers."
                      testId="sales-associate-select"
                    />
                    <p className="text-xs text-muted-foreground">
                      A lead can be referred by either a Sales Associate or a Selling Partner.
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Commission Settings (Admin Only) */}
          {isAdmin && (
            <Card>
              <CardHeader>
                <CardTitle>Commission Settings</CardTitle>
                <CardDescription>Override default commission rates</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="commission_override">
                    Vyapaar Commission Override (%)
                  </Label>
                  <Input
                    id="commission_override"
                    name="commission_override"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={formData.commission_override}
                    onChange={handleChange}
                    placeholder="Default: 15%"
                    data-testid="commission-override-input"
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave empty to use partner's default rate
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sales_associate_commission">
                    Referrer Commission (% of Vyapaar share)
                  </Label>
                  <Input
                    id="sales_associate_commission"
                    name="sales_associate_commission"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={formData.sales_associate_commission}
                    onChange={handleChange}
                    placeholder="e.g., 10"
                    data-testid="sa-commission-input"
                  />
                  <p className="text-xs text-muted-foreground">
                    Percentage of Vyapaar's share paid to the referrer (Sales Associate or Selling Partner)
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Submit Button */}
        <div className="flex justify-end gap-4">
          <Button 
            type="button" 
            variant="outline" 
            onClick={() => navigate('/leads')}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            disabled={submitting}
            data-testid="submit-lead-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {isEditing ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                {isEditing ? 'Update Lead' : 'Create Lead'}
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
};

// Loading Skeleton
const LeadFormSkeleton = () => (
  <div className="space-y-6">
    <div className="flex items-center gap-4">
      <Skeleton className="h-10 w-24" />
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-64" />
      </div>
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-6 w-32 mb-2" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            {[1, 2, 3].map((j) => (
              <div key={j} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

export default LeadForm;
