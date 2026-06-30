import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  IndianRupee, FileText, AlertTriangle, TrendingUp, Repeat,
  CalendarClock, Activity, Receipt, Wallet, ArrowRight, RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';

// --- Small KPI tile shared across the dashboard ---
const KpiTile = ({ icon: Icon, label, value, sub, tone = 'indigo', testid }) => {
  const tones = {
    indigo: 'from-indigo-500/10 to-indigo-500/0 text-indigo-700 dark:text-indigo-300',
    emerald: 'from-emerald-500/10 to-emerald-500/0 text-emerald-700 dark:text-emerald-300',
    rose: 'from-rose-500/10 to-rose-500/0 text-rose-700 dark:text-rose-300',
    amber: 'from-amber-500/10 to-amber-500/0 text-amber-700 dark:text-amber-300',
    violet: 'from-violet-500/10 to-violet-500/0 text-violet-700 dark:text-violet-300',
    slate: 'from-slate-500/10 to-slate-500/0 text-slate-700 dark:text-slate-300',
  };
  return (
    <Card data-testid={testid} className={`bg-gradient-to-br ${tones[tone] || tones.indigo} border-l-2`}>
      <CardContent className="pt-4 pb-3 space-y-1">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider font-semibold">
          <Icon className="w-3.5 h-3.5" />
          {label}
        </div>
        <div className="text-2xl font-bold tracking-tight text-foreground">{value}</div>
        {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
};

const SectionCard = ({ title, description, icon: Icon, children }) => (
  <Card>
    <CardHeader className="pb-3">
      <CardTitle className="flex items-center gap-2 text-base">
        {Icon && <Icon className="w-4 h-4 text-indigo-600" />}
        {title}
      </CardTitle>
      {description && <CardDescription className="text-xs">{description}</CardDescription>}
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const FinanceDashboard = () => {
  const [kpi, setKpi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchKpi = async (silent = false) => {
    if (!silent) setLoading(true);
    setRefreshing(true);
    try {
      const r = await api.get('/finance/dashboard');
      setKpi(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load finance dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchKpi();
  }, []);

  const r = kpi?.receivables || {};
  const p = kpi?.payables || {};
  const rev = kpi?.revenue || {};
  const ops = kpi?.operations || {};

  const quickFilters = useMemo(() => ([
    { label: 'Pending Invoices', count: r.invoices_pending_count, to: '/finance/register?status=ready_for_invoice', tone: 'amber' },
    { label: 'Awaiting Collection', count: ops.collections_pending, to: '/finance/register?status=awaiting_payment', tone: 'indigo' },
    { label: 'Overdue', count: r.overdue_collections_count, to: '/finance/register?status=invoice_sent&overdue=1', tone: 'rose' },
    { label: 'Settlements Pending', count: ops.settlements_pending, to: '/finance/register?status=referral_payable', tone: 'violet' },
  ]), [r, ops]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4,5,6,7,8].map(i => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="finance-dashboard">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Finance & Commission Management</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Revenue events, invoices, collections & settlements — as of {kpi?.as_of}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchKpi(true)} disabled={refreshing} data-testid="refresh-kpi-btn">
            <RefreshCw className={`w-4 h-4 mr-1 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Link to="/finance/register">
            <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="open-register-btn">
              <FileText className="w-4 h-4 mr-1" /> Open Commission Register <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Quick filter chips */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {quickFilters.map((q) => (
          <Link key={q.label} to={q.to} data-testid={`quick-filter-${q.label.toLowerCase().replace(/\s/g, '-')}`}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer">
              <CardContent className="pt-4 pb-3 flex items-center justify-between">
                <div>
                  <div className="text-xs text-muted-foreground">{q.label}</div>
                  <div className="text-xl font-bold mt-0.5">{q.count ?? 0}</div>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Receivables */}
      <SectionCard title="Receivables" description="What customers owe Vyapaar" icon={IndianRupee}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiTile testid="kpi-commission-receivable" icon={IndianRupee} tone="indigo"
                   label="Commission Receivable"
                   value={formatCurrency(r.total_commission_receivable || 0)}
                   sub="Open events × Vyapaar %" />
          <KpiTile testid="kpi-invoices-pending" icon={FileText} tone="amber"
                   label="Invoices Pending"
                   value={r.invoices_pending_count || 0}
                   sub="Ready to raise" />
          <KpiTile testid="kpi-collections-pending" icon={Wallet} tone="indigo"
                   label="Collections Pending"
                   value={formatCurrency(r.collections_pending_amount || 0)}
                   sub="Invoiced & awaiting payment" />
          <KpiTile testid="kpi-overdue-collections" icon={AlertTriangle} tone="rose"
                   label="Overdue Collections"
                   value={formatCurrency(r.overdue_collections_amount || 0)}
                   sub={`${r.overdue_collections_count || 0} event(s)`} />
        </div>
      </SectionCard>

      {/* Payables */}
      <SectionCard title="Payables" description="What Vyapaar owes to referrers" icon={Receipt}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiTile testid="kpi-referral-payable" icon={Receipt} tone="violet"
                   label="Referral Payable"
                   value={formatCurrency(p.referral_payable_amount || 0)} />
          <KpiTile testid="kpi-referral-pending" icon={Activity} tone="amber"
                   label="Settlements Pending"
                   value={p.referral_pending_count || 0} />
          <KpiTile testid="kpi-referral-overdue" icon={AlertTriangle} tone="rose"
                   label="Settlements Overdue (>15d)"
                   value={p.referral_overdue_count || 0} />
        </div>
      </SectionCard>

      {/* Revenue */}
      <SectionCard title="Revenue" description="Gross, net & forecast" icon={TrendingUp}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <KpiTile testid="kpi-gross-revenue" icon={IndianRupee} tone="emerald"
                   label="Gross Revenue Realised"
                   value={formatCurrency(rev.gross_revenue_realised || 0)}
                   sub="Payment received & beyond" />
          <KpiTile testid="kpi-net-revenue" icon={TrendingUp} tone="emerald"
                   label="Vyapaar Net Revenue"
                   value={formatCurrency(rev.vyapaar_net_revenue_realised || 0)}
                   sub="After referral payouts" />
          <KpiTile testid="kpi-recurring-open" icon={Repeat} tone="indigo"
                   label="Recurring Revenue (Open)"
                   value={formatCurrency(rev.recurring_revenue_open || 0)} />
          <KpiTile testid="kpi-rev-month" icon={CalendarClock} tone="indigo"
                   label="Expected — This Month"
                   value={formatCurrency(rev.expected_revenue_this_month || 0)} />
          <KpiTile testid="kpi-rev-quarter" icon={CalendarClock} tone="indigo"
                   label="Expected — This Quarter"
                   value={formatCurrency(rev.expected_revenue_this_quarter || 0)} />
          <KpiTile testid="kpi-rev-year" icon={CalendarClock} tone="indigo"
                   label="Expected — This Year"
                   value={formatCurrency(rev.expected_revenue_this_year || 0)} />
        </div>
      </SectionCard>

      {/* Operations */}
      <SectionCard title="Operations" description="Pipeline health across the revenue chain" icon={Activity}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <KpiTile testid="kpi-ops-created" icon={Activity} tone="slate"
                   label="Events — Created"
                   value={ops.events_created || 0} />
          <KpiTile testid="kpi-ops-closed" icon={Activity} tone="emerald"
                   label="Events — Closed"
                   value={ops.events_closed || 0} />
          <KpiTile testid="kpi-ops-total" icon={Activity} tone="indigo"
                   label="Total Events"
                   value={ops.total_events || 0} />
        </div>
      </SectionCard>
    </div>
  );
};

export default FinanceDashboard;
