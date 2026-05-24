import { useEffect, useState, useCallback } from 'react';
import api, { formatCurrency } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, AreaChart, Area, PieChart as RechartsPieChart, Pie, Cell
} from 'recharts';
import { TrendingUp, DollarSign, Repeat, Activity as ActivityIcon, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const COLORS = ['#4169E1', '#10B981', '#F59E0B', '#DC143C', '#8B5CF6'];

const CommercialsAnalytics = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState(12);
  const [scanning, setScanning] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/commercials/analytics?months=${months}`);
      setData(res.data);
    } catch (e) {
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [months]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runRenewalScan = async () => {
    setScanning(true);
    try {
      const res = await api.post('/commercials/run-renewal-scan');
      const { created, flagged } = res.data;
      if (created > 0) toast.success(`${created} renewal lead(s) auto-created`);
      else if (flagged > 0) toast.info(`${flagged} contract(s) flagged for renewal`);
      else toast.info('No contracts in renewal window');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Renewal scan failed');
    } finally {
      setScanning(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  const { series, forecast_90d, revenue_mix, current } = data;
  const mixData = [
    { name: 'Recurring', value: revenue_mix.recurring },
    { name: 'One-Time', value: revenue_mix.one_time },
  ].filter(d => d.value > 0);

  return (
    <div className="space-y-6" data-testid="commercials-analytics-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Revenue Analytics</h1>
          <p className="text-sm text-muted-foreground">MRR/ARR trends, churn, and forecast across all commercials.</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="text-xs uppercase tracking-wider text-muted-foreground">Window</label>
            <Select value={String(months)} onValueChange={(v) => setMonths(Number(v))}>
              <SelectTrigger className="w-32" data-testid="analytics-window-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="6">6 months</SelectItem>
                <SelectItem value="12">12 months</SelectItem>
                <SelectItem value="24">24 months</SelectItem>
                <SelectItem value="36">36 months</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={runRenewalScan} disabled={scanning} data-testid="run-renewal-scan-btn">
            <RefreshCw className={`w-4 h-4 mr-2 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning…' : 'Run renewal scan'}
          </Button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid gap-4 md:grid-cols-4 stagger-children">
        <KPI icon={TrendingUp} label="Current MRR" value={formatCurrency(current.mrr)} sub={`ARR ${formatCurrency(current.arr)}`} />
        <KPI icon={Repeat} label="Active contracts" value={current.active_contracts} />
        <KPI icon={ActivityIcon} label="Churn (this month)" value={`${current.churn_rate_pct}%`} accent={current.churn_rate_pct > 5 ? 'text-red-600 dark:text-red-400' : ''} />
        <KPI icon={DollarSign} label="90-day forecast" value={formatCurrency(forecast_90d.total)} sub="invoices + billings + milestones" />
      </div>

      {/* MRR / ARR trend */}
      <Card data-testid="mrr-trend-chart">
        <CardHeader>
          <CardTitle>MRR & ARR trend</CardTitle>
          <CardDescription>Monthly recurring revenue and annualized run-rate.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-72">
            <ResponsiveContainer>
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="mrrFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4169E1" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#4169E1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v, k) => [formatCurrency(v), k.toUpperCase()]} />
                <Legend />
                <Area type="monotone" dataKey="mrr" stroke="#4169E1" fill="url(#mrrFill)" strokeWidth={2} name="MRR" />
                <Line type="monotone" dataKey="arr" stroke="#10B981" strokeWidth={1.5} dot={false} name="ARR" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Contracts: New vs Churned */}
        <Card data-testid="contracts-flow-chart">
          <CardHeader>
            <CardTitle>Contract flow</CardTitle>
            <CardDescription>New vs churned contracts per month.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="new_contracts" fill="#10B981" name="New" radius={[4,4,0,0]} />
                  <Bar dataKey="churned_contracts" fill="#DC143C" name="Churned" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Revenue mix */}
        <Card data-testid="revenue-mix-chart">
          <CardHeader>
            <CardTitle>Revenue mix (lifetime)</CardTitle>
            <CardDescription>Recurring vs one-time payments received.</CardDescription>
          </CardHeader>
          <CardContent>
            {mixData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">No payments recorded yet.</div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer>
                  <RechartsPieChart>
                    <Pie data={mixData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }) => `${name}: ${formatCurrency(value)}`}>
                      {mixData.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => formatCurrency(v)} />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Revenue collected vs invoiced */}
      <Card data-testid="collection-chart">
        <CardHeader>
          <CardTitle>Revenue collected vs invoiced</CardTitle>
          <CardDescription>Payments received against invoices raised per month.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={series}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => formatCurrency(v)} />
                <Legend />
                <Bar dataKey="invoices_raised" fill="#F59E0B" name="Invoiced" radius={[4,4,0,0]} />
                <Bar dataKey="revenue_collected" fill="#10B981" name="Collected" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* 90-day forecast breakdown */}
      <Card data-testid="forecast-breakdown">
        <CardHeader>
          <CardTitle>90-day revenue forecast</CardTitle>
          <CardDescription>Expected cash inflow within the next 90 days.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <ForecastItem label="Pending invoices (outstanding)" value={forecast_90d.pending_invoices} color="#F59E0B" />
            <ForecastItem label="Recurring billings (scheduled)" value={forecast_90d.recurring_billings} color="#4169E1" />
            <ForecastItem label="Project milestones (upcoming)" value={forecast_90d.project_milestones} color="#10B981" />
          </div>
          <div className="mt-4 p-4 rounded-md bg-primary/5 border border-primary/20 text-sm">
            <strong>Total expected inflow:</strong> {formatCurrency(forecast_90d.total)} over the next 90 days.
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const KPI = ({ icon: Icon, label, value, sub, accent = '' }) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">{label}</CardTitle>
      <Icon className="w-4 h-4 text-primary" />
    </CardHeader>
    <CardContent>
      <div className={`text-2xl font-bold ${accent}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </CardContent>
  </Card>
);

const ForecastItem = ({ label, value, color }) => (
  <div className="p-3 rounded-md border" style={{ borderLeft: `3px solid ${color}` }}>
    <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
    <div className="text-lg font-semibold mt-1">{formatCurrency(value)}</div>
  </div>
);

export default CommercialsAnalytics;
