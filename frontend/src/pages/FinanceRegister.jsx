import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Download, Filter, X, Loader2, ChevronRight, IndianRupee,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';

// Lifecycle → readable label + colour
export const LIFECYCLE_META = {
  created: { label: 'Created', color: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
  ready_for_invoice: { label: 'Ready for Invoice', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
  invoice_raised: { label: 'Invoice Raised', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  invoice_sent: { label: 'Invoice Sent', color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' },
  awaiting_payment: { label: 'Awaiting Payment', color: 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300' },
  payment_received: { label: 'Payment Received', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
  referral_payable: { label: 'Referral Payable', color: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300' },
  referral_paid: { label: 'Referral Paid', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' },
  closed: { label: 'Closed', color: 'bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200' },
};

const REVENUE_TYPE_LABEL = {
  one_time: 'One-Time',
  milestone: 'Milestone',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-Yearly',
  annual: 'Annual',
  renewal: 'Renewal',
  upsell: 'Upsell',
  cross_sell: 'Cross-Sell',
  other: 'Other',
};

export const StatusBadge = ({ status }) => {
  const m = LIFECYCLE_META[status] || { label: status, color: 'bg-slate-100 text-slate-700' };
  return <Badge className={`${m.color} border-0 text-[10px] font-semibold`}>{m.label}</Badge>;
};

// ---- Filter bar ----
const FilterBar = ({ filters, onChange, onReset, options }) => (
  <Card>
    <CardContent className="pt-4 pb-3 space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
        <Filter className="w-4 h-4" /> Filters
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
        <div>
          <label className="text-[11px] text-muted-foreground">Status</label>
          <Select value={filters.lifecycle_status || 'all'} onValueChange={(v) => onChange({ lifecycle_status: v === 'all' ? '' : v })}>
            <SelectTrigger data-testid="filter-status"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {Object.entries(LIFECYCLE_META).map(([k, m]) => (
                <SelectItem key={k} value={k}>{m.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground">Revenue type</label>
          <Select value={filters.revenue_type || 'all'} onValueChange={(v) => onChange({ revenue_type: v === 'all' ? '' : v })}>
            <SelectTrigger data-testid="filter-revenue-type"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {Object.entries(REVENUE_TYPE_LABEL).map(([k, l]) => (
                <SelectItem key={k} value={k}>{l}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground">Category</label>
          <Select value={filters.primary_category_id || 'all'} onValueChange={(v) => onChange({ primary_category_id: v === 'all' ? '' : v })}>
            <SelectTrigger data-testid="filter-category"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {(options.categories || []).map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground">Due from</label>
          <Input type="date" value={filters.due_from || ''} onChange={(e) => onChange({ due_from: e.target.value })} data-testid="filter-due-from" />
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground">Due to</label>
          <Input type="date" value={filters.due_to || ''} onChange={(e) => onChange({ due_to: e.target.value })} data-testid="filter-due-to" />
        </div>
      </div>
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={onReset} data-testid="reset-filters-btn">
          <X className="w-3.5 h-3.5 mr-1" /> Reset
        </Button>
      </div>
    </CardContent>
  </Card>
);

// ---- Main Grid Page ----
export const CommissionRegister = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    lifecycle_status: searchParams.get('status') || '',
    revenue_type: searchParams.get('type') || '',
    primary_category_id: '',
    due_from: '',
    due_to: '',
  });
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const r = await api.get('/finance/revenue-events', { params });
      setEvents(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load events');
    } finally { setLoading(false); }
  };

  useEffect(() => {
    api.get('/master/primary-categories').then((r) => setCategories(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => { fetchEvents(); }, [filters]);

  const filtered = useMemo(() => {
    if (!search.trim()) return events;
    const q = search.toLowerCase();
    return events.filter((e) =>
      (e.name || '').toLowerCase().includes(q)
      || (e.customer_name || '').toLowerCase().includes(q)
      || (e.lead_title || '').toLowerCase().includes(q)
    );
  }, [events, search]);

  const exportCsv = () => {
    if (filtered.length === 0) return toast.info('Nothing to export.');
    const headers = ['Revenue Event', 'Lead', 'Customer', 'Selling Partner', 'Revenue Type', 'Expected', 'Vyapaar %', 'Vyapaar Amt', 'Referral %', 'Referral Amt', 'Net Revenue', 'Due Date', 'Status'];
    const rows = filtered.map((e) => [
      e.name, e.lead_title, e.customer_name, e.selling_partner_name || '',
      REVENUE_TYPE_LABEL[e.revenue_type] || e.revenue_type,
      e.expected_amount, e.vyapaar_pct, e.vyapaar_amount, e.referral_pct, e.referral_amount, e.net_revenue,
      e.due_date || '', LIFECYCLE_META[e.lifecycle_status]?.label || e.lifecycle_status,
    ]);
    const csv = [headers, ...rows].map((row) => row.map((cell) => {
      const s = String(cell ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `commission-register-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totals = useMemo(() => filtered.reduce((acc, e) => {
    acc.expected += Number(e.expected_amount || 0);
    acc.vyapaar += Number(e.vyapaar_amount || 0);
    acc.referral += Number(e.referral_amount || 0);
    acc.net += Number(e.net_revenue || 0);
    return acc;
  }, { expected: 0, vyapaar: 0, referral: 0, net: 0 }), [filtered]);

  return (
    <div className="space-y-5" data-testid="commission-register">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/finance"><Button variant="ghost" size="sm"><ArrowLeft className="w-3.5 h-3.5 mr-1" /> Dashboard</Button></Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight mt-1">Commission Register</h1>
          <p className="text-sm text-muted-foreground">Every revenue event across every commercial. One row = one billable unit.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search lead / customer / event…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
            data-testid="register-search"
          />
          <Button variant="outline" size="sm" onClick={exportCsv} data-testid="register-export-btn">
            <Download className="w-4 h-4 mr-1" /> Export CSV
          </Button>
        </div>
      </div>

      <FilterBar
        filters={filters}
        onChange={(patch) => setFilters((f) => ({ ...f, ...patch }))}
        onReset={() => setFilters({ lifecycle_status: '', revenue_type: '', primary_category_id: '', due_from: '', due_to: '' })}
        options={{ categories }}
      />

      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm">
            {loading ? '…' : `${filtered.length} event${filtered.length === 1 ? '' : 's'}`}
          </CardTitle>
          <div className="text-xs text-muted-foreground flex items-center gap-4">
            <span>Expected: <b className="text-foreground">{formatCurrency(totals.expected)}</b></span>
            <span className="text-indigo-700 dark:text-indigo-300">Vyapaar: <b>{formatCurrency(totals.vyapaar)}</b></span>
            <span className="text-rose-600 dark:text-rose-300">Referral: <b>{formatCurrency(totals.referral)}</b></span>
            <span className="text-emerald-700 dark:text-emerald-300">Net: <b>{formatCurrency(totals.net)}</b></span>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-4 space-y-2">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-9 w-full" />)}</div>
          ) : (
            <Table data-testid="register-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Event</TableHead>
                  <TableHead>Customer / Lead</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Expected</TableHead>
                  <TableHead className="text-right">Vyapaar</TableHead>
                  <TableHead className="text-right">Referral</TableHead>
                  <TableHead className="text-right">Net</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((e) => (
                  <TableRow
                    key={e.id}
                    className="cursor-pointer hover:bg-muted/40"
                    onClick={() => navigate(`/finance/events/${e.id}`)}
                    data-testid={`register-row-${e.id}`}
                  >
                    <TableCell className="font-medium">{e.name}</TableCell>
                    <TableCell>
                      <div className="text-sm">{e.customer_name || '—'}</div>
                      <div className="text-[11px] text-muted-foreground">{e.lead_title}</div>
                    </TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">{REVENUE_TYPE_LABEL[e.revenue_type] || e.revenue_type}</Badge></TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(e.expected_amount)}</TableCell>
                    <TableCell className="text-right tabular-nums text-indigo-700 dark:text-indigo-300">
                      {formatCurrency(e.vyapaar_amount)} <span className="text-[10px] text-muted-foreground">({e.vyapaar_pct}%)</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-rose-600 dark:text-rose-300">
                      {e.referral_amount ? formatCurrency(e.referral_amount) : '—'} {e.referral_amount ? <span className="text-[10px] text-muted-foreground">({e.referral_pct}%)</span> : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-semibold text-emerald-700 dark:text-emerald-300">{formatCurrency(e.net_revenue)}</TableCell>
                    <TableCell className="text-xs">{e.due_date || '—'}</TableCell>
                    <TableCell><StatusBadge status={e.lifecycle_status} /></TableCell>
                    <TableCell><ChevronRight className="w-4 h-4 text-muted-foreground" /></TableCell>
                  </TableRow>
                ))}
                {filtered.length === 0 && (
                  <TableRow><TableCell colSpan={10} className="text-center text-muted-foreground py-10">
                    <IndianRupee className="w-6 h-6 mx-auto mb-2 opacity-40" />
                    No revenue events match these filters.
                  </TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// ---- Revenue Event Detail Screen ----
const Field = ({ label, children }) => (
  <div>
    <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">{label}</div>
    <div className="text-sm">{children || <span className="text-muted-foreground">—</span>}</div>
  </div>
);

const SectionCard = ({ title, icon: Icon, children, testid }) => (
  <Card data-testid={testid}>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-indigo-600" />}
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-3">{children}</CardContent>
  </Card>
);

// Allowed forward transitions (mirrors backend state machine)
const FORWARD_NEXT = {
  created: { action: 'mark_ready_for_invoice', label: 'Mark Ready for Invoice' },
  ready_for_invoice: { action: 'mark_invoice_raised', label: 'Mark Invoice Raised' },
  invoice_raised: { action: 'mark_invoice_sent', label: 'Mark Invoice Sent' },
  invoice_sent: { action: 'mark_payment_received', label: 'Mark Payment Received' },
  awaiting_payment: { action: 'mark_payment_received', label: 'Mark Payment Received' },
  payment_received: { action: 'mark_referral_payable', label: 'Move to Referral Payable' },
  referral_payable: { action: 'mark_referral_paid', label: 'Mark Referral Paid' },
  referral_paid: { action: 'close', label: 'Close Event' },
};

export const RevenueEventDetail = () => {
  const navigate = useNavigate();
  const eventId = window.location.pathname.split('/').pop();
  const [event, setEvent] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [edit, setEdit] = useState({});

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [evRes, tlRes] = await Promise.all([
        api.get(`/finance/revenue-events/${eventId}`),
        api.get(`/finance/revenue-events/${eventId}/timeline`),
      ]);
      setEvent(evRes.data);
      setTimeline(tlRes.data || []);
      setEdit({});
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load event');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, [eventId]);

  if (loading || !event) {
    return <div className="space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-32 w-full" /><Skeleton className="h-32 w-full" /></div>;
  }

  const merged = { ...event, ...edit };
  const next = FORWARD_NEXT[event.lifecycle_status];

  const saveSection = async () => {
    if (Object.keys(edit).length === 0) return;
    setSaving(true);
    try {
      const r = await api.patch(`/finance/revenue-events/${eventId}`, edit);
      setEvent(r.data);
      setEdit({});
      toast.success('Saved');
      // Reload timeline
      const tl = await api.get(`/finance/revenue-events/${eventId}/timeline`);
      setTimeline(tl.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const transition = async (action) => {
    try {
      const r = await api.post(`/finance/revenue-events/${eventId}/transitions/${action}`);
      setEvent(r.data);
      toast.success(`Status → ${LIFECYCLE_META[r.data.lifecycle_status]?.label}`);
      const tl = await api.get(`/finance/revenue-events/${eventId}/timeline`);
      setTimeline(tl.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Transition failed');
    }
  };

  const set = (k, v) => setEdit((s) => ({ ...s, [k]: v }));
  const hasEdits = Object.keys(edit).length > 0;

  return (
    <div className="space-y-5" data-testid="revenue-event-detail">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link to="/finance/register"><Button variant="ghost" size="sm"><ArrowLeft className="w-3.5 h-3.5 mr-1" /> Register</Button></Link>
          <h1 className="text-2xl font-bold tracking-tight mt-1">{event.name}</h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
            <span>{event.customer_name}</span> · <span>{event.lead_title}</span>
            <StatusBadge status={event.lifecycle_status} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {hasEdits && (
            <Button size="sm" onClick={saveSection} disabled={saving} data-testid="save-event-btn">
              {saving && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}Save changes
            </Button>
          )}
          {next && (
            <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700" onClick={() => transition(next.action)} data-testid="transition-btn">
              {next.label}
            </Button>
          )}
          {event.lifecycle_status === 'closed' && (
            <Button size="sm" variant="outline" onClick={() => transition('reopen')} data-testid="reopen-btn">
              Reopen
            </Button>
          )}
        </div>
      </div>

      {/* Section A — Commercial Summary */}
      <SectionCard title="Commercial Summary" testid="section-summary">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Customer">{event.customer_name}</Field>
          <Field label="Lead">{event.lead_title}</Field>
          <Field label="Selling Partner">{event.selling_partner_name}</Field>
          <Field label="Referral Partner">{event.referral_partner_name}</Field>
          <Field label="Category">{event.primary_category_name}</Field>
          <Field label="Revenue Type">{REVENUE_TYPE_LABEL[event.revenue_type] || event.revenue_type}</Field>
          <Field label="Due Date">{event.due_date}</Field>
          <Field label="Source">{event.source_kind}</Field>
        </div>
      </SectionCard>

      {/* Section B — Commission Breakdown */}
      <SectionCard title="Commission Breakdown" testid="section-commission">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <Field label="Expected Amount">
            <Input type="number" value={merged.expected_amount ?? ''} onChange={(e) => set('expected_amount', parseFloat(e.target.value) || 0)} data-testid="edit-expected" />
          </Field>
          <Field label={`Vyapaar (${event.vyapaar_pct}%)`}>
            <div className="text-lg font-semibold text-indigo-700 dark:text-indigo-300">{formatCurrency(event.vyapaar_amount)}</div>
          </Field>
          <Field label={`Referral (${event.referral_pct}%)`}>
            <div className="text-lg font-semibold text-rose-600 dark:text-rose-300">{formatCurrency(event.referral_amount)}</div>
          </Field>
          <Field label="Net Revenue (after referral)">
            <div className="text-lg font-semibold text-emerald-700 dark:text-emerald-300">{formatCurrency(event.net_revenue)}</div>
          </Field>
          <Field label="Outstanding Balance">{formatCurrency(event.outstanding_balance)}</Field>
        </div>
      </SectionCard>

      {/* Section C — Invoice Tracking */}
      <SectionCard title="Invoice Tracking (Manual)" testid="section-invoice">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Field label="Invoice #"><Input value={merged.invoice_number || ''} onChange={(e) => set('invoice_number', e.target.value)} data-testid="edit-invoice-number" /></Field>
          <Field label="Invoice Date"><Input type="date" value={merged.invoice_date || ''} onChange={(e) => set('invoice_date', e.target.value)} data-testid="edit-invoice-date" /></Field>
          <Field label="Due Date"><Input type="date" value={merged.invoice_due_date || ''} onChange={(e) => set('invoice_due_date', e.target.value)} data-testid="edit-invoice-due" /></Field>
          <Field label="Invoice PDF URL"><Input value={merged.invoice_pdf_url || ''} onChange={(e) => set('invoice_pdf_url', e.target.value)} placeholder="Zoho / Drive link" data-testid="edit-invoice-pdf" /></Field>
          <Field label="Raised By">{event.invoice_raised_by_name || <span className="text-muted-foreground">Set on transition</span>}</Field>
          <Field label="Invoice Source"><Badge variant="outline">{event.invoice_source || 'manual'}</Badge></Field>
        </div>
        <Field label="Remarks">
          <Input value={merged.invoice_remarks || ''} onChange={(e) => set('invoice_remarks', e.target.value)} data-testid="edit-invoice-remarks" />
        </Field>
      </SectionCard>

      {/* Section D — Collection Tracking */}
      <SectionCard title="Collection Tracking" testid="section-collection">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Field label="Amount Received"><Input type="number" value={merged.amount_received ?? ''} onChange={(e) => set('amount_received', parseFloat(e.target.value) || 0)} data-testid="edit-amount-received" /></Field>
          <Field label="Payment Date"><Input type="date" value={merged.payment_date || ''} onChange={(e) => set('payment_date', e.target.value)} data-testid="edit-payment-date" /></Field>
          <Field label="Bank Reference"><Input value={merged.bank_reference || ''} onChange={(e) => set('bank_reference', e.target.value)} data-testid="edit-bank-ref" /></Field>
          <Field label="UTR"><Input value={merged.utr || ''} onChange={(e) => set('utr', e.target.value)} data-testid="edit-utr" /></Field>
          <Field label="Outstanding Balance"><span className="font-semibold">{formatCurrency(event.outstanding_balance)}</span></Field>
        </div>
        <Field label="Collection Notes">
          <Input value={merged.collection_notes || ''} onChange={(e) => set('collection_notes', e.target.value)} data-testid="edit-collection-notes" />
        </Field>
      </SectionCard>

      {/* Section E — Referral Settlement (visible only if referral commission applicable) */}
      {Number(event.referral_pct || 0) > 0 && (
        <SectionCard title="Referral Settlement" testid="section-referral">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="Referral Partner">{event.referral_partner_name || '—'}</Field>
            <Field label="Referral Invoice Received">
              <Select value={String(merged.referral_invoice_received ?? false)} onValueChange={(v) => set('referral_invoice_received', v === 'true')}>
                <SelectTrigger data-testid="edit-ref-invoice-rec"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">Yes</SelectItem>
                  <SelectItem value="false">No</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="Referral Invoice #"><Input value={merged.referral_invoice_number || ''} onChange={(e) => set('referral_invoice_number', e.target.value)} data-testid="edit-ref-invoice-no" /></Field>
            <Field label="Payment Date"><Input type="date" value={merged.referral_payment_date || ''} onChange={(e) => set('referral_payment_date', e.target.value)} data-testid="edit-ref-pay-date" /></Field>
            <Field label="UTR"><Input value={merged.referral_utr || ''} onChange={(e) => set('referral_utr', e.target.value)} data-testid="edit-ref-utr" /></Field>
            <Field label="TDS"><Input type="number" value={merged.referral_tds ?? ''} onChange={(e) => set('referral_tds', parseFloat(e.target.value) || 0)} data-testid="edit-ref-tds" /></Field>
            <Field label="GST"><Input type="number" value={merged.referral_gst ?? ''} onChange={(e) => set('referral_gst', parseFloat(e.target.value) || 0)} data-testid="edit-ref-gst" /></Field>
          </div>
          <Field label="Remarks">
            <Input value={merged.referral_remarks || ''} onChange={(e) => set('referral_remarks', e.target.value)} data-testid="edit-ref-remarks" />
          </Field>
        </SectionCard>
      )}

      {/* Timeline */}
      <SectionCard title="Finance Timeline" testid="section-timeline">
        <div className="space-y-2">
          {timeline.length === 0 && <div className="text-sm text-muted-foreground">No activity yet.</div>}
          {timeline.map((row) => (
            <div key={row.id} className="flex items-start gap-3 text-sm border-l-2 border-indigo-200 dark:border-indigo-900 pl-3 py-1">
              <div className="flex-1">
                <div className="font-medium">{row.message}</div>
                <div className="text-[11px] text-muted-foreground">
                  {row.user_name || 'System'} · <span className="font-mono">{row.action}</span> · {new Date(row.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
};

export default CommissionRegister;
