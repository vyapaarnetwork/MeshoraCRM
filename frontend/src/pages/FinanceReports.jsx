import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Download, FileBarChart2, TrendingUp, Repeat, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';
import { LIFECYCLE_META, StatusBadge } from './FinanceRegister';

const downloadCsv = (filename, headers, rows) => {
  if (!rows.length) return toast.info('Nothing to export.');
  const csv = [headers, ...rows].map((r) => r.map((c) => {
    const s = String(c ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};

const todayIso = () => new Date().toISOString().slice(0, 10);

// Bucket helpers
const ageingBucket = (dateIso) => {
  if (!dateIso) return '—';
  const days = Math.floor((Date.now() - new Date(dateIso).getTime()) / 86_400_000);
  if (days <= 0) return 'Current';
  if (days <= 30) return '1–30 days';
  if (days <= 60) return '31–60 days';
  if (days <= 90) return '61–90 days';
  return '90+ days';
};

const ReportShell = ({ title, description, count, onExport, children }) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-2 pb-2">
      <div>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription className="text-xs">{description}</CardDescription>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline">{count} rows</Badge>
        <Button size="sm" variant="outline" onClick={onExport} data-testid="report-export-btn">
          <Download className="w-3.5 h-3.5 mr-1" /> Export CSV
        </Button>
      </div>
    </CardHeader>
    <CardContent className="overflow-x-auto">{children}</CardContent>
  </Card>
);

const FinanceReports = () => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/finance/revenue-events?limit=2000')
      .then((r) => setEvents(r.data || []))
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed to load events'))
      .finally(() => setLoading(false));
  }, []);

  // ---- Report data builders ----
  const pendingInvoice = useMemo(() => events.filter(e => e.lifecycle_status === 'ready_for_invoice'), [events]);
  const outstandingCollections = useMemo(() => events.filter(e =>
    ['invoice_raised', 'invoice_sent', 'awaiting_payment'].includes(e.lifecycle_status)
  ), [events]);
  const referralPayables = useMemo(() => events.filter(e =>
    ['payment_received', 'referral_payable'].includes(e.lifecycle_status) && Number(e.referral_amount || 0) > 0
  ), [events]);
  const collectionAgeing = useMemo(() => {
    const buckets = { 'Current': [], '1–30 days': [], '31–60 days': [], '61–90 days': [], '90+ days': [] };
    outstandingCollections.forEach(e => {
      const b = ageingBucket(e.due_date);
      if (buckets[b]) buckets[b].push(e);
    });
    return buckets;
  }, [outstandingCollections]);
  const recurringForecast = useMemo(() => {
    const recurringTypes = new Set(['monthly', 'quarterly', 'half_yearly', 'annual', 'renewal']);
    const today = todayIso();
    return events.filter(e =>
      recurringTypes.has(e.revenue_type)
      && (e.due_date || '') >= today
      && !['closed', 'referral_paid'].includes(e.lifecycle_status)
    );
  }, [events]);
  const renewalForecast = useMemo(() => {
    // Renewal-tagged + upcoming
    return events.filter(e => e.revenue_type === 'renewal' && (e.due_date || '') >= todayIso());
  }, [events]);
  const monthlyRevenue = useMemo(() => {
    // Group payment_received+ by month
    const groups = {};
    events.forEach(e => {
      if (!['payment_received', 'referral_payable', 'referral_paid', 'closed'].includes(e.lifecycle_status)) return;
      const month = (e.payment_date || e.due_date || '').slice(0, 7);
      if (!month) return;
      if (!groups[month]) groups[month] = { month, gross: 0, vyapaar: 0, referral: 0, net: 0, count: 0 };
      groups[month].gross += Number(e.expected_amount || 0);
      groups[month].vyapaar += Number(e.vyapaar_amount || 0);
      groups[month].referral += Number(e.referral_amount || 0);
      groups[month].net += Number(e.net_revenue || 0);
      groups[month].count += 1;
    });
    return Object.values(groups).sort((a, b) => a.month.localeCompare(b.month));
  }, [events]);
  const partnerRevenue = useMemo(() => {
    const groups = {};
    events.forEach(e => {
      const name = e.selling_partner_name || 'Direct';
      if (!groups[name]) groups[name] = { partner: name, gross: 0, vyapaar: 0, net: 0, count: 0 };
      groups[name].gross += Number(e.expected_amount || 0);
      groups[name].vyapaar += Number(e.vyapaar_amount || 0);
      groups[name].net += Number(e.net_revenue || 0);
      groups[name].count += 1;
    });
    return Object.values(groups).sort((a, b) => b.gross - a.gross);
  }, [events]);
  const categoryRevenue = useMemo(() => {
    const groups = {};
    events.forEach(e => {
      const name = e.primary_category_name || 'Uncategorised';
      if (!groups[name]) groups[name] = { category: name, gross: 0, vyapaar: 0, net: 0, count: 0 };
      groups[name].gross += Number(e.expected_amount || 0);
      groups[name].vyapaar += Number(e.vyapaar_amount || 0);
      groups[name].net += Number(e.net_revenue || 0);
      groups[name].count += 1;
    });
    return Object.values(groups).sort((a, b) => b.gross - a.gross);
  }, [events]);
  const grossVsNet = useMemo(() => {
    let gross = 0, vyapaar = 0, referral = 0, net = 0;
    events.forEach(e => {
      if (!['payment_received', 'referral_payable', 'referral_paid', 'closed'].includes(e.lifecycle_status)) return;
      gross += Number(e.expected_amount || 0);
      vyapaar += Number(e.vyapaar_amount || 0);
      referral += Number(e.referral_amount || 0);
      net += Number(e.net_revenue || 0);
    });
    return { gross, vyapaar, referral, net };
  }, [events]);
  const eventStatus = useMemo(() => {
    const counts = {};
    Object.keys(LIFECYCLE_META).forEach(k => { counts[k] = 0; });
    events.forEach(e => { counts[e.lifecycle_status] = (counts[e.lifecycle_status] || 0) + 1; });
    return counts;
  }, [events]);

  if (loading) {
    return <div className="space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>;
  }

  return (
    <div className="space-y-5" data-testid="finance-reports">
      <div>
        <Link to="/finance"><Button variant="ghost" size="sm"><ArrowLeft className="w-3.5 h-3.5 mr-1" /> Dashboard</Button></Link>
        <h1 className="text-2xl font-bold tracking-tight mt-1">Finance Reports</h1>
        <p className="text-sm text-muted-foreground">11 reports across receivables, payables, revenue & ageing.</p>
      </div>

      <Tabs defaultValue="pending-invoice" className="w-full">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="pending-invoice" data-testid="tab-pending-invoice">Pending Invoice</TabsTrigger>
          <TabsTrigger value="outstanding" data-testid="tab-outstanding">Outstanding Collections</TabsTrigger>
          <TabsTrigger value="referral-payables" data-testid="tab-referral-payables">Referral Payables</TabsTrigger>
          <TabsTrigger value="monthly-revenue" data-testid="tab-monthly-revenue">Monthly Revenue</TabsTrigger>
          <TabsTrigger value="partner-revenue" data-testid="tab-partner-revenue">Partner-wise</TabsTrigger>
          <TabsTrigger value="category-revenue" data-testid="tab-category-revenue">Category-wise</TabsTrigger>
          <TabsTrigger value="recurring-forecast" data-testid="tab-recurring-forecast">Recurring Forecast</TabsTrigger>
          <TabsTrigger value="renewal-forecast" data-testid="tab-renewal-forecast">Renewal Forecast</TabsTrigger>
          <TabsTrigger value="gross-vs-net" data-testid="tab-gross-vs-net">Gross vs Net</TabsTrigger>
          <TabsTrigger value="ageing" data-testid="tab-ageing">Collection Ageing</TabsTrigger>
          <TabsTrigger value="event-status" data-testid="tab-event-status">Event Status</TabsTrigger>
        </TabsList>

        <TabsContent value="pending-invoice" className="mt-3">
          <ReportShell title="Pending Invoice" description="Revenue events ready to be invoiced" count={pendingInvoice.length}
            onExport={() => downloadCsv('pending-invoice',
              ['Event', 'Customer', 'Lead', 'Expected', 'Vyapaar', 'Due Date'],
              pendingInvoice.map(e => [e.name, e.customer_name, e.lead_title, e.expected_amount, e.vyapaar_amount, e.due_date]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Customer</TableHead><TableHead className="text-right">Expected</TableHead><TableHead className="text-right">Vyapaar</TableHead><TableHead>Due</TableHead></TableRow></TableHeader>
              <TableBody>
                {pendingInvoice.map(e => (
                  <TableRow key={e.id}><TableCell><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell><TableCell>{e.customer_name}</TableCell><TableCell className="text-right">{formatCurrency(e.expected_amount)}</TableCell><TableCell className="text-right text-indigo-700 dark:text-indigo-300">{formatCurrency(e.vyapaar_amount)}</TableCell><TableCell>{e.due_date}</TableCell></TableRow>
                ))}
                {!pendingInvoice.length && <TableRow><TableCell colSpan={5} className="text-center py-6 text-muted-foreground">All invoices are up to date.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="outstanding" className="mt-3">
          <ReportShell title="Outstanding Collections" description="Invoiced events awaiting payment" count={outstandingCollections.length}
            onExport={() => downloadCsv('outstanding-collections',
              ['Event', 'Customer', 'Invoice #', 'Expected', 'Outstanding', 'Due', 'Status'],
              outstandingCollections.map(e => [e.name, e.customer_name, e.invoice_number || '', e.expected_amount, e.outstanding_balance, e.due_date, e.lifecycle_status]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Customer</TableHead><TableHead>Invoice #</TableHead><TableHead className="text-right">Outstanding</TableHead><TableHead>Due</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {outstandingCollections.map(e => (
                  <TableRow key={e.id}><TableCell><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell><TableCell>{e.customer_name}</TableCell><TableCell>{e.invoice_number || '—'}</TableCell><TableCell className="text-right">{formatCurrency(e.outstanding_balance)}</TableCell><TableCell>{e.due_date}</TableCell><TableCell><StatusBadge status={e.lifecycle_status} /></TableCell></TableRow>
                ))}
                {!outstandingCollections.length && <TableRow><TableCell colSpan={6} className="text-center py-6 text-muted-foreground">No outstanding collections.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="referral-payables" className="mt-3">
          <ReportShell title="Referral Payables" description="Amounts due to referrers after payment is received" count={referralPayables.length}
            onExport={() => downloadCsv('referral-payables',
              ['Event', 'Customer', 'Referral Partner', 'Ref %', 'Ref Amount', 'Status'],
              referralPayables.map(e => [e.name, e.customer_name, e.referral_partner_name || '', e.referral_pct, e.referral_amount, e.lifecycle_status]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Referrer</TableHead><TableHead className="text-right">Ref %</TableHead><TableHead className="text-right">Amount</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {referralPayables.map(e => (
                  <TableRow key={e.id}><TableCell><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell><TableCell>{e.referral_partner_name || '—'}</TableCell><TableCell className="text-right">{e.referral_pct}%</TableCell><TableCell className="text-right text-rose-600 dark:text-rose-300">{formatCurrency(e.referral_amount)}</TableCell><TableCell><StatusBadge status={e.lifecycle_status} /></TableCell></TableRow>
                ))}
                {!referralPayables.length && <TableRow><TableCell colSpan={5} className="text-center py-6 text-muted-foreground">No referral payables.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="monthly-revenue" className="mt-3">
          <ReportShell title="Monthly Revenue" description="Realised gross, vyapaar, referral, net per month" count={monthlyRevenue.length}
            onExport={() => downloadCsv('monthly-revenue',
              ['Month', 'Events', 'Gross', 'Vyapaar', 'Referral', 'Net'],
              monthlyRevenue.map(r => [r.month, r.count, r.gross, r.vyapaar, r.referral, r.net]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Month</TableHead><TableHead className="text-right">Events</TableHead><TableHead className="text-right">Gross</TableHead><TableHead className="text-right">Vyapaar</TableHead><TableHead className="text-right">Referral</TableHead><TableHead className="text-right">Net</TableHead></TableRow></TableHeader>
              <TableBody>
                {monthlyRevenue.map(r => (
                  <TableRow key={r.month}><TableCell className="font-medium">{r.month}</TableCell><TableCell className="text-right">{r.count}</TableCell><TableCell className="text-right">{formatCurrency(r.gross)}</TableCell><TableCell className="text-right text-indigo-700 dark:text-indigo-300">{formatCurrency(r.vyapaar)}</TableCell><TableCell className="text-right text-rose-600 dark:text-rose-300">{formatCurrency(r.referral)}</TableCell><TableCell className="text-right font-semibold text-emerald-700 dark:text-emerald-300">{formatCurrency(r.net)}</TableCell></TableRow>
                ))}
                {!monthlyRevenue.length && <TableRow><TableCell colSpan={6} className="text-center py-6 text-muted-foreground">No revenue realised yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="partner-revenue" className="mt-3">
          <ReportShell title="Partner-wise Revenue" description="Aggregated by selling partner" count={partnerRevenue.length}
            onExport={() => downloadCsv('partner-revenue', ['Partner', 'Events', 'Gross', 'Vyapaar', 'Net'], partnerRevenue.map(p => [p.partner, p.count, p.gross, p.vyapaar, p.net]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Partner</TableHead><TableHead className="text-right">Events</TableHead><TableHead className="text-right">Gross</TableHead><TableHead className="text-right">Vyapaar</TableHead><TableHead className="text-right">Net</TableHead></TableRow></TableHeader>
              <TableBody>
                {partnerRevenue.map(p => (
                  <TableRow key={p.partner}><TableCell className="font-medium">{p.partner}</TableCell><TableCell className="text-right">{p.count}</TableCell><TableCell className="text-right">{formatCurrency(p.gross)}</TableCell><TableCell className="text-right text-indigo-700 dark:text-indigo-300">{formatCurrency(p.vyapaar)}</TableCell><TableCell className="text-right text-emerald-700 dark:text-emerald-300">{formatCurrency(p.net)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="category-revenue" className="mt-3">
          <ReportShell title="Category-wise Revenue" description="Aggregated by primary category" count={categoryRevenue.length}
            onExport={() => downloadCsv('category-revenue', ['Category', 'Events', 'Gross', 'Vyapaar', 'Net'], categoryRevenue.map(c => [c.category, c.count, c.gross, c.vyapaar, c.net]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Category</TableHead><TableHead className="text-right">Events</TableHead><TableHead className="text-right">Gross</TableHead><TableHead className="text-right">Vyapaar</TableHead><TableHead className="text-right">Net</TableHead></TableRow></TableHeader>
              <TableBody>
                {categoryRevenue.map(c => (
                  <TableRow key={c.category}><TableCell className="font-medium">{c.category}</TableCell><TableCell className="text-right">{c.count}</TableCell><TableCell className="text-right">{formatCurrency(c.gross)}</TableCell><TableCell className="text-right text-indigo-700 dark:text-indigo-300">{formatCurrency(c.vyapaar)}</TableCell><TableCell className="text-right text-emerald-700 dark:text-emerald-300">{formatCurrency(c.net)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="recurring-forecast" className="mt-3">
          <ReportShell title="Recurring Revenue Forecast" description="Future MRR / QRR / ARR commitments" count={recurringForecast.length}
            onExport={() => downloadCsv('recurring-forecast', ['Event', 'Customer', 'Type', 'Expected', 'Due'], recurringForecast.map(e => [e.name, e.customer_name, e.revenue_type, e.expected_amount, e.due_date]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Customer</TableHead><TableHead>Type</TableHead><TableHead className="text-right">Expected</TableHead><TableHead>Due</TableHead></TableRow></TableHeader>
              <TableBody>
                {recurringForecast.map(e => (
                  <TableRow key={e.id}><TableCell><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell><TableCell>{e.customer_name}</TableCell><TableCell><Badge variant="outline">{e.revenue_type}</Badge></TableCell><TableCell className="text-right">{formatCurrency(e.expected_amount)}</TableCell><TableCell>{e.due_date}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="renewal-forecast" className="mt-3">
          <ReportShell title="Renewal Forecast" description="Upcoming renewal events" count={renewalForecast.length}
            onExport={() => downloadCsv('renewal-forecast', ['Event', 'Customer', 'Expected', 'Due'], renewalForecast.map(e => [e.name, e.customer_name, e.expected_amount, e.due_date]))}>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Customer</TableHead><TableHead className="text-right">Expected</TableHead><TableHead>Due</TableHead></TableRow></TableHeader>
              <TableBody>
                {renewalForecast.map(e => (
                  <TableRow key={e.id}><TableCell><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell><TableCell>{e.customer_name}</TableCell><TableCell className="text-right">{formatCurrency(e.expected_amount)}</TableCell><TableCell>{e.due_date}</TableCell></TableRow>
                ))}
                {!renewalForecast.length && <TableRow><TableCell colSpan={4} className="text-center py-6 text-muted-foreground">No upcoming renewals.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </ReportShell>
        </TabsContent>

        <TabsContent value="gross-vs-net" className="mt-3">
          <ReportShell title="Gross vs Net Revenue" description="Realised performance summary" count={1}
            onExport={() => downloadCsv('gross-vs-net', ['Metric', 'Amount'], [['Gross', grossVsNet.gross], ['Vyapaar', grossVsNet.vyapaar], ['Referral', grossVsNet.referral], ['Net', grossVsNet.net]])}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Gross Realised</div><div className="text-2xl font-bold">{formatCurrency(grossVsNet.gross)}</div></CardContent></Card>
              <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Vyapaar Share</div><div className="text-2xl font-bold text-indigo-700 dark:text-indigo-300">{formatCurrency(grossVsNet.vyapaar)}</div></CardContent></Card>
              <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Referral Paid Out</div><div className="text-2xl font-bold text-rose-600 dark:text-rose-300">{formatCurrency(grossVsNet.referral)}</div></CardContent></Card>
              <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Net to Vyapaar</div><div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{formatCurrency(grossVsNet.net)}</div></CardContent></Card>
            </div>
          </ReportShell>
        </TabsContent>

        <TabsContent value="ageing" className="mt-3">
          <ReportShell title="Collection Ageing" description="Outstanding events bucketed by due-date age" count={outstandingCollections.length}
            onExport={() => downloadCsv('collection-ageing',
              ['Bucket', 'Event', 'Customer', 'Outstanding', 'Due', 'Status'],
              Object.entries(collectionAgeing).flatMap(([bucket, rows]) =>
                rows.map(e => [bucket, e.name, e.customer_name, e.outstanding_balance, e.due_date, e.lifecycle_status])))}>
            {Object.entries(collectionAgeing).map(([bucket, rows]) => (
              <div key={bucket} className="mb-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-2">
                  <AlertTriangle className={`w-3 h-3 ${bucket === '90+ days' ? 'text-rose-500' : bucket === '61–90 days' ? 'text-amber-500' : 'text-slate-400'}`} /> {bucket}
                  <Badge variant="outline" className="text-[10px]">{rows.length}</Badge>
                  <span className="ml-auto font-semibold text-foreground">{formatCurrency(rows.reduce((a, b) => a + Number(b.outstanding_balance || 0), 0))}</span>
                </div>
                {rows.length > 0 && (
                  <Table>
                    <TableBody>
                      {rows.map(e => (
                        <TableRow key={e.id}>
                          <TableCell className="w-[260px]"><Link to={`/finance/events/${e.id}`} className="hover:underline font-medium">{e.name}</Link></TableCell>
                          <TableCell>{e.customer_name}</TableCell>
                          <TableCell className="text-right">{formatCurrency(e.outstanding_balance)}</TableCell>
                          <TableCell>{e.due_date}</TableCell>
                          <TableCell><StatusBadge status={e.lifecycle_status} /></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            ))}
          </ReportShell>
        </TabsContent>

        <TabsContent value="event-status" className="mt-3">
          <ReportShell title="Revenue Event Status" description="Count by lifecycle state" count={Object.keys(eventStatus).length}
            onExport={() => downloadCsv('event-status', ['Status', 'Count'], Object.entries(eventStatus).map(([s, c]) => [LIFECYCLE_META[s]?.label || s, c]))}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(eventStatus).map(([s, c]) => (
                <Card key={s} className="hover:shadow-sm">
                  <CardContent className="pt-4 flex items-center justify-between">
                    <div>
                      <StatusBadge status={s} />
                      <div className="text-2xl font-bold mt-1">{c}</div>
                    </div>
                    <Link to={`/finance/register?status=${s}`}>
                      <Button variant="ghost" size="sm">View →</Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </ReportShell>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default FinanceReports;
