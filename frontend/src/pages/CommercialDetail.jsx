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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator, DropdownMenuLabel } from '../components/ui/dropdown-menu';
import { ArrowLeft, Plus, Trash2, Save, Briefcase, Repeat, FileText, Upload, Activity, Calendar, Receipt, Wallet, RefreshCw, Download, ChevronUp, ChevronDown, GripVertical, Search as SearchIcon, ExternalLink, Sparkles, TrendingUp, AlertTriangle, Wand2 } from 'lucide-react';
import SearchableUserSelect from '../components/SearchableUserSelect';
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
  const [dragIndex, setDragIndex] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [renewalProb, setRenewalProb] = useState(null);
  const [paymentRisk, setPaymentRisk] = useState(null);
  const [activityFilter, setActivityFilter] = useState('all');
  const [activitySearch, setActivitySearch] = useState('');
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

  // Phase 35 — Allow switching One-Time ↔ Recurring after creation
  const [typeChangeDialog, setTypeChangeDialog] = useState(false);
  const [typeChangeSaving, setTypeChangeSaving] = useState(false);
  const changeType = async () => {
    if (!commercial) return;
    const nextType = commercial.type === 'one_time' ? 'recurring' : 'one_time';
    setTypeChangeSaving(true);
    try {
      const res = await api.patch(`/commercials/${id}`, { type: nextType });
      setCommercial(res.data);
      setMilestones((res.data.milestones || []).map((m) => ({ ...m })));
      toast.success(`Contract type changed to ${nextType === 'one_time' ? 'One-Time' : 'Recurring'}`);
      setTypeChangeDialog(false);
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to change type');
    } finally {
      setTypeChangeSaving(false);
    }
  };

  const saveOverview = async () => {
    setSaving(true);
    try {
      const payload = {};
      const fields = commercial.type === 'one_time'
        ? ['total_value', 'start_date', 'end_date', 'project_owner_id', 'delivery_spoc_id', 'billing_contact_id', 'notes', 'currency']
        : ['contract_value', 'billing_frequency', 'contract_start_date', 'contract_end_date', 'auto_renewal', 'renewal_type', 'renewal_notice_days', 'account_manager_id', 'contract_owner_id', 'billing_contact_id', 'notes', 'currency', 'contract_status', 'one_time_fee_amount', 'one_time_fee_label', 'one_time_fee_due_date'];
      fields.forEach((f) => {
        if (commercial[f] !== undefined && commercial[f] !== null && commercial[f] !== '') payload[f] = commercial[f];
        else if (commercial[f] === '') payload[f] = null;
      });
      // Numeric coercion
      if (payload.total_value !== undefined) payload.total_value = Number(payload.total_value);
      if (payload.contract_value !== undefined) payload.contract_value = Number(payload.contract_value);
      if (payload.renewal_notice_days !== undefined) payload.renewal_notice_days = Number(payload.renewal_notice_days);
      if (payload.one_time_fee_amount !== undefined) payload.one_time_fee_amount = Number(payload.one_time_fee_amount) || 0;
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

  // Drag-and-drop reorder
  const handleDragStart = (idx) => (e) => {
    setDragIndex(idx);
    e.dataTransfer.effectAllowed = 'move';
    // Required for Firefox
    try { e.dataTransfer.setData('text/plain', String(idx)); } catch (_) { /* noop */ }
  };
  const handleDragOver = (idx) => (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };
  const handleDrop = (idx) => (e) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === idx) {
      setDragIndex(null);
      return;
    }
    setMilestones((prev) => {
      const next = [...prev];
      const [moved] = next.splice(dragIndex, 1);
      next.splice(idx, 0, moved);
      return next;
    });
    setDragIndex(null);
  };
  const handleDragEnd = () => setDragIndex(null);

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

  // Auto-distribute helpers.
  // mode = 'evenly'    -> overwrite all amounts, splitting project value across all rows.
  // mode = 'remaining' -> only fill rows whose amount is 0/empty with the unallocated balance.
  // The last targeted row absorbs the rounding remainder so amounts sum EXACTLY to total_value.
  const autoDistribute = (mode) => {
    const total = Number(commercial?.total_value) || 0;
    if (total <= 0) {
      toast.error('Set a project value first before auto-distributing.');
      return;
    }
    if (milestones.length === 0) {
      toast.error('Add at least one milestone row first.');
      return;
    }
    setMilestones((prev) => {
      const next = prev.map((m) => ({ ...m }));
      let targetIndices = [];
      let allocatable = total;
      if (mode === 'remaining') {
        const allocated = next.reduce(
          (s, m) => s + (Number(m.amount) > 0 ? Number(m.amount) : 0),
          0,
        );
        allocatable = Math.max(0, Number((total - allocated).toFixed(2)));
        targetIndices = next
          .map((m, i) => (Number(m.amount) > 0 ? -1 : i))
          .filter((i) => i >= 0);
        if (targetIndices.length === 0) {
          toast.info('No empty milestones to fill. Use "Split evenly" to re-distribute all rows.');
          return prev;
        }
        if (allocatable <= 0) {
          toast.info('No remaining amount left to allocate.');
          return prev;
        }
      } else {
        targetIndices = next.map((_, i) => i);
      }
      const n = targetIndices.length;
      // Distribute to 2-decimal precision, last row absorbs the remainder.
      const perRow = Math.floor((allocatable / n) * 100) / 100;
      let remainder = Number((allocatable - perRow * n).toFixed(2));
      targetIndices.forEach((idx, k) => {
        const isLast = k === targetIndices.length - 1;
        const amt = isLast ? Number((perRow + remainder).toFixed(2)) : perRow;
        next[idx].amount = amt;
        next[idx].percentage = Number(((amt / total) * 100).toFixed(2));
      });
      return next;
    });
    const verb = mode === 'remaining' ? 'Remaining amount distributed' : 'Project value split evenly';
    toast.success(`${verb} across milestones.`);
  };

  const totals = milestones.reduce(
    (acc, m) => ({ amount: acc.amount + Number(m.amount || 0), percentage: acc.percentage + Number(m.percentage || 0) }),
    { amount: 0, percentage: 0 }
  );
  const totalValue = Number(commercial?.total_value || 0);
  const amountValid = totalValue === 0 || Math.abs(totals.amount - totalValue) < 0.01;
  // Amounts are the source of truth when a project value is set — if amounts
  // match, the percentage breakdown is valid regardless of per-row 2-decimal
  // display rounding (e.g. 3 × 33.33% = 99.99%). Without a project value,
  // allow a small 0.5% tolerance for per-row rounding drift.
  const pctValid =
    milestones.length === 0 ||
    (totalValue > 0 ? amountValid : Math.abs(totals.percentage - 100) <= 0.5);

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
      is_one_time_fee: form.get('is_one_time_fee') === 'on' || invoiceDialog.is_one_time_fee || false,
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

  const downloadInvoicePdf = async (inv) => {
    try {
      const res = await api.get(`/commercials/${id}/invoices/${inv.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `invoice_${inv.invoice_number || inv.id}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('PDF download failed');
    }
  };

  const fetchAiInsights = useCallback(async () => {
    if (!commercial) return;
    if (commercial.type === 'recurring') {
      api.get(`/commercials/${id}/ai/renewal-probability`).then((r) => setRenewalProb(r.data)).catch(() => {});
    }
    api.get(`/commercials/${id}/ai/payment-delay-risk`).then((r) => setPaymentRisk(r.data)).catch(() => {});
  }, [commercial, id]);

  useEffect(() => { fetchAiInsights(); }, [fetchAiInsights]);

  const requestAiMilestones = async () => {
    if (!commercial?.total_value || commercial.total_value <= 0) {
      toast.error('Set total project value before requesting AI suggestions');
      return;
    }
    setAiBusy(true);
    try {
      const res = await api.post('/commercials/ai/suggest-milestones', {
        project_title: commercial.lead_title,
        description: commercial.notes,
        total_value: Number(commercial.total_value),
        currency: commercial.currency || 'INR',
        start_date: commercial.start_date,
        end_date: commercial.end_date,
      });
      const suggested = (res.data.milestones || []).map((m, i) => ({
        id: `tmp_ai_${Date.now()}_${i}`,
        _new: true,
        name: m.name,
        description: m.description,
        delivery_date: m.delivery_date || '',
        invoice_due_date: '',
        amount: m.amount,
        percentage: m.percentage,
        status: 'pending',
      }));
      if (milestones.length > 0 && !window.confirm(`Replace existing ${milestones.length} milestone(s) with ${suggested.length} AI suggestions?`)) {
        setAiBusy(false);
        return;
      }
      setMilestones(suggested);
      toast.success(`${suggested.length} AI milestones loaded — review and save`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'AI suggestion failed');
    } finally {
      setAiBusy(false);
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
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs gap-1"
              onClick={() => setTypeChangeDialog(true)}
              data-testid="change-commercial-type-btn"
              title="Switch between One-Time Project and Recurring Contract"
            >
              <RefreshCw className="w-3 h-3" />
              Change type
            </Button>
            {!isOneTime && commercial.contract_status && (
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200 capitalize">
                {commercial.contract_status.replace('_', ' ')}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Customer: <strong>{commercial.customer_name || '—'}</strong> · Lead{' '}
            <Link to={`/leads/${commercial.lead_id}`} className="text-primary hover:underline">view</Link>
            {commercial.renewal_lead_id && (
              <>
                {' · '}
                <Link to={`/leads/${commercial.renewal_lead_id}`} className="text-amber-600 hover:underline font-medium inline-flex items-center gap-1" data-testid="renewal-lead-link">
                  Renewal pipeline <ExternalLink className="w-3 h-3" />
                </Link>
              </>
            )}
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
              {/* Phase 36 — One-Time Setup Fee on Recurring contracts (SaaS pattern) */}
              {!isOneTime && (
                <Card className="border-violet-200 dark:border-violet-900 bg-gradient-to-br from-violet-50/50 to-indigo-50/30 dark:from-violet-950/20 dark:to-indigo-950/10 mt-4">
                  <CardContent className="py-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-violet-600" />
                      <h4 className="font-semibold text-sm">One-Time Setup Fee</h4>
                      {commercial.one_time_fee_status && (
                        <span className="ml-auto text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-white/60 dark:bg-card/60 border">
                          {commercial.one_time_fee_status}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Onboarding / implementation / customisation fee billed once at the start of the contract.
                      Uses the same Vyapaar commission % as the base deal. Will appear as a dedicated invoice line.
                    </p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Field label="Amount">
                        <Input
                          type="number"
                          value={commercial.one_time_fee_amount ?? ''}
                          onChange={(e) => updateField('one_time_fee_amount', e.target.value)}
                          placeholder="0"
                          data-testid="one-time-fee-amount"
                        />
                      </Field>
                      <Field label="Label">
                        <Input
                          value={commercial.one_time_fee_label || ''}
                          onChange={(e) => updateField('one_time_fee_label', e.target.value)}
                          placeholder="e.g. Onboarding fee"
                          data-testid="one-time-fee-label"
                        />
                      </Field>
                      <Field label="Due date">
                        <Input
                          type="date"
                          value={commercial.one_time_fee_due_date || ''}
                          onChange={(e) => updateField('one_time_fee_due_date', e.target.value)}
                          data-testid="one-time-fee-due"
                        />
                      </Field>
                    </div>
                  </CardContent>
                </Card>
              )}
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

          {/* AI insights panels */}
          <div className="grid gap-4 lg:grid-cols-2 mt-4">
            {!isOneTime && renewalProb && (
              <Card data-testid="renewal-probability-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><TrendingUp className="w-4 h-4 text-primary" /> Renewal probability</CardTitle>
                  <CardDescription>Heuristic score from payment history, tenure, and renewal config.</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-3 mb-2">
                    <span className={`text-3xl font-bold ${renewalProb.band === 'high' ? 'text-green-600' : renewalProb.band === 'medium' ? 'text-amber-600' : 'text-red-600'}`}>
                      {Math.round(renewalProb.probability * 100)}%
                    </span>
                    <Badge variant="outline" className="uppercase">{renewalProb.band}</Badge>
                  </div>
                  <Progress value={renewalProb.probability * 100} className="h-2 mb-3" />
                  <ul className="text-xs text-muted-foreground space-y-1">
                    {renewalProb.factors.map((f, i) => <li key={i}>• {f}</li>)}
                    {renewalProb.factors.length === 0 && <li>• No history available — score is baseline.</li>}
                  </ul>
                </CardContent>
              </Card>
            )}
            {paymentRisk && paymentRisk.invoices.length > 0 && (
              <Card data-testid="payment-risk-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-500" /> Payment-delay risk</CardTitle>
                  <CardDescription>
                    Avg historical pay-lag: {paymentRisk.avg_pay_lag_days ? `${paymentRisk.avg_pay_lag_days}d` : 'no history'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {paymentRisk.invoices.slice(0, 4).map((r) => (
                      <li key={r.invoice_id} className="flex items-center justify-between text-sm">
                        <div>
                          <div className="font-medium">{r.invoice_number}</div>
                          <div className="text-xs text-muted-foreground">{r.factors.join(' · ') || 'No risk factors'}</div>
                        </div>
                        <Badge className={r.band === 'high' ? 'bg-red-100 text-red-700' : r.band === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}>
                          {Math.round(r.risk_score * 100)}% · {r.band}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
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
                  <div className="flex gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={!totalValue || milestones.length === 0}
                          data-testid="auto-distribute-btn"
                        >
                          <Wand2 className="w-4 h-4 mr-1" />
                          Auto-distribute
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-64">
                        <DropdownMenuLabel className="text-xs">
                          Split {milestones.length} milestone{milestones.length === 1 ? '' : 's'}
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => autoDistribute('evenly')}
                          data-testid="auto-distribute-evenly"
                        >
                          <div className="flex flex-col">
                            <span className="font-medium">Split evenly across all</span>
                            <span className="text-xs text-muted-foreground">Overwrites all amounts</span>
                          </div>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => autoDistribute('remaining')}
                          data-testid="auto-distribute-remaining"
                        >
                          <div className="flex flex-col">
                            <span className="font-medium">Split remaining into empty rows</span>
                            <span className="text-xs text-muted-foreground">Keeps existing amounts</span>
                          </div>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <Button onClick={requestAiMilestones} size="sm" variant="outline" disabled={aiBusy} data-testid="ai-milestones-btn">
                      <Sparkles className={`w-4 h-4 mr-1 ${aiBusy ? 'animate-pulse' : ''}`} />
                      {aiBusy ? 'Thinking…' : 'AI suggest'}
                    </Button>
                    <Button onClick={addMilestone} size="sm" data-testid="add-milestone-btn">
                      <Plus className="w-4 h-4 mr-1" />
                      Add milestone
                    </Button>
                  </div>
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
                        <tr
                          key={m.id}
                          className={`border-b last:border-0 transition-colors ${dragIndex === idx ? 'opacity-40 bg-primary/5' : ''}`}
                          draggable
                          onDragStart={handleDragStart(idx)}
                          onDragOver={handleDragOver(idx)}
                          onDrop={handleDrop(idx)}
                          onDragEnd={handleDragEnd}
                          data-testid={`milestone-row-${idx}`}
                        >
                          <td className="py-2">
                            <div className="flex flex-col items-center gap-1">
                              <GripVertical className="w-3 h-3 text-muted-foreground cursor-grab" title="Drag to reorder" />
                              <span className="text-xs">{idx + 1}</span>
                              <div className="flex flex-col">
                                <button type="button" onClick={() => moveMilestone(idx, -1)} className="text-muted-foreground hover:text-foreground"><ChevronUp className="w-3 h-3" /></button>
                                <button type="button" onClick={() => moveMilestone(idx, 1)} className="text-muted-foreground hover:text-foreground"><ChevronDown className="w-3 h-3" /></button>
                              </div>
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
                        <Button size="icon" variant="ghost" className="ml-1" onClick={() => downloadInvoicePdf(inv)} title="Download PDF" data-testid={`download-pdf-${inv.id}`}>
                          <Download className="w-4 h-4" />
                        </Button>
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
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2"><Activity className="w-4 h-4 text-primary" /> Activity & Audit log</CardTitle>
                  <CardDescription>Every commercial change with user, timestamp and metadata.</CardDescription>
                </div>
                <div className="flex flex-col sm:flex-row gap-2">
                  <div className="relative">
                    <SearchIcon className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={activitySearch}
                      onChange={(e) => setActivitySearch(e.target.value)}
                      placeholder="Search activity…"
                      className="pl-7 w-56 h-9"
                      data-testid="activity-search"
                    />
                  </div>
                  <Select value={activityFilter} onValueChange={setActivityFilter}>
                    <SelectTrigger className="w-44 h-9" data-testid="activity-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All events</SelectItem>
                      <SelectItem value="created">Setup / created</SelectItem>
                      <SelectItem value="updated">Updates</SelectItem>
                      <SelectItem value="milestones_updated,milestone_status">Milestones</SelectItem>
                      <SelectItem value="invoice_raised,invoice_updated">Invoices</SelectItem>
                      <SelectItem value="payment_received">Payments</SelectItem>
                      <SelectItem value="document_uploaded,document_deleted">Documents</SelectItem>
                      <SelectItem value="billing_regenerated,renewal_lead_created">Billing & renewals</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {(() => {
                const filterTypes = activityFilter === 'all' ? null : new Set(activityFilter.split(','));
                const q = activitySearch.toLowerCase();
                const filtered = activity.filter((a) => {
                  if (filterTypes && !filterTypes.has(a.type)) return false;
                  if (q) {
                    const hay = `${a.message || ''} ${a.user_name || ''} ${a.type || ''}`.toLowerCase();
                    if (!hay.includes(q)) return false;
                  }
                  return true;
                });
                if (activity.length === 0) {
                  return <p className="text-sm text-muted-foreground">No activity yet.</p>;
                }
                if (filtered.length === 0) {
                  return <p className="text-sm text-muted-foreground">No events match your filter.</p>;
                }
                return (
                  <ul className="space-y-3" data-testid="activity-list">
                    {filtered.map((a) => (
                      <li key={a.id} className="flex gap-3 text-sm">
                        <div className="w-2 h-2 mt-2 rounded-full bg-primary flex-shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span>{a.message}</span>
                            <Badge variant="outline" className="text-[10px] capitalize">{(a.type || '').replace(/_/g, ' ')}</Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">{formatDateTime(a.created_at)} · {a.user_name}</div>
                          {a.meta && Object.keys(a.meta).length > 0 && (
                            <details className="text-[11px] text-muted-foreground mt-1">
                              <summary className="cursor-pointer hover:text-foreground">View metadata</summary>
                              <pre className="mt-1 p-2 rounded bg-muted/50 overflow-x-auto">{JSON.stringify(a.meta, null, 2)}</pre>
                            </details>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                );
              })()}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Phase 35 — Change Commercial Type Confirmation */}
      <Dialog open={typeChangeDialog} onOpenChange={setTypeChangeDialog}>
        <DialogContent data-testid="change-type-dialog">
          <DialogHeader>
            <DialogTitle>Change commercial type</DialogTitle>
            <DialogDescription>
              {commercial?.type === 'one_time'
                ? 'Switch this One-Time Project to a Recurring Contract. A fresh billing schedule will be generated from the existing terms.'
                : 'Switch this Recurring Contract to a One-Time Project. The existing billing schedule will be preserved for reference but new periods will not be generated.'}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30 p-3 text-sm">
            <p className="font-semibold text-amber-900 dark:text-amber-200">Heads-up</p>
            <p className="text-amber-800/90 dark:text-amber-200/80 mt-0.5">
              Already-raised invoices and recorded payments are preserved. Recheck the billing schedule / milestones after switching.
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTypeChangeDialog(false)}>Cancel</Button>
            <Button onClick={changeType} disabled={typeChangeSaving} data-testid="confirm-change-type-btn">
              {typeChangeSaving ? 'Switching…' : `Switch to ${commercial?.type === 'one_time' ? 'Recurring' : 'One-Time'}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
            {/* Phase 36 — flag this invoice as the recurring contract's One-Time Setup Fee */}
            {!isOneTime && commercial?.one_time_fee_amount > 0 && (
              <label className="flex items-center gap-2 text-sm bg-violet-50 dark:bg-violet-950/30 border border-violet-200 dark:border-violet-900 rounded-md p-2">
                <input
                  type="checkbox"
                  name="is_one_time_fee"
                  className="accent-violet-600"
                  data-testid="is-one-time-fee-checkbox"
                />
                <span>Mark this invoice as the One-Time Setup Fee ({fmtMoney(commercial.one_time_fee_amount, commercial.currency)})</span>
              </label>
            )}
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
  <SearchableUserSelect
    value={value || ''}
    onChange={(v) => onChange(v || null)}
    users={users}
    placeholder="Search and select user..."
    emptyText="No matching users."
    testId={testid}
    secondaryRender={(u) => u.email}
  />
);

export default CommercialDetail;
