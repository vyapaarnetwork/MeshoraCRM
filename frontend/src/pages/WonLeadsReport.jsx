import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Trophy, ArrowUpRight, ArrowDownRight, Minus, Loader2, Calendar, Send, IndianRupee } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import api from '../utils/api';
import { toast } from 'sonner';

const formatINR = (amount) => {
  const n = Number(amount || 0);
  if (Number.isNaN(n)) return '₹0';
  // Indian grouping: 1,25,000
  const sign = n < 0 ? '-' : '';
  const fixed = Math.abs(n).toFixed(0);
  let lastThree = fixed.slice(-3);
  const otherNumbers = fixed.slice(0, -3);
  if (otherNumbers !== '') lastThree = ',' + lastThree;
  const formatted = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
  return `₹${sign}${formatted}`;
};

const DeltaBadge = ({ delta, deltaPct, type = 'count' }) => {
  if (delta === null || delta === undefined) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  if (delta === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-500">
        <Minus className="w-3 h-3" /> No change
      </span>
    );
  }
  const positive = delta > 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  const cls = positive ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40' : 'text-rose-600 bg-rose-50 dark:bg-rose-950/40';
  const value = type === 'value' ? formatINR(Math.abs(delta)) : Math.abs(delta);
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded ${cls}`}>
      <Icon className="w-3 h-3" />
      {value}
      {deltaPct !== null && deltaPct !== undefined ? ` (${deltaPct > 0 ? '+' : ''}${deltaPct}%)` : ''}
    </span>
  );
};

const WonLeadsReport = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [period, setPeriod] = useState('month');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dispatchingDigest, setDispatchingDigest] = useState(false);

  const canDispatchDigest = user?.role === 'super_admin' || user?.is_vyapaar_ops;

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period };
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const res = await api.get('/reports/won-leads', { params });
      setData(res.data);
    } catch (e) {
      toast.error('Failed to load Won Leads report');
    } finally {
      setLoading(false);
    }
  }, [period, startDate, endDate]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const triggerMonthlyDigest = async () => {
    setDispatchingDigest(true);
    try {
      const res = await api.post('/admin/dispatch-monthly-digest?force=true');
      toast.success(`Digest sent to ${res.data.sent}/${res.data.recipients || 0} recipients (${res.data.last_count} deals · ${res.data.prior_count} prior)`);
    } catch (e) {
      const msg = e.response?.data?.detail || 'Digest dispatch failed';
      toast.error(msg);
    } finally {
      setDispatchingDigest(false);
    }
  };

  const buckets = data?.buckets || [];
  const summary = data?.summary || { total_won: 0, total_value: 0, bucket_count: 0 };

  return (
    <div className="space-y-6 p-1" data-testid="won-leads-report">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-950/40 dark:to-teal-950/40">
              <Trophy className="w-6 h-6 text-emerald-700 dark:text-emerald-300" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Won Leads Report</h1>
              <p className="text-sm text-muted-foreground mt-0.5">Deals closed by month, quarter, or fiscal year (Apr–Mar)</p>
            </div>
          </div>
        </div>
        {canDispatchDigest && (
          <Button
            onClick={triggerMonthlyDigest}
            disabled={dispatchingDigest}
            data-testid="dispatch-monthly-digest-btn"
            className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white"
          >
            {dispatchingDigest ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
            Send Monthly Digest Now
          </Button>
        )}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <div className="flex-1">
              <p className="text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wider">Period</p>
              <Tabs value={period} onValueChange={setPeriod} data-testid="period-tabs">
                <TabsList className="grid grid-cols-3 w-full max-w-md">
                  <TabsTrigger value="month" data-testid="period-month">Monthly</TabsTrigger>
                  <TabsTrigger value="quarter" data-testid="period-quarter">Quarterly</TabsTrigger>
                  <TabsTrigger value="annual" data-testid="period-annual">Annual (FY)</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:max-w-md">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wider">From</p>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  data-testid="start-date-filter"
                />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wider">To</p>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  data-testid="end-date-filter"
                />
              </div>
            </div>
            {(startDate || endDate) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setStartDate(''); setEndDate(''); }}
                data-testid="clear-filters-btn"
              >
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* KPI Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border-emerald-200 dark:border-emerald-900">
          <CardContent className="py-5">
            <p className="text-xs font-medium uppercase tracking-wider text-emerald-700 dark:text-emerald-300">Total Deals Won</p>
            <p className="text-3xl font-bold text-emerald-900 dark:text-emerald-100 mt-1" data-testid="kpi-total-won">{summary.total_won}</p>
            <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">{summary.bucket_count} {period === 'month' ? 'months' : period === 'quarter' ? 'quarters' : 'fiscal years'}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/30 dark:to-indigo-950/30 border-violet-200 dark:border-violet-900">
          <CardContent className="py-5">
            <p className="text-xs font-medium uppercase tracking-wider text-violet-700 dark:text-violet-300">Total Revenue</p>
            <p className="text-3xl font-bold text-violet-900 dark:text-violet-100 mt-1" data-testid="kpi-total-value">{formatINR(summary.total_value)}</p>
            <p className="text-xs text-violet-600 dark:text-violet-400 mt-1">Aggregate deal value</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30 border-amber-200 dark:border-amber-900">
          <CardContent className="py-5">
            <p className="text-xs font-medium uppercase tracking-wider text-amber-700 dark:text-amber-300">Avg Deal Value</p>
            <p className="text-3xl font-bold text-amber-900 dark:text-amber-100 mt-1" data-testid="kpi-avg-deal">
              {summary.total_won > 0 ? formatINR(summary.total_value / summary.total_won) : '₹0'}
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">Per closed deal</p>
          </CardContent>
        </Card>
      </div>

      {/* Buckets */}
      {loading ? (
        <Card><CardContent className="py-12 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></CardContent></Card>
      ) : buckets.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Trophy className="w-12 h-12 mx-auto text-muted-foreground/40 mb-3" />
            <p className="text-muted-foreground">No won deals in this period.</p>
            <p className="text-xs text-muted-foreground/60 mt-1">Try adjusting the date filters or switch period.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {buckets.slice().reverse().map((b) => (
            <Card key={b.key} data-testid={`bucket-${b.key}`} className="overflow-hidden">
              <CardHeader className="pb-3 bg-muted/40">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-violet-600" />
                      {b.label}
                    </CardTitle>
                    {b.prev_label && (
                      <CardDescription className="mt-1">vs {b.prev_label}</CardDescription>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Deals</p>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-bold">{b.won_count}</span>
                        <DeltaBadge delta={b.delta_count} deltaPct={b.delta_pct} />
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Revenue</p>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{formatINR(b.total_value)}</span>
                        <DeltaBadge delta={b.delta_value} type="value" />
                      </div>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="space-y-2">
                  {b.leads.slice().sort((a, c) => c.deal_value - a.deal_value).map((l) => (
                    <div
                      key={l.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => navigate(`/leads/${l.id}`)}
                      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/leads/${l.id}`); }}
                      className="flex items-center justify-between gap-3 p-3 rounded-lg border bg-card hover:bg-accent hover:border-violet-300 dark:hover:border-violet-700 transition-colors cursor-pointer"
                      data-testid={`won-lead-${l.id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{l.title}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground truncate">
                            {l.customer_company || l.customer_name}
                          </span>
                          {l.primary_category_name && (
                            <Badge variant="outline" className="text-[10px] py-0 h-4">{l.primary_category_name}</Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300 flex items-center justify-end">
                          <IndianRupee className="w-3 h-3" />
                          {formatINR(l.deal_value).replace('₹', '')}
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">Closed {l.closure_date || '—'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default WonLeadsReport;
