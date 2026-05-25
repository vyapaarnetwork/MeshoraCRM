import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend, Area, AreaChart,
} from 'recharts';
import {
  TrendingUp, Wallet, Trophy, Target, AlertTriangle, DollarSign,
  Activity, Briefcase, Repeat, CalendarRange, Sparkles,
} from 'lucide-react';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const BAND_COLORS = {
  hot: '#EF4444',
  warm: '#F59E0B',
  cold: '#0EA5E9',
  at_risk: '#E11D48',
};

const RevenueIntelligence = () => {
  const { isAdmin, isVyapaarOps } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [runningRules, setRunningRules] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      const res = await api.get(`/dashboard/revenue-intelligence?${params.toString()}`);
      setData(res.data);
    } catch (e) { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetch(); /* eslint-disable-next-line */ }, []);

  if (loading) return <RevenueIntelligenceSkeleton />;
  if (!data) return null;

  const { kpis, pipeline_by_stage, top_partners, forecast, win_rate_trend, health_value_distribution } = data;

  return (
    <div className="space-y-6" data-testid="revenue-intelligence-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <TrendingUp className="w-7 h-7 text-violet-600" />
            Revenue Intelligence
          </h1>
          <p className="text-muted-foreground mt-1">
            Boardroom-ready view of pipeline, forecasted revenue, win rates, and partner performance.
          </p>
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <div className="space-y-1">
            <Label className="text-xs">From</Label>
            <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-9 w-36" data-testid="ri-start-date" />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">To</Label>
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-9 w-36" data-testid="ri-end-date" />
          </div>
          <Button onClick={fetch} className="h-9" data-testid="ri-apply-btn">Apply</Button>
          {(isAdmin || isVyapaarOps) && (
            <Button
              variant="outline"
              className="h-9"
              disabled={runningRules}
              data-testid="ri-run-rules-btn"
              onClick={async () => {
                setRunningRules(true);
                try {
                  const r = await api.post('/notifications/run-rules');
                  toast.success(`Smart rules fired ${r.data.fired_count} notification(s)`);
                } catch (e) {
                  toast.error(e.response?.data?.detail || 'Run rules failed');
                } finally {
                  setRunningRules(false);
                }
              }}
            >
              <Sparkles className="w-4 h-4 mr-1.5" />
              {runningRules ? 'Running…' : 'Run Smart Rules'}
            </Button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Wallet} label="Total Pipeline" value={formatCurrency(kpis.total_pipeline)} accent="violet" subtitle={`${kpis.total_leads} leads`} testId="kpi-pipeline" />
        <KpiCard icon={Target} label="Weighted Pipeline" value={formatCurrency(kpis.weighted_pipeline)} accent="indigo" subtitle="Probability-adjusted" testId="kpi-weighted" />
        <KpiCard icon={Trophy} label="Won Revenue" value={formatCurrency(kpis.won_value)} accent="emerald" subtitle={`${kpis.won_count} deals · avg ${formatCurrency(kpis.avg_deal_size)}`} testId="kpi-won" />
        <KpiCard icon={Activity} label="Win Rate" value={`${kpis.win_rate}%`} accent="sky" subtitle="Won ÷ closed" testId="kpi-win-rate" />
        <KpiCard icon={Repeat} label="MRR" value={formatCurrency(kpis.mrr)} accent="violet" subtitle="Monthly recurring" testId="kpi-mrr" />
        <KpiCard icon={DollarSign} label="ARR" value={formatCurrency(kpis.arr)} accent="indigo" subtitle="Annualized recurring" testId="kpi-arr" />
        <KpiCard icon={AlertTriangle} label="At-Risk Pipeline" value={formatCurrency(kpis.at_risk_value)} accent="rose" subtitle="Action needed" testId="kpi-at-risk" />
        <KpiCard icon={Briefcase} label="Avg Deal Size" value={formatCurrency(kpis.avg_deal_size)} accent="amber" subtitle="Won deals only" testId="kpi-avg" />
      </div>

      {/* Pipeline by stage + Health value distribution */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="ri-stage-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-violet-600" />
              Pipeline by Stage
            </CardTitle>
            <CardDescription>Total deal value and weighted (probability-adjusted) value per stage</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {pipeline_by_stage.length === 0 ? (
              <EmptyState text="No pipeline data" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pipeline_by_stage} margin={{ top: 5, right: 16, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="stage" fontSize={11} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis fontSize={11} tickFormatter={(v) => v >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v} />
                  <Tooltip formatter={(v) => formatCurrency(v)} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="total_value" name="Total" fill="#A78BFA" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="weighted_value" name="Weighted" fill="#6366F1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card data-testid="ri-health-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-rose-600" />
              Pipeline Value by Health
            </CardTitle>
            <CardDescription>Where your money is sitting — hot, warm, cold, or at-risk</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {health_value_distribution.every(b => b.value === 0) ? (
              <EmptyState text="No health data yet" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={health_value_distribution.filter(b => b.value > 0)}
                    dataKey="value"
                    nameKey="band"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={(e) => `${e.band} · ${formatCurrency(e.value)}`}
                    labelLine={false}
                  >
                    {health_value_distribution.map((b) => (
                      <Cell key={b.band} fill={BAND_COLORS[b.band] || '#8B5CF6'} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => formatCurrency(v)} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Win rate trend + Forecast */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="ri-trend-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-sky-600" />
              Win Rate Trend
            </CardTitle>
            <CardDescription>Closed-won % over the last 6 months</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={win_rate_trend} margin={{ top: 5, right: 16, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="month" fontSize={11} />
                <YAxis fontSize={11} unit="%" />
                <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="win_rate" stroke="#0EA5E9" strokeWidth={2.5} dot={{ r: 4 }} name="Win %" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card data-testid="ri-forecast-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-600" />
              Revenue Forecast
            </CardTitle>
            <CardDescription>Expected close based on weighted pipeline (next 3 months)</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={forecast} margin={{ top: 5, right: 16, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="month" fontSize={11} />
                <YAxis fontSize={11} tickFormatter={(v) => v >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v} />
                <Tooltip formatter={(v) => formatCurrency(v)} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="forecasted" stroke="#8B5CF6" strokeWidth={2.5} fillOpacity={1} fill="url(#forecastGrad)" name="Forecast" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Top partners */}
      <Card data-testid="ri-partners-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500" />
            Top Selling Partners
          </CardTitle>
          <CardDescription>Ranked by won revenue. Conversion = won deals ÷ assigned deals</CardDescription>
        </CardHeader>
        <CardContent>
          {top_partners.length === 0 ? (
            <EmptyState text="No partner data yet" />
          ) : (
            <div className="space-y-2">
              {top_partners.map((p, i) => {
                const conv = p.deal_count > 0 ? (p.won_count / p.deal_count) * 100 : 0;
                return (
                  <div key={p.partner_id || `u-${i}`} className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/40">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-white flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{p.partner_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {p.won_count} won / {p.deal_count} total · {conv.toFixed(0)}% conversion
                      </div>
                    </div>
                    <Badge className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                      {formatCurrency(p.won_revenue)}
                    </Badge>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const KpiCard = ({ icon: Icon, label, value, subtitle, accent = 'violet', testId }) => {
  const cls = {
    violet: 'from-violet-500 to-indigo-500 bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300',
    indigo: 'from-indigo-500 to-blue-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300',
    emerald: 'from-emerald-500 to-teal-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
    sky: 'from-sky-500 to-cyan-500 bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300',
    amber: 'from-amber-500 to-orange-500 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
    rose: 'from-rose-500 to-pink-500 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  }[accent] || 'bg-violet-50 text-violet-700';
  return (
    <Card data-testid={testId} className={cls.split(' ').slice(2).join(' ')}>
      <CardContent className="pt-5">
        <Icon className="w-5 h-5 mb-1.5" />
        <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {subtitle && <div className="text-[11px] opacity-60 mt-0.5">{subtitle}</div>}
      </CardContent>
    </Card>
  );
};

const EmptyState = ({ text }) => (
  <div className="h-full flex items-center justify-center text-muted-foreground text-sm">{text}</div>
);

const RevenueIntelligenceSkeleton = () => (
  <div className="space-y-6">
    <Skeleton className="h-10 w-72" />
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      <Skeleton className="h-80 w-full rounded-xl" />
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  </div>
);

export default RevenueIntelligence;
