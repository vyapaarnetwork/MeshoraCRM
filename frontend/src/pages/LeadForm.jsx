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
import { ArrowLeft, Loader2, Save, AlertCircle, Search, Building2, X, Check, Plus } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import SearchableUserSelect from '../components/SearchableUserSelect';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '../components/ui/command';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';

const LeadForm = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin, isSellingPartner, isCustomer } = useAuth();
  const isEditing = !!id;

  const [loading, setLoading] = useState(isEditing);
  const [submitting, setSubmitting] = useState(false);
  const todayIso = new Date().toISOString().slice(0, 10);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    customer_company: '',
    customer_company_id: '',     // Phase 40.2 — link to Companies master
    selling_partner_id: '',
    selling_partner_company_id: '',
    lead_owner_id: '',
    vyapaar_lead_owner_id: '',
    sales_associate_id: '',
    primary_category_id: '',
    secondary_category_id: '',
    deal_value: '',
    commission_override: '',
    sales_associate_commission: '',
    vyapaar_commission_template_id: '',   // Phase 36.3
    referral_commission_id: '',           // Phase 36.3
    status_id: '',
    start_date: todayIso,
    closure_date: ''
  });

  const [options, setOptions] = useState({
    statuses: [],
    primaryCategories: [],
    secondaryCategories: [],
    sellingPartners: [],
    salesAssociates: [],
    sellingPartnerCompanies: [],
    companyUsers: [],
    vyapaarTeam: [],
    commissionTemplates: [],    // Phase 36.3 — Vyapaar Commission templates master
    referralCommissions: [],    // Phase 36.3 — Referral Commission levels master
    allCompanies: [],           // Phase 40.2 — Companies master (Customer + Selling Partner) for lead-customer picker
  });
  const [loadingPartners, setLoadingPartners] = useState(false);
  const [loadingCompanyUsers, setLoadingCompanyUsers] = useState(false);

  useEffect(() => {
    fetchOptions();
    if (isEditing) {
      fetchLead();
    }
     
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
     
  }, [formData.secondary_category_id]);

  const fetchOptions = async () => {
    try {
      const [statusesRes, primaryRes, secondaryRes, associatesRes, companiesRes, vyapaarRes, templatesRes, referralsRes, allCompaniesRes] = await Promise.all([
        api.get('/master/lead-status'),
        api.get('/master/primary-categories'),
        api.get('/master/secondary-categories'),
        api.get('/users/referrers').catch(() => ({ data: [] })),
        api.get('/companies/selling-partners').catch(() => ({ data: [] })),
        api.get('/users/vyapaar-team').catch(() => ({ data: [] })),
        api.get('/master/commission-templates').catch(() => ({ data: [] })),
        api.get('/referral-commissions').catch(() => ({ data: [] })),
        // Phase 40.2 — load all companies (Customer + Selling Partner types) so the
        // customer picker can attach a lead to any existing company in the master.
        api.get('/companies').catch(() => ({ data: [] })),
      ]);

      setOptions(prev => ({
        ...prev,
        statuses: statusesRes.data,
        primaryCategories: primaryRes.data,
        secondaryCategories: secondaryRes.data,
        salesAssociates: associatesRes.data,
        sellingPartnerCompanies: companiesRes.data,
        vyapaarTeam: vyapaarRes.data,
        commissionTemplates: templatesRes.data || [],
        referralCommissions: referralsRes.data || [],
        allCompanies: allCompaniesRes.data || [],
      }));

      // Phase 36.3 — Auto-default Status to the first available lead-status when creating
      // a new lead so the form never silently fails on missing status_id.
      if (!isEditing) {
        setFormData(prev => {
          if (prev.status_id) return prev;
          const firstStatus = (statusesRes.data || [])[0];
          return firstStatus ? { ...prev, status_id: firstStatus.id } : prev;
        });
      }
    } catch (error) {
      console.error('Failed to fetch options:', error);
    }
  };

  // Phase 34.7 — Refetch users when SP company changes
  useEffect(() => {
    const loadUsers = async () => {
      if (!formData.selling_partner_company_id) {
        setOptions(prev => ({ ...prev, companyUsers: [] }));
        return;
      }
      setLoadingCompanyUsers(true);
      try {
        const res = await api.get(`/users/by-company/${formData.selling_partner_company_id}`);
        setOptions(prev => ({ ...prev, companyUsers: res.data }));
      } catch (e) {
        setOptions(prev => ({ ...prev, companyUsers: [] }));
      } finally {
        setLoadingCompanyUsers(false);
      }
    };
    loadUsers();
  }, [formData.selling_partner_company_id]);

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
        customer_company_id: lead.customer_company_id || '',  // Phase 40.2
        selling_partner_id: lead.selling_partner_id || '',
        selling_partner_company_id: lead.selling_partner_company_id || '',
        lead_owner_id: lead.lead_owner_id || lead.selling_partner_id || '',
        vyapaar_lead_owner_id: lead.vyapaar_lead_owner_id || '',
        sales_associate_id: lead.sales_associate_id || '',
        primary_category_id: lead.primary_category_id || '',
        secondary_category_id: lead.secondary_category_id || '',
        deal_value: lead.deal_value?.toString() || '',
        commission_override: lead.commission_override?.toString() || '',
        sales_associate_commission: lead.sales_associate_commission?.toString() || '',
        vyapaar_commission_template_id: lead.vyapaar_commission_template_id || '',
        referral_commission_id: lead.referral_commission_id || '',
        status_id: lead.status_id || '',
        start_date: lead.start_date || (lead.created_at ? lead.created_at.slice(0, 10) : todayIso),
        closure_date: lead.closure_date || ''
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
        vyapaar_commission_template_id: formData.vyapaar_commission_template_id || null,
        referral_commission_id: formData.referral_commission_id || null,
        selling_partner_id: formData.lead_owner_id || formData.selling_partner_id || null,
        selling_partner_company_id: formData.selling_partner_company_id || null,
        lead_owner_id: formData.lead_owner_id || null,
        vyapaar_lead_owner_id: formData.vyapaar_lead_owner_id || null,
        sales_associate_id: formData.sales_associate_id || null,
        secondary_category_id: formData.secondary_category_id || null,
        start_date: formData.start_date || todayIso,
        closure_date: formData.closure_date || null
      };

      // If user is selling partner, auto-assign themselves as Lead Owner
      if (isSellingPartner && !payload.lead_owner_id) {
        payload.lead_owner_id = user.id;
        payload.selling_partner_id = user.id;
        if (!payload.selling_partner_company_id) {
          payload.selling_partner_company_id = user.company_id;
        }
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
      // Phase 36.3 — surface validation errors clearly (422 returns array of {loc, msg})
      const detail = error.response?.data?.detail;
      let message = 'Failed to save lead';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        message = detail.map((d) => {
          const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : '';
          return field ? `${field}: ${d.msg}` : d.msg;
        }).join(' • ');
      }
      toast.error(message);
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

              {/* Phase 34.6 — Lead start & closure dates */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="start_date">Lead Start Date</Label>
                  <Input
                    type="date"
                    id="start_date"
                    name="start_date"
                    value={formData.start_date || ''}
                    onChange={handleChange}
                    data-testid="lead-start-date"
                  />
                  <p className="text-xs text-muted-foreground">Defaults to today; edit if the deal started earlier.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="closure_date">Lead Closure Date</Label>
                  <Input
                    type="date"
                    id="closure_date"
                    name="closure_date"
                    value={formData.closure_date || ''}
                    onChange={handleChange}
                    data-testid="lead-closure-date"
                  />
                  <p className="text-xs text-muted-foreground">Auto-stamps when status flips to Won / Lost / Dead / Disqualified. Override here if needed.</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Customer Information */}
          <Card>
            <CardHeader>
              <CardTitle>Customer Information</CardTitle>
              <CardDescription>
                Pick an existing company from the master, or {(isAdmin) ? 'enter a new customer below' : 'ask Vyapaar to add the new customer first'}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Phase 40.2 — Customer picker from Companies master */}
              <CustomerPicker
                companies={options.allCompanies}
                selectedId={formData.customer_company_id}
                canCreate={isAdmin}
                onCreated={(c) => {
                  setOptions((prev) => ({ ...prev, allCompanies: [...prev.allCompanies, c] }));
                }}
                onSelect={(c) => {
                  if (c) {
                    setFormData(prev => ({
                      ...prev,
                      customer_company_id: c.id,
                      customer_company: c.name || '',
                      customer_email: c.contact_email || prev.customer_email,
                      customer_phone: c.contact_phone || prev.customer_phone,
                      // Keep Customer Name editable (Companies master holds contact, not contact-person name)
                      customer_name: prev.customer_name || c.name || '',
                    }));
                  } else {
                    // Unlink
                    setFormData(prev => ({ ...prev, customer_company_id: '' }));
                  }
                }}
              />

              {/* Linked badge OR manual-entry banner */}
              {formData.customer_company_id && (
                <Alert className="border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30">
                  <AlertDescription className="flex items-center justify-between gap-2 text-xs">
                    <span>
                      <strong>Linked</strong> to{' '}
                      {options.allCompanies.find(c => c.id === formData.customer_company_id)?.name || 'a company in the master'}.
                      Edit contact details in Companies → master to keep this lead in sync.
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setFormData(prev => ({ ...prev, customer_company_id: '' }))}
                      className="h-6 text-xs"
                      data-testid="customer-unlink-btn"
                    >
                      Unlink
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              {!formData.customer_company_id && !isAdmin && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    No company selected. Only Vyapaar team can add a new customer to the master — please pick one above, or contact your Vyapaar Network admin to add this customer.
                  </AlertDescription>
                </Alert>
              )}

              {/* Manual entry fields — read-only when linked OR when non-admin without selection */}
              <div className="space-y-2">
                <Label htmlFor="customer_name">Customer Contact Name *</Label>
                <Input
                  id="customer_name"
                  name="customer_name"
                  value={formData.customer_name}
                  onChange={handleChange}
                  placeholder="John Doe"
                  required
                  readOnly={!isAdmin && !formData.customer_company_id ? false : false}
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
                  disabled={!isAdmin && !formData.customer_company_id}
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
                  disabled={!isAdmin && !formData.customer_company_id}
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
                  disabled={!isAdmin && !formData.customer_company_id}
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
                  {/* Phase 34.7 — split SP into Company → Lead Owner + add Vyapaar Lead Owner */}
                  <div className="space-y-2">
                    <Label htmlFor="selling_partner_company_id">Selling Partner Company</Label>
                    <SearchableUserSelect
                      value={formData.selling_partner_company_id}
                      onChange={(v) => {
                        setFormData(prev => ({
                          ...prev,
                          selling_partner_company_id: v,
                          lead_owner_id: '',  // reset owner when company changes
                          selling_partner_id: '',
                        }));
                      }}
                      users={options.sellingPartnerCompanies}
                      placeholder="Search and select selling partner company..."
                      emptyText="No selling partner companies."
                      testId="sp-company-select"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lead_owner_id">Lead Owner (Selling Partner User)</Label>
                    <SearchableUserSelect
                      value={formData.lead_owner_id}
                      onChange={(v) => {
                        setFormData(prev => ({
                          ...prev,
                          lead_owner_id: v,
                          selling_partner_id: v,  // keep legacy in sync
                        }));
                      }}
                      users={options.companyUsers}
                      disabled={!formData.selling_partner_company_id || loadingCompanyUsers}
                      placeholder={
                        !formData.selling_partner_company_id
                          ? 'Select company first'
                          : loadingCompanyUsers
                            ? 'Loading users...'
                            : options.companyUsers.length === 0
                              ? 'No users in this company'
                              : 'Search and select a Lead Owner...'
                      }
                      emptyText="No matching users."
                      testId="lead-owner-select"
                      secondaryRender={(u) => u.company_role || ''}
                    />
                    <p className="text-xs text-muted-foreground">
                      Any active user from <strong>{options.sellingPartnerCompanies.find(c => c.id === formData.selling_partner_company_id)?.name || 'this company'}</strong> will be able to see this lead.
                    </p>
                    {!isEditing && !formData.lead_owner_id && (
                      <Alert className="border-amber-200 bg-amber-50 text-amber-800">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription className="text-xs">
                          Without a Lead Owner, this lead will be saved as <strong>Draft</strong>.
                          It will move to "New" status when an owner is assigned.
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vyapaar_lead_owner_id">Vyapaar Lead Owner</Label>
                    <SearchableUserSelect
                      value={formData.vyapaar_lead_owner_id}
                      onChange={(v) => handleSelectChange('vyapaar_lead_owner_id', v)}
                      users={options.vyapaarTeam}
                      placeholder="Search and select Vyapaar Lead Owner..."
                      emptyText="No matching Vyapaar users."
                      testId="vyapaar-lead-owner-select"
                      secondaryRender={(u) => (u.role || '').replace('_', ' ')}
                    />
                    <p className="text-xs text-muted-foreground">
                      The Vyapaar Network user responsible for shepherding this lead internally.
                    </p>
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

          {/* Commission Settings (Admin Only) — Phase 36.3 redesigned */}
          {isAdmin && (
            <Card data-testid="commission-settings-card">
              <CardHeader>
                <CardTitle>Commission Settings</CardTitle>
                <CardDescription>Pick a Vyapaar Commission template and a Referral Commission level. Both are managed under Manage → Commissions.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Vyapaar Commission template */}
                <div className="space-y-2">
                  <Label htmlFor="vyapaar_commission_template_id">Vyapaar Commission</Label>
                  <Select
                    value={formData.vyapaar_commission_template_id || ''}
                    onValueChange={(v) => handleSelectChange('vyapaar_commission_template_id', v)}
                  >
                    <SelectTrigger id="vyapaar_commission_template_id" data-testid="vyapaar-commission-template-select">
                      <SelectValue placeholder="Use partner default" />
                    </SelectTrigger>
                    <SelectContent>
                      {(options.commissionTemplates || []).map((tpl) => (
                        <SelectItem key={tpl.id} value={tpl.id}>
                          {tpl.name} ({tpl.vyapaar_percentage}%)
                          {tpl.is_default ? ' — default' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    The cut Vyapaar takes from the deal. Leave blank to use the partner's default.
                  </p>
                </div>

                {/* Referral level */}
                <div className="space-y-2">
                  <Label htmlFor="referral_commission_id">Referral Commission Level</Label>
                  <Select
                    value={formData.referral_commission_id || ''}
                    onValueChange={(v) => handleSelectChange('referral_commission_id', v)}
                  >
                    <SelectTrigger id="referral_commission_id" data-testid="referral-commission-select">
                      <SelectValue placeholder="Pick a level…" />
                    </SelectTrigger>
                    <SelectContent>
                      {(options.referralCommissions || []).map((rc) => (
                        <SelectItem key={rc.id} value={rc.id}>
                          {rc.name} — {rc.percent}%
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {formData.referral_commission_id && (
                    <p className="text-xs text-muted-foreground">
                      {(options.referralCommissions || []).find((rc) => rc.id === formData.referral_commission_id)?.meaning || ''}
                    </p>
                  )}
                </div>

                {/* Calculated breakup */}
                <CommissionBreakdownPreview
                  dealValue={parseFloat(formData.deal_value) || 0}
                  vyapaarPct={(() => {
                    const tpl = (options.commissionTemplates || []).find((t) => t.id === formData.vyapaar_commission_template_id);
                    if (tpl) return parseFloat(tpl.vyapaar_percentage);
                    if (formData.commission_override) return parseFloat(formData.commission_override);
                    return 15; // default fallback
                  })()}
                  referralPct={(() => {
                    // Phase 40.2 — only show referral payout when a level is EXPLICITLY picked.
                    // Without an explicit selection we no longer assume Lead Scout 10% in the UI.
                    if (!formData.referral_commission_id) return 0;
                    const rc = (options.referralCommissions || []).find((r) => r.id === formData.referral_commission_id);
                    return rc ? parseFloat(rc.percent) : 0;
                  })()}
                  referralLevelName={(options.referralCommissions || []).find((r) => r.id === formData.referral_commission_id)?.name}
                />
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

// ---------------------------------------------------------------------------
// Phase 36.3 — Live commission breakdown preview (rendered inside the form)
// ---------------------------------------------------------------------------
const CommissionBreakdownPreview = ({ dealValue, vyapaarPct, referralPct, referralLevelName }) => {
  if (!dealValue || dealValue <= 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground bg-muted/30">
        Enter a deal value to see the commission breakdown.
      </div>
    );
  }
  const fmt = (n) => `₹${(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  const vyapaarShare = (dealValue * vyapaarPct) / 100;
  const referralPayout = (vyapaarShare * referralPct) / 100;
  const netToVyapaar = vyapaarShare - referralPayout;
  const partnerKeeps = dealValue - vyapaarShare;
  return (
    <div className="rounded-lg border bg-gradient-to-br from-indigo-50/40 to-violet-50/30 dark:from-indigo-950/20 dark:to-violet-950/10 p-4 space-y-2.5" data-testid="commission-breakdown">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Deal value</span>
        <span className="font-semibold">{fmt(dealValue)}</span>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Selling partner keeps <span className="text-xs">({(100 - vyapaarPct).toFixed(1)}%)</span>
        </span>
        <span className="font-medium">{fmt(partnerKeeps)}</span>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-indigo-700 dark:text-indigo-300">
          Vyapaar commission <span className="text-xs">({vyapaarPct}%)</span>
        </span>
        <span className="font-semibold text-indigo-700 dark:text-indigo-300">{fmt(vyapaarShare)}</span>
      </div>
      {referralPct > 0 ? (
        <>
          <div className="border-l-2 border-indigo-300 dark:border-indigo-700 ml-4 pl-3 space-y-1.5 py-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                Referral payout {referralLevelName ? `(${referralLevelName} ${referralPct}%)` : `(${referralPct}%)`}
              </span>
              <span className="font-medium text-rose-600 dark:text-rose-300">– {fmt(referralPayout)}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Net to Vyapaar</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-300">{fmt(netToVyapaar)}</span>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground pt-1 border-t mt-2">
            Referral payout = {referralPct}% of Vyapaar&apos;s commission share, paid to the sales associate / selling partner that referred this lead.
          </p>
        </>
      ) : (
        <p className="text-[11px] text-muted-foreground pt-1 border-t mt-2">
          No referral commission applies. Pick a Referral Commission Level above if a sales associate / selling partner referred this lead.
        </p>
      )}
    </div>
  );
};



// ============================ Phase 40.2 — Customer Picker ============================
// Searchable popover that lets the user pick an existing company from the master
// (both Customer and Selling Partner types — selling partners can raise leads
// for their own internal requirements). On select the parent form auto-fills
// customer_company, contact email & phone from the picked company.
// Phase 40.4 — Grouped by type with heading + top-level filter chips so
// customers are impossible to miss among selling partners.
const CustomerPicker = ({ companies, selectedId, onSelect, canCreate, onCreated }) => {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('all'); // all | customer | selling_partner
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ name: '', contact_email: '', contact_phone: '', address: '' });
  const selected = companies.find((c) => c.id === selectedId);

  const handleCreate = async () => {
    if (!newCustomer.name.trim()) {
      toast.error('Company name is required');
      return;
    }
    setCreating(true);
    try {
      const res = await api.post('/companies', {
        name: newCustomer.name.trim(),
        type: 'customer',
        contact_email: newCustomer.contact_email.trim() || null,
        contact_phone: newCustomer.contact_phone.trim() || null,
        address: newCustomer.address.trim() || null,
      });
      const created = res.data;
      toast.success(`Added ${created.name} to Customer master`);
      if (onCreated) onCreated(created);
      onSelect(created);
      setCreateOpen(false);
      setOpen(false);
      setNewCustomer({ name: '', contact_email: '', contact_phone: '', address: '' });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create customer');
    } finally {
      setCreating(false);
    }
  };

  const customers = companies
    .filter((c) => c.type === 'customer')
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  const partners = companies
    .filter((c) => c.type === 'selling_partner')
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  const others = companies
    .filter((c) => c.type !== 'customer' && c.type !== 'selling_partner')
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

  const showCustomers = filter === 'all' || filter === 'customer';
  const showPartners = filter === 'all' || filter === 'selling_partner';

  const chip = (key, label, count) => (
    <button
      type="button"
      onClick={() => setFilter(key)}
      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
        filter === key
          ? 'bg-indigo-600 text-white border-indigo-600'
          : 'bg-transparent text-muted-foreground border-border hover:bg-muted'
      }`}
      data-testid={`customer-picker-filter-${key}`}
    >
      {label} <span className="opacity-75">({count})</span>
    </button>
  );

  const renderItem = (c) => (
    <CommandItem
      key={c.id}
      value={`${c.name} ${c.contact_email || ''} ${c.type || ''}`}
      onSelect={() => {
        onSelect(c);
        setOpen(false);
      }}
      data-testid={`customer-picker-option-${c.id}`}
    >
      <Check className={`mr-2 h-4 w-4 ${selectedId === c.id ? 'opacity-100' : 'opacity-0'}`} />
      <Building2 className={`mr-2 h-3.5 w-3.5 ${c.type === 'customer' ? 'text-emerald-600' : 'text-indigo-600'}`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate">{c.name}</div>
        <div className="text-[10px] text-muted-foreground truncate">{c.contact_email || 'no email on file'}</div>
      </div>
      <Badge
        variant="outline"
        className={`text-[10px] capitalize ml-2 ${
          c.type === 'customer'
            ? 'border-emerald-300 text-emerald-700 dark:text-emerald-300'
            : 'border-indigo-300 text-indigo-700 dark:text-indigo-300'
        }`}
      >
        {(c.type || '').replace(/_/g, ' ')}
      </Badge>
    </CommandItem>
  );

  return (
    <div className="space-y-1.5">
      <Label>Select existing customer or company</Label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between font-normal"
            data-testid="customer-picker-trigger"
          >
            <span className="flex items-center gap-2 truncate">
              <Building2 className={`w-4 h-4 shrink-0 ${selected?.type === 'customer' ? 'text-emerald-600' : 'text-muted-foreground'}`} />
              {selected ? (
                <>
                  <span className="truncate">{selected.name}</span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] capitalize ${
                      selected.type === 'customer'
                        ? 'border-emerald-300 text-emerald-700'
                        : 'border-indigo-300 text-indigo-700'
                    }`}
                  >
                    {(selected.type || '').replace(/_/g, ' ')}
                  </Badge>
                </>
              ) : (
                <span className="text-muted-foreground">
                  Search & pick — {customers.length} customer{customers.length === 1 ? '' : 's'} · {partners.length} selling partner{partners.length === 1 ? '' : 's'}
                </span>
              )}
            </span>
            <Search className="w-4 h-4 opacity-50 shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <div className="flex items-center gap-1.5 px-2 pt-2 pb-1 border-b flex-wrap">
            {chip('all', 'All', companies.length)}
            {chip('customer', 'Customers', customers.length)}
            {chip('selling_partner', 'Selling Partners', partners.length)}
            {canCreate && (
              <button
                type="button"
                onClick={() => { setOpen(false); setCreateOpen(true); }}
                className="ml-auto text-xs px-2.5 py-1 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white border border-emerald-600 inline-flex items-center gap-1"
                data-testid="customer-picker-new-btn"
              >
                <Plus className="w-3 h-3" /> New Customer
              </button>
            )}
          </div>
          <Command>
            <CommandInput placeholder="Type to search companies…" data-testid="customer-picker-search" />
            <CommandList>
              <CommandEmpty>No matching company. Ask Vyapaar to add it first.</CommandEmpty>
              {showCustomers && customers.length > 0 && (
                <CommandGroup heading={`Customers · ${customers.length}`}>
                  {customers.map(renderItem)}
                </CommandGroup>
              )}
              {showPartners && partners.length > 0 && (
                <CommandGroup heading={`Selling Partners · ${partners.length}`}>
                  {partners.map(renderItem)}
                </CommandGroup>
              )}
              {filter === 'all' && others.length > 0 && (
                <CommandGroup heading={`Other · ${others.length}`}>
                  {others.map(renderItem)}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {selected && (
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mt-0.5"
          data-testid="customer-picker-clear"
        >
          <X className="w-3 h-3" /> Clear selection
        </button>
      )}

      {/* Phase 40.4 — Quick-add Customer dialog (admins only) */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-md" data-testid="customer-picker-new-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-emerald-600" /> New Customer
            </DialogTitle>
            <DialogDescription>
              Quickly add a customer to the master without leaving this lead. It will be auto-selected on save.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="new-cust-name">Company Name *</Label>
              <Input
                id="new-cust-name"
                autoFocus
                value={newCustomer.name}
                onChange={(e) => setNewCustomer((p) => ({ ...p, name: e.target.value }))}
                placeholder="Acme Industries Pvt Ltd"
                data-testid="customer-picker-new-name"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="new-cust-email">Contact Email</Label>
                <Input
                  id="new-cust-email"
                  type="email"
                  value={newCustomer.contact_email}
                  onChange={(e) => setNewCustomer((p) => ({ ...p, contact_email: e.target.value }))}
                  placeholder="ops@acme.com"
                  data-testid="customer-picker-new-email"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new-cust-phone">Contact Phone</Label>
                <Input
                  id="new-cust-phone"
                  value={newCustomer.contact_phone}
                  onChange={(e) => setNewCustomer((p) => ({ ...p, contact_phone: e.target.value }))}
                  placeholder="+91 98…"
                  data-testid="customer-picker-new-phone"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-cust-address">Address</Label>
              <Textarea
                id="new-cust-address"
                rows={2}
                value={newCustomer.address}
                onChange={(e) => setNewCustomer((p) => ({ ...p, address: e.target.value }))}
                placeholder="Optional"
                data-testid="customer-picker-new-address"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating} data-testid="customer-picker-new-cancel">
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={creating || !newCustomer.name.trim()}
              className="bg-emerald-600 hover:bg-emerald-700"
              data-testid="customer-picker-new-save"
            >
              {creating ? (<><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Adding…</>) : (<><Plus className="w-4 h-4 mr-1" /> Add & Select</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
