import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import api, { formatCurrency, formatDate, formatDateTime } from '../utils/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { ArrowLeft, Plus, Trash2, Save, Briefcase, Repeat, FileText, Upload, Activity, Calendar, Receipt, Wallet, RefreshCw, Download, ChevronUp, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';

const MILESTONE_STATUS_STYLES = {
  pending: { label: 'Pending', cls: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
  in_progress: { label: 'In Progress', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200' },
  delivered: { label: 'Delivered', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200' },
  invoice_raised: { label: 'Invoice Raised', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200' },
  payment_received: { label: 'Payment Received', cls: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-200' },
  overdue: { label: 'Overdue', cls: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-200' },
};

const BILLING_STATUS_STYLES = {
  scheduled: { label: 'Scheduled', cls: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
  invoiced: { label: 'Invoiced', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200' },
  paid: { label: 'Paid', cls: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-200' },
  skipped: { label: 'Skipped', cls: 'bg-slate-100 text-slate-500' },
};

const INVOICE_STATUS_STYLES = {
  draft: { label: 'Draft', cls: 'bg-slate-100 text-slate-700' },
  raised: { label: 'Raised', cls: 'bg-amber-100 text-amber-700' },
  partial: { label: 'Partial', cls: 'bg-orange-100 text-orange-700' },
  paid: { label: 'Paid', cls: 'bg-green-100 text-green-700' },
  overdue: { label: 'Overdue', cls: 'bg-red-100 text-red-700' },
  cancelled: { label: 'Cancelled', cls: 'bg-slate-100 text-slate-500 line-through' },
};

const CURRENCY_PREFIX = { INR: '₹', USD: '$', EUR: '€', GBP: '£' };

const fmtMoney = (v, ccy = 'INR') => `${CURRENCY_PREFIX[ccy] || ''}${(Number(v) || 0).toLocaleString()}`;

const newMilestone = (idx) => ({
  id: `tmp_${Date.now()}_${idx}`,
  _new: true,
  name: '',
  description: '',
  delivery_date: '',
  invoice_due_date: '',
  amount: 0,
  percentage: 0,
  status: 'pending',
});

const CommercialDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [commercial, setCommercial] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState('overview');
  const [users, setUsers] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [payments, setPayments] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [activity, setActivity] = useState([]);
  const [milestones, setMilestones] = useState([]);
  const [invoiceDialog, setInvoiceDialog] = useState({ open: false, milestone_id: null, billing_schedule_id: null, suggestedAmount: 0 });
  const [paymentDialog, setPaymentDialog] = useState({ open: false, invoice: null });
  const [uploadDialog, setUploadDialog] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const res = await api.get(`/commercials/${id}`);
      setCommercial(res.data);
      setMilestones((res.data.milestones || []).map((m) => ({ ...m })));
    } catch (e) {
      toast.error('Failed to load commercial');
      navigate('/commercials');
      return;
    }
    const [invRes, payRes, docRes, actRes, usrRes] = await Promise.all([
      api.get(`/commercials/${id}/invoices`).catch(() => ({ data: [] })),
      api.get(`/commercials/${id}/payments`).catch(() => ({ data: [] })),
      api.get(`/commercials/${id}/documents`).catch(() => ({ data: [] })),
      api.get(`/commercials/${id}/activity`).catch(() => ({ data: [] })),
      api.get('/users').catch(() => ({ data: [] })),
    ]);
    setInvoices(invRes.data || []);
    setPayments(payRes.data || []);
    setDocuments(docRes.data || []);
    setActivity(actRes.data || []);
    setUsers(usrRes.data || []);
    setLoading(false);
  }, [id, navigate]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const updateField = (field, value) => {
    setCommercial((prev) => ({ ...prev, [field]: value }));
  };

  const saveOverview = async () => {
    setSaving(true);
    try {
      const payload = {};
      const fields = commercial.type === 'one_time'
        ? ['total_value', 'start_date', 'end_date', 'project_owner_id', 'delivery_spoc_id', 'billing_contact_id', 'notes', 'currency']
        : ['contract_value', 'billing_frequency', 'contract_start_date', 'contract_end_date', 'auto_renewal', 'renewal_type', 'renewal_notice_days', 'account_manager_id', 'contract_owner_id', 'billing_contact_id', 'notes', 'currency', 'contract_status'];
      fields.forEach((f) => {
        if (commercial[f] !== undefined && commercial[f] !== null && commercial[f] !== '') payload[f] = commercial[f];
        else if (commercial[f] === '') payload[f] = null;
      });
      // Numeric coercion
      if (payload.total_value !== undefined) payload.total_value = Number(payload.total_value);
      if (payload.contract_value !== undefined) payload.contract_value = Number(payload.contract_value);
      if (payload.renewal_notice_days !== undefined) payload.renewal_notice_days = Number(payload.renewal_notice_days);
      const res = await api.patch(`/commercials/${id}`, payload);
      setCommercial(res.data);
      toast.success('Saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  // Milestone helpers
  const addMilestone = () => setMilestones((prev) => [...prev, newMilestone(prev.length)]);

  const removeMilestone = (idx) => setMilestones((prev) => prev.filter((_, i) => i !== idx));

  const moveMilestone = (idx, dir) => {
    setMilestones((prev) => {
      const next = [...prev];
      const t = idx + dir;
      if (t < 0 || t >= next.length) return prev;
      [next[idx], next[t]] = [next[t], next[idx]];
      return next;
    });
  };

  const updateMilestone = (idx, field, value) => {
    setMilestones((prev) => {
      const next = [...prev];
      const m = { ...next[idx] };
      m[field] = value;
      if (field === 'amount') {
        const total = Number(commercial?.total_value) || 0;
        if (total > 0) m.percentage = Number(((Number(value) / total) * 100).toFixed(2));
      } else if (field === 'percentage') {
        const total = Number(commercial?.total_value) || 0;
        m.amount = Number(((Number(value) / 100) * total).toFixed(2));
      }
      next[idx] = m;
      return next;
    });
  };

  const totals = milestones.reduce(
    (acc, m) => ({ amount: acc.amount + Number(m.amount || 0), percentage: acc.percentage + Number(m.percentage || 0) }),
    { amount: 0, percentage: 0 }
  );
  const totalValue = Number(commercial?.total_value || 0);
  const amountValid = totalValue === 0 || Math.abs(totals.amount - totalValue) < 0.01;
  const pctValid = milestones.length === 0 || Math.abs(totals.percentage - 100) < 0.01;

  const saveMilestones = async () => {
    if (!amountValid) {
      toast.error(`Milestone amounts (${totals.amount}) must equal project value (${totalValue})`);
      return;
    }
    if (!pctValid) {
      toast.error(`Milestone percentages must total 100 (got ${totals.percentage.toFixed(2)})`);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        milestones: milestones.map(({ _new, ...rest }) => ({
          ...rest,
          id: _new ? undefined : rest.id,
          amount: Number(rest.amount || 0),
          percentage: Number(rest.percentage || 0),
          delivery_date: rest.delivery_date || null,
          invoice_due_date: rest.invoice_due_date || null,
        })),
      };
      const res = await api.put(`/commercials/${id}/milestones`, payload);
      setMilestones(res.data.milestones || []);
      const refreshed = await api.get(`/commercials/${id}`);
      setCommercial(refreshed.data);
      toast.success('Milestones saved');
      fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save milestones');
    } finally {
      setSaving(false);
    }
  };

  const setMilestoneStatus = async (milestone_id, status) => {
    try {
      const res = await api.patch(`/commercials/${id}/milestones/${milestone_id}`, { status });
      setMilestones(res.data.milestones || []);
      const refreshed = await api.get(`/commercials/${id}`);
      setCommercial(refreshed.data);
      toast.success('Milestone updated');
      fetchAll();
    } catch (e) {
      toast.error('Failed to update milestone status');
    }
  };

  const regenerateBilling = async () => {
    setSaving(true);
    try {
      const res = await api.post(`/commercials/${id}/regenerate-billing`);
      setCommercial((prev) => ({ ...prev, billing_schedule: res.data.billing_schedule }));
      toast.success('Billing schedule regenerated');
    } catch (e) {
      toast.error('Failed to regenerate schedule');
    } finally {
      setSaving(false);
    }
  };

  const raiseInvoice = async (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = {
      milestone_id: invoiceDialog.milestone_id || undefined,
      billing_schedule_id: invoiceDialog.billing_schedule_id || undefined,
      invoice_number: form.get('invoice_number'),
      amount: Number(form.get('amount')),
      due_date: form.get('due_date') || undefined,
      notes: form.get('notes') || undefined,
    };
    try {
      await api.post(`/commercials/${id}/invoices`, payload);
      toast.success('Invoice raised');
      setInvoiceDialog({ open: false, milestone_id: null, billing_schedule_id: null, suggestedAmount: 0 });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to raise invoice');
    }
  };

  const recordPayment = async (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = {
      invoice_id: paymentDialog.invoice?.id,
      amount: Number(form.get('amount')),
      method: form.get('method') || undefined,
      reference: form.get('reference') || undefined,
      paid_at: form.get('paid_at') || undefined,
    };
    try {
      await api.post(`/commercials/${id}/payments`, payload);
      toast.success('Payment recorded');
      setPaymentDialog({ open: false, invoice: null });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to record payment');
    }
  };

  const uploadDocument = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const file = form.querySelector('input[name="file"]').files[0];
    if (!file) return;
    const data = new FormData();
    data.append('file', file);
    data.append('document_type', form.querySelector('select[name="document_type"]').value);
    data.append('title', form.querySelector('input[name="title"]').value || '');
    try {
      await api.post(`/commercials/${id}/documents`, data, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Document uploaded');
      setUploadDialog(false);
      fetchAll();
    } catch (err) {
      toast.error('Upload failed');
    }
  };

  const deleteDocument = async (docId) => {
    if (!window.confirm('Delete this document?')) return;
    try {
      await api.delete(`/commercials/${id}/documents/${docId}`);
      toast.success('Deleted');
      fetchAll();
    } catch (err) {
      toast.error('Failed to delete');
    }
  };

  const downloadDocument = async (doc) => {
    try {
      const res = await api.get(`/commercials/${id}/documents/${doc.id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Download failed');
    }
  };

  if (loading || !commercial) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const isOneTime = commercial.type === 'one_time';
  const totalRealized = payments.reduce((a, p) => a + Number(p.amount || 0), 0);
  const realizedPct = totalValue > 0 ? Math.min(100, (totalRealized / totalValue) * 100) : 0;

  return (
    <div className="space-y-6" data-testid="commercial-detail-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <Button variant="ghost" onClick={() => navigate('/commercials')} data-testid="back-to-commercials">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {isOneTime ? <Briefcase className="w-5 h-5 text-primary" /> : <Repeat className="w-5 h-5 text-primary" />}
            <h1 className="text-2xl font-bold">{commercial.lead_title}</h1>
            <Badge variant="secondary">{isOneTime ? 'One-Time Project' : 'Recurring Contract'}</Badge>
            {!isOneTime && commercial.contract_status && (
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200 capitalize">
                {commercial.contract_status.replace('_', ' ')}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Customer: <strong>{commercial.customer_name || '—'}</strong> · Lead{' '}
            <Link to={`/leads/${commercial.lead_id}`} className="text-primary hover:underline">view</Link>
          </p>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <KPI label={isOneTime ? 'Project Value' : 'Contract Value'} value={fmtMoney(isOneTime ? commercial.total_value : commercial.contract_value, commercial.currency)} />
        <KPI label="Revenue Realized" value={fmtMoney(totalRealized, commercial.currency)} sub={`${realizedPct.toFixed(0)}% of total`} />
        <KPI label={isOneTime ? 'Milestones' : 'Billing Periods'} value={isOneTime ? (commercial.milestones?.length || 0) : (commercial.billing_schedule?.length || 0)} />
        <KPI label="Outstanding Invoices" value={invoices.filter((i) => ['raised', 'partial', 'overdue'].includes(i.status)).length} />
      </div>

      {totalValue > 0 && (
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="font-medium">Revenue realization</span>
              <span className="text-muted-foreground">{fmtMoney(totalRealized, commercial.currency)} / {fmtMoney(totalValue, commercial.currency)}</span>
            </div>
            <Progress value={realizedPct} className="h-2" data-testid="revenue-progress" />
          </CardContent>
        </Card>
      )}

      <Tabs value={tab} onValueChange={setTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          {isOneTime ? (
            <TabsTrigger value="milestones" data-testid="tab-milestones">Milestones</TabsTrigger>
          ) : (
            <TabsTrigger value="billing" data-testid="tab-billing">Billing Schedule</TabsTrigger>
          )}
          <TabsTrigger value="invoices" data-testid="tab-invoices">Invoices &amp; Payments</TabsTrigger>
          <TabsTrigger value="documents" data-testid="tab-documents">Documents</TabsTrigger>
          <TabsTrigger value="activity" data-testid="tab-activity">Activity</TabsTrigger>
        </TabsList>

        {/* === OVERVIEW === */}
        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle>Commercial setup</CardTitle>
              <CardDescription>
                {isOneTime ? 'Capture the project commercials, owners, and billing contact.' : 'Capture the contract terms, billing cycle, and renewal preferences.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Currency">
                  <Select value={commercial.currency || 'INR'} onValueChange={(v) => updateField('currency', v)}>
                    <SelectTrigger data-testid="currency-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {['INR', 'USD', 'EUR', 'GBP'].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </Field>

                {isOneTime ? (
                  <>
                    <Field label="Total Project Value">
                      <Input type="number" value={commercial.total_value || ''} onChange={(e) => updateField('total_value', e.target.value)} data-testid="total-value-input" />
                    </Field>
                    <Field label="Project Start Date">
                      <Input type="date" value={commercial.start_date || ''} onChange={(e) => updateField('start_date', e.target.value)} data-testid="project-start-date" />
                    </Field>
                    <Field label="Estimated End Date">
                      <Input type="date" value={commercial.end_date || ''} onChange={(e) => updateField('end_date', e.target.value)} data-testid="project-end-date" />
                    </Field>
                    <Field label="Project Owner">
                      <UserSelect value={commercial.project_owner_id} onChange={(v) => updateField('project_owner_id', v)} users={users} testid="project-owner-select" />
                    </Field>
                    <Field label="Delivery SPOC">
                      <UserSelect value={commercial.delivery_spoc_id} onChange={(v) => updateField('delivery_spoc_id', v)} users={users} testid="delivery-spoc-select" />
                    </Field>
                    <Field label="Billing Contact">
                      <UserSelect value={commercial.billing_contact_id} onChange={(v) => updateField('billing_contact_id', v)} users={users} testid="billing-contact-select" />
                    </Field>
                  </>
                ) : (
                  <>
                    <Field label="Contract Value">
                      <Input type="number" value={commercial.contract_value || ''} onChange={(e) => updateField('contract_value', e.target.value)} data-testid="contract-value-input" />
                    </Field>
                    <Field label="Billing Frequency">
                      <Select value={commercial.billing_frequency || ''} onValueChange={(v) => updateField('billing_frequency', v)}>
                        <SelectTrigger data-testid="billing-frequency-select"><SelectValue placeholder="Select" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="monthly">Monthly</SelectItem>
                          <SelectItem value="quarterly">Quarterly</SelectItem>
                          <SelectItem value="half_yearly">Half-Yearly</SelectItem>
                          <SelectItem value="annual">Annual</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Contract Start Date">
                      <Input type="date" value={commercial.contract_start_date || ''} onChange={(e) => updateField('contract_start_date', e.target.value)} data-testid="contract-start-date" />
                    </Field>
                    <Field label="Contract End Date">
                      <Input type="date" value={commercial.contract_end_date || ''} onChange={(e) => updateField('contract_end_date', e.target.value)} data-testid="contract-end-date" />
                    </Field>
                    <Field label="Renewal Type">
                      <Select value={commercial.renewal_type || 'manual'} onValueChange={(v) => updateField('renewal_type', v)}>
                        <SelectTrigger data-testid="renewal-type-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="manual">Manual Renewal</SelectItem>
                          <SelectItem value="auto">Auto Renew</SelectItem>
                          <SelectItem value="approval_required">Approval Required</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Renewal Notice Period (days)">
                      <Input type="number" value={commercial.renewal_notice_days ?? 30} onChange={(e) => updateField('renewal_notice_days', e.target.value)} data-testid="renewal-notice-days" />
                    </Field>
                    <Field label="Auto Renewal">
                      <Select value={String(commercial.auto_renewal || false)} onValueChange={(v) => updateField('auto_renewal', v === 'true')}>
                        <SelectTrigger data-testid="auto-renewal-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="true">Yes</SelectItem>
                          <SelectItem value="false">No</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Account Manager">
                      <UserSelect value={commercial.account_manager_id} onChange={(v) => updateField('account_manager_id', v)} users={users} testid="account-manager-select" />
                    </Field>
                    <Field label="Contract Owner">
                      <UserSelect value={commercial.contract_owner_id} onChange={(v) => updateField('contract_owner_id', v)} users={users} testid="contract-owner-select" />
                    </Field>
                    <Field label="Billing Contact">
                      <UserSelect value={commercial.billing_contact_id} onChange={(v) => updateField('billing_contact_id', v)} users={users} testid="billing-contact-select-r" />
                    </Field>
                    <Field label="Contract Status">
                      <Select value={commercial.contract_status || 'active'} onValueChange={(v) => updateField('contract_status', v)}>
                        <SelectTrigger data-testid="contract-status-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="active">Active</SelectItem>
                          <SelectItem value="renewal_due">Renewal Due</SelectItem>
                          <SelectItem value="renewed">Renewed</SelectItem>
                          <SelectItem value="expired">Expired</SelectItem>
                          <SelectItem value="cancelled">Cancelled</SelectItem>
                          <SelectItem value="on_hold">On Hold</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                  </>
                )}
              </div>
              <Field label="Notes">
                <Textarea value={commercial.notes || ''} onChange={(e) => updateField('notes', e.target.value)} rows={3} data-testid="commercial-notes" />
              </Field>
              <div className="flex gap-2">
                <Button onClick={saveOverview} disabled={saving} data-testid="save-overview-btn">
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? 'Saving…' : 'Save changes'}
                </Button>
                {!isOneTime && (
                  <Button variant="outline" onClick={regenerateBilling} disabled={saving} data-testid="regenerate-billing-btn">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Regenerate billing schedule
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* === MILESTONES === */}
        {isOneTime && (
          <TabsContent value="milestones">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Delivery & Payment Milestones</CardTitle>
                    <CardDescription>Total amounts must equal project value; percentages must total 100%.</CardDescription>
                  </div>
                  <Button onClick={addMilestone} size="sm" data-testid="add-milestone-btn">
                    <Plus className="w-4 h-4 mr-1" />
                    Add milestone
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Validation banner */}
                <div className={`text-sm rounded-md p-3 ${amountValid && pctValid ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-200' : 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-200'}`}>
                  Sum:{' '}
                  <strong data-testid="ms-total-amount">{fmtMoney(totals.amount, commercial.currency)}</strong> of {fmtMoney(totalValue, commercial.currency)}{' '}
                  · <strong data-testid="ms-total-percentage">{totals.percentage.toFixed(2)}%</strong> of 100%
                  {(!amountValid || !pctValid) && <span className="ml-2">— adjust before saving.</span>}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="py-2 w-[40px]">#</th>
                        <th className="py-2">Name</th>
                        <th className="py-2 w-[140px]">Delivery date</th>
                        <th className="py-2 w-[140px]">Invoice due</th>
                        <th className="py-2 w-[140px]">Amount</th>
                        <th className="py-2 w-[100px]">%</th>
                        <th className="py-2 w-[160px]">Status</th>
                        <th className="py-2 w-[80px]"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {milestones.map((m, idx) => (
                        <tr key={m.id} className="border-b last:border-0" data-testid={`milestone-row-${idx}`}>
                          <td className="py-2">
                            <div className="flex flex-col items-center gap-1">
                              <button type="button" onClick={() => moveMilestone(idx, -1)} className="text-muted-foreground hover:text-foreground"><ChevronUp className="w-3 h-3" /></button>
                              <span className="text-xs">{idx + 1}</span>
                              <button type="button" onClick={() => moveMilestone(idx, 1)} className="text-muted-foreground hover:text-foreground"><ChevronDown className="w-3 h-3" /></button>
                            </div>
                          </td>
                          <td className="py-2 pr-2">
                            <Input value={m.name} onChange={(e) => updateMilestone(idx, 'name', e.target.value)} placeholder="Milestone name" data-testid={`milestone-name-${idx}`} />
                            <Textarea className="mt-1 text-xs" rows={1} value={m.description || ''} onChange={(e) => updateMilestone(idx, 'description', e.target.value)} placeholder="Description (optional)" />
                          </td>
                          <td className="py-2 pr-2">
                            <Input type="date" value={m.delivery_date || ''} onChange={(e) => updateMilestone(idx, 'delivery_date', e.target.value)} data-testid={`milestone-delivery-${idx}`} />
                          </td>
                          <td className="py-2 pr-2">
                            <Input type="date" value={m.invoice_due_date || ''} onChange={(e) => updateMilestone(idx, 'invoice_due_date', e.target.value)} />
                          </td>
                          <td className="py-2 pr-2">
                            <Input type="number" value={m.amount} onChange={(e) => updateMilestone(idx, 'amount', e.target.value)} data-testid={`milestone-amount-${idx}`} />
                          </td>
                          <td className="py-2 pr-2">
                            <Input type="number" step="0.01" value={m.percentage} onChange={(e) => updateMilestone(idx, 'percentage', e.target.value)} data-testid={`milestone-pct-${idx}`} />
                          </td>
                          <td className="py-2 pr-2">
                            <Select value={m.status} onValueChange={(v) => updateMilestone(idx, 'status', v)}>
                              <SelectTrigger data-testid={`milestone-status-${idx}`}><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {Object.entries(MILESTONE_STATUS_STYLES).map(([k, v]) => (
                                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="py-2">
                            <div className="flex gap-1">
                              {!m._new && (
                                <Button size="icon" variant="ghost" onClick={() => setInvoiceDialog({ open: true, milestone_id: m.id, billing_schedule_id: null, suggestedAmount: m.amount })} title="Raise invoice" data-testid={`raise-invoice-btn-${idx}`}>
                                  <Receipt className="w-4 h-4" />
                                </Button>
                              )}
                              <Button size="icon" variant="ghost" onClick={() => removeMilestone(idx)} title="Delete" data-testid={`remove-milestone-${idx}`}>
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {milestones.length === 0 && (
                        <tr><td colSpan={8} className="py-8 text-center text-muted-foreground">No milestones yet. Click "Add milestone" to begin.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Timeline visualization */}
                {milestones.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium mb-2">Timeline</h4>
                    <div className="space-y-2">
                      {milestones.map((m, idx) => (
                        <div key={m.id} className="flex items-center gap-3 text-sm">
                          <div className="w-2 h-2 rounded-full bg-primary" />
                          <span className="font-medium min-w-[120px]">{m.delivery_date ? formatDate(m.delivery_date) : 'TBD'}</span>
                          <span className="flex-1">{m.name || `Milestone ${idx + 1}`}</span>
                          <Badge className={MILESTONE_STATUS_STYLES[m.status]?.cls}>{MILESTONE_STATUS_STYLES[m.status]?.label}</Badge>
                          <span className="text-muted-foreground">{fmtMoney(m.amount, commercial.currency)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Button onClick={saveMilestones} disabled={saving || !amountValid || !pctValid} data-testid="save-milestones-btn">
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? 'Saving…' : 'Save milestones'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* === BILLING SCHEDULE (recurring) === */}
        {!isOneTime && (
          <TabsContent value="billing">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Billing Schedule</CardTitle>
                    <CardDescription>Auto-generated from billing frequency and contract dates.</CardDescription>
                  </div>
                  <Button size="sm" variant="outline" onClick={regenerateBilling} disabled={saving} data-testid="regenerate-billing-tab-btn">
                    <RefreshCw className="w-4 h-4 mr-2" />Regenerate
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="py-2 w-[40px]">#</th>
                        <th className="py-2">Period</th>
                        <th className="py-2">Due date</th>
                        <th className="py-2">Amount</th>
                        <th className="py-2">Status</th>
                        <th className="py-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(commercial.billing_schedule || []).map((b, idx) => (
                        <tr key={b.id} className="border-b last:border-0" data-testid={`billing-row-${idx}`}>
                          <td className="py-2">{idx + 1}</td>
                          <td className="py-2">{formatDate(b.period_start)} → {formatDate(b.period_end)}</td>
                          <td className="py-2">{formatDate(b.due_date)}</td>
                          <td className="py-2">{fmtMoney(b.amount, commercial.currency)}</td>
                          <td className="py-2"><Badge className={BILLING_STATUS_STYLES[b.status]?.cls}>{BILLING_STATUS_STYLES[b.status]?.label}</Badge></td>
                          <td className="py-2">
                            {b.status === 'scheduled' && (
                              <Button size="sm" variant="ghost" onClick={() => setInvoiceDialog({ open: true, milestone_id: null, billing_schedule_id: b.id, suggestedAmount: b.amount })} data-testid={`raise-invoice-billing-${idx}`}>
                                <Receipt className="w-4 h-4 mr-1" />
                                Raise invoice
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {(commercial.billing_schedule || []).length === 0 && (
                        <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">No billing periods. Set billing frequency + contract dates and regenerate.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* === INVOICES & PAYMENTS === */}
        <TabsContent value="invoices">
          <div className="grid lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Receipt className="w-4 h-4 text-amber-500" /> Invoices</CardTitle>
              </CardHeader>
              <CardContent>
                {invoices.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No invoices raised yet.</p>
                ) : (
                  <div className="space-y-2">
                    {invoices.map((inv) => (
                      <div key={inv.id} className="flex items-center justify-between p-3 border rounded-md" data-testid={`invoice-row-${inv.id}`}>
                        <div className="flex-1">
                          <div className="font-medium">{inv.invoice_number} · {fmtMoney(inv.amount, inv.currency)}</div>
                          <div className="text-xs text-muted-foreground">
                            Raised {formatDate(inv.raised_at)} · Due {formatDate(inv.due_date) || '—'}
                            {inv.amount_paid > 0 && ` · Paid ${fmtMoney(inv.amount_paid, inv.currency)}`}
                          </div>
                        </div>
                        <Badge className={INVOICE_STATUS_STYLES[inv.status]?.cls}>{INVOICE_STATUS_STYLES[inv.status]?.label}</Badge>
                        {['raised', 'partial', 'overdue'].includes(inv.status) && (
                          <Button size="sm" variant="outline" className="ml-2" onClick={() => setPaymentDialog({ open: true, invoice: inv })} data-testid={`record-payment-${inv.id}`}>
                            <Wallet className="w-3 h-3 mr-1" />Record payment
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Wallet className="w-4 h-4 text-green-500" /> Payments</CardTitle>
              </CardHeader>
              <CardContent>
                {payments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No payments recorded yet.</p>
                ) : (
                  <div className="space-y-2">
                    {payments.map((p) => (
                      <div key={p.id} className="flex items-center justify-between p-3 border rounded-md">
                        <div>
                          <div className="font-medium">{fmtMoney(p.amount, p.currency)}{p.method ? ` · ${p.method}` : ''}</div>
                          <div className="text-xs text-muted-foreground">{formatDateTime(p.paid_at)}{p.reference ? ` · Ref ${p.reference}` : ''}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* === DOCUMENTS === */}
        <TabsContent value="documents">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Attached documents</CardTitle>
                <Button size="sm" onClick={() => setUploadDialog(true)} data-testid="upload-doc-btn">
                  <Upload className="w-4 h-4 mr-2" />Upload
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {documents.length === 0 ? (
                <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
              ) : (
                <div className="space-y-2">
                  {documents.map((d) => (
                    <div key={d.id} className="flex items-center gap-3 p-3 border rounded-md" data-testid={`doc-row-${d.id}`}>
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      <div className="flex-1">
                        <div className="font-medium text-sm">{d.title}</div>
                        <div className="text-xs text-muted-foreground capitalize">{d.document_type} · {(d.size / 1024).toFixed(1)} KB · uploaded {formatDate(d.uploaded_at)} by {d.uploaded_by_name}</div>
                      </div>
                      <Button size="icon" variant="ghost" onClick={() => downloadDocument(d)}><Download className="w-4 h-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => deleteDocument(d.id)}><Trash2 className="w-4 h-4 text-red-500" /></Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* === ACTIVITY === */}
        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Activity className="w-4 h-4 text-primary" /> Activity log</CardTitle>
            </CardHeader>
            <CardContent>
              {activity.length === 0 ? (
                <p className="text-sm text-muted-foreground">No activity yet.</p>
              ) : (
                <ul className="space-y-3">
                  {activity.map((a) => (
                    <li key={a.id} className="flex gap-3 text-sm">
                      <div className="w-2 h-2 mt-2 rounded-full bg-primary flex-shrink-0" />
                      <div>
                        <div>{a.message}</div>
                        <div className="text-xs text-muted-foreground">{formatDateTime(a.created_at)} · {a.user_name}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Invoice dialog */}
      <Dialog open={invoiceDialog.open} onOpenChange={(o) => setInvoiceDialog((p) => ({ ...p, open: o }))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Raise invoice</DialogTitle>
            <DialogDescription>Create an invoice record. PDF generation will arrive in a future release.</DialogDescription>
          </DialogHeader>
          <form onSubmit={raiseInvoice} className="space-y-3">
            <Field label="Invoice number">
              <Input name="invoice_number" required data-testid="invoice-number-input" placeholder="INV-001" />
            </Field>
            <Field label="Amount">
              <Input name="amount" type="number" required defaultValue={invoiceDialog.suggestedAmount || ''} data-testid="invoice-amount-input" />
            </Field>
            <Field label="Due date">
              <Input name="due_date" type="date" />
            </Field>
            <Field label="Notes">
              <Textarea name="notes" rows={2} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setInvoiceDialog({ open: false, milestone_id: null, billing_schedule_id: null, suggestedAmount: 0 })}>Cancel</Button>
              <Button type="submit" data-testid="invoice-submit">Raise invoice</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Payment dialog */}
      <Dialog open={paymentDialog.open} onOpenChange={(o) => setPaymentDialog((p) => ({ ...p, open: o }))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record payment</DialogTitle>
            <DialogDescription>Invoice {paymentDialog.invoice?.invoice_number}</DialogDescription>
          </DialogHeader>
          <form onSubmit={recordPayment} className="space-y-3">
            <Field label="Amount">
              <Input name="amount" type="number" required defaultValue={paymentDialog.invoice ? (paymentDialog.invoice.amount - (paymentDialog.invoice.amount_paid || 0)) : ''} data-testid="payment-amount-input" />
            </Field>
            <Field label="Method (e.g. bank transfer)">
              <Input name="method" />
            </Field>
            <Field label="Reference">
              <Input name="reference" />
            </Field>
            <Field label="Paid at">
              <Input name="paid_at" type="date" />
            </Field>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setPaymentDialog({ open: false, invoice: null })}>Cancel</Button>
              <Button type="submit" data-testid="payment-submit">Save</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Upload dialog */}
      <Dialog open={uploadDialog} onOpenChange={setUploadDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload document</DialogTitle>
            <DialogDescription>Attach proposals, SOWs, signed contracts, or invoice PDFs.</DialogDescription>
          </DialogHeader>
          <form onSubmit={uploadDocument} className="space-y-3">
            <Field label="File">
              <Input name="file" type="file" required />
            </Field>
            <Field label="Document type">
              <select name="document_type" className="w-full h-9 rounded-md border bg-background px-3 text-sm" defaultValue="contract">
                <option value="proposal">Proposal</option>
                <option value="sow">SOW</option>
                <option value="contract">Signed Contract</option>
                <option value="invoice">Invoice</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field label="Title (optional)">
              <Input name="title" />
            </Field>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setUploadDialog(false)}>Cancel</Button>
              <Button type="submit" data-testid="upload-submit">Upload</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const Field = ({ label, children }) => (
  <div className="space-y-1.5">
    <Label className="text-xs uppercase tracking-wider text-muted-foreground">{label}</Label>
    {children}
  </div>
);

const KPI = ({ label, value, sub }) => (
  <Card>
    <CardContent className="py-4">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-xl font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </CardContent>
  </Card>
);

const UserSelect = ({ value, onChange, users, testid }) => (
  <Select value={value || '__none__'} onValueChange={(v) => onChange(v === '__none__' ? null : v)}>
    <SelectTrigger data-testid={testid}><SelectValue placeholder="Select user" /></SelectTrigger>
    <SelectContent>
      <SelectItem value="__none__">— None —</SelectItem>
      {users.map((u) => (
        <SelectItem key={u.id} value={u.id}>{u.name} ({u.email})</SelectItem>
      ))}
    </SelectContent>
  </Select>
);

export default CommercialDetail;
