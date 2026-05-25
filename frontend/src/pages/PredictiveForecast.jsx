import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  TrendingUp, TrendingDown, Minus, Sparkles, RefreshCw, Activity, Calendar,
  Target, Wallet, Clock, Zap, AlertCircle,
} from 'lucide-react';
import {
  ComposedChart, Bar, Line, Area, AreaChart, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';
import FeatureInfo from '../components/FeatureInfo';

const PredictiveForecast = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState(6);
  const [refreshing, setRefreshing] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/dashboard/predictive-forecast?horizon_months=${horizon}`);
      setData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load forecast');
    } finally { setLoading(false); }
  }, [horizon]);

  useEffect(() => { load(); }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
    toast.success('Forecast refreshed');
  };

  if (loading) return <ForecastSkeleton />;
  if (!data) return null;

  const { history, forecast, closure_predictions_next_90d, summary, ai_narrative } = data;

  // Merge history + forecast into a single timeline series for the chart
  const chartData = [
    ...history.map((h) => ({
      month: h.month,
      actual: h.won_revenue,
      forecast: null,
      low: null,
      high: null,
    })),
    ...forecast.map((f) => ({
      month: f.month,
      actual: null,
      forecast: f.combined,
      low: f.low,
      high: f.high,
    })),
  ];

  const TrendIcon = summary.trend_direction === 'up' ? TrendingUp
    : summary.trend_direction === 'down' ? TrendingDown : Minus;
  const trendColor = summary.trend_direction === 'up' ? 'text-emerald-600'
    : summary.trend_direction === 'down' ? 'text-rose-600' : 'text-slate-500';

  return (
    <div className="space-y-6" data-testid="predictive-forecast-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-violet-600" />
            Predictive Revenue Forecasting
            <FeatureInfo
              ai
              size="lg"
              title="How the forecast works"
              description="Blends two signals: (1) a statistical baseline (linear regression + EMA on the last 12 months of won revenue) and (2) a pipeline-weighted projection (per-deal probability = stage × health × recency × stage-velocity offset). The combined forecast is the weighted sum (55% pipeline, 45% statistical), with a widening confidence band as horizon grows."
              tip="The AI executive summary at the top is one-click boardroom-ready language explaining your trend, biggest opportunity month, and top risk."
            />
          </h1>
          <p className="text-muted-foreground mt-1">
            Hybrid statistical + pipeline-weighted forecast, with AI-generated executive narrative.
          </p>
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <Select value={String(horizon)} onValueChange={(v) => setHorizon(Number(v))}>
            <SelectTrigger className="w-36 h-9" data-testid="forecast-horizon-select">
              <SelectValue placeholder="Horizon" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="3">Next 3 months</SelectItem>
              <SelectItem value="6">Next 6 months</SelectItem>
              <SelectItem value="9">Next 9 months</SelectItem>
              <SelectItem value="12">Next 12 months</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={refresh} disabled={refreshing} size="sm" data-testid="forecast-refresh-btn">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* AI Narrative banner */}
      {ai_narrative && (
        <Card className="border-violet-200 dark:border-violet-900 bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/40 dark:to-indigo-950/40" data-testid="ai-narrative-card">
          <CardContent className="pt-5">
            <div className="flex items-start gap-3">
              <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white shrink-0">
                <Sparkles className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-semibold mb-1 text-violet-900 dark:text-violet-200">AI Executive Summary</h3>
                <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{ai_narrative}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* KPI strip */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Wallet} label="Total Forecast" value={formatCurrency(summary.total_forecast)} accent="violet" subtitle={`Next ${horizon} months`} testId="kpi-total" />
        <KpiCard icon={Activity} label="Avg / Month" value={formatCurrency(summary.avg_monthly_forecast)} accent="indigo" subtitle={`Historical: ${formatCurrency(summary.avg_historical_monthly)}`} testId="kpi-avg" />
        <KpiCard icon={TrendIcon} iconCls={trendColor} label="Trend (last 3m vs prior 3m)" value={`${summary.mom_change_pct > 0 ? '+' : ''}${summary.mom_change_pct}%`} accent={summary.trend_direction === 'up' ? 'emerald' : summary.trend_direction === 'down' ? 'rose' : 'slate'} subtitle={summary.trend_direction.toUpperCase()} testId="kpi-trend" />
        <KpiCard icon={Target} label="Open Pipeline Weighted" value={formatCurrency(summary.pipeline_weighted_total)} accent="amber" subtitle={`${summary.open_deal_count} open deals`} testId="kpi-pipeline" />
      </div>

      {/* Forecast chart */}
      <Card data-testid="forecast-chart-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-violet-600" />
            Revenue Forecast Timeline
          </CardTitle>
          <CardDescription>
            Solid bars = historical won revenue. Dashed line + shaded band = forecasted combined (statistical + weighted pipeline) with confidence interval.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-96" style={{ minHeight: 360 }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={320} debounce={50}>
            <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis dataKey="month" fontSize={11} interval={0} angle={-25} textAnchor="end" height={60} />
              <YAxis fontSize={11} tickFormatter={(v) => v >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v} />
              <Tooltip formatter={(v) => v != null ? formatCurrency(v) : '—'} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine x={history[history.length - 1]?.month} stroke="#64748B" strokeDasharray="3 3" label={{ value: 'Today', fontSize: 10, fill: '#64748B' }} />
              <Bar dataKey="actual" name="Won (actual)" fill="#10B981" radius={[4, 4, 0, 0]} />
              <Area type="monotone" dataKey="high" name="Confidence band (high)" fill="#A78BFA" fillOpacity={0.18} stroke="none" />
              <Area type="monotone" dataKey="low" name="Confidence band (low)" fill="#ffffff" fillOpacity={1} stroke="none" />
              <Line type="monotone" dataKey="forecast" name="Forecast (combined)" stroke="#8B5CF6" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 4, fill: '#8B5CF6' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Forecast breakdown table */}
      <Card data-testid="forecast-breakdown-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-indigo-600" />
            Month-by-Month Breakdown
          </CardTitle>
          <CardDescription>Statistical baseline vs pipeline-weighted contribution to combined forecast</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <div className="min-w-[640px]">
              {/* header row */}
              <div className="grid grid-cols-5 gap-3 text-xs text-muted-foreground border-b pb-2 mb-1">
                <div className="text-left">Month</div>
                <div className="text-right">Statistical</div>
                <div className="text-right">Pipeline-weighted</div>
                <div className="text-right">Combined</div>
                <div className="text-right">Range (low – high)</div>
              </div>
              {/* data rows */}
              {forecast.map((f) => (
                <div
                  key={f.month_iso}
                  className="grid grid-cols-5 gap-3 text-sm border-b last:border-b-0 hover:bg-muted/40 py-2"
                  data-testid={`forecast-row-${f.month_iso}`}
                >
                  <div className="font-medium">{f.month}</div>
                  <div className="text-right tabular-nums text-muted-foreground">{formatCurrency(f.stat_forecast)}</div>
                  <div className="text-right tabular-nums text-muted-foreground">{formatCurrency(f.pipeline_forecast)}</div>
                  <div className="text-right tabular-nums font-semibold text-violet-700 dark:text-violet-300">{formatCurrency(f.combined)}</div>
                  <div className="text-right text-xs text-muted-foreground tabular-nums">
                    {formatCurrency(f.low)} – {formatCurrency(f.high)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Closure predictions */}
      <Card data-testid="closure-predictions-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            Top Closure Predictions (Next 90 Days)
          </CardTitle>
          <CardDescription>
            Per-deal probability scored from stage, health, and recency. Click a row to open the lead.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {closure_predictions_next_90d.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
              No deals expected to close in the next 90 days.
            </div>
          ) : (
            <div className="space-y-1.5">
              {closure_predictions_next_90d.map((c) => {
                const bandCls = {
                  hot: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
                  warm: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
                  cold: 'bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300',
                  at_risk: 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300',
                }[c.health_band] || 'bg-slate-100 text-slate-700';
                return (
                  <button
                    key={c.lead_id}
                    type="button"
                    onClick={() => navigate(`/leads/${c.lead_id}`)}
                    className="w-full text-left p-2.5 rounded-md border hover:bg-accent transition-colors flex items-center gap-3"
                    data-testid={`closure-row-${c.lead_id}`}
                  >
                    <div className="shrink-0 w-12 h-12 rounded-md bg-gradient-to-br from-violet-100 to-indigo-100 dark:from-violet-950/40 dark:to-indigo-950/40 flex flex-col items-center justify-center">
                      <div className="text-xs font-bold text-violet-700 dark:text-violet-300 tabular-nums">{c.probability}%</div>
                      <div className="text-[9px] text-muted-foreground uppercase">prob</div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium truncate">{c.title || c.customer_company}</span>
                        <Badge className={`text-[10px] ${bandCls}`}>{c.health_band}</Badge>
                        <Badge variant="outline" className="text-[10px]">{c.stage}</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground flex flex-wrap gap-3 mt-0.5">
                        <span>💼 {c.customer_company || '—'}</span>
                        <span><Clock className="inline w-3 h-3 mr-0.5" />Close in {c.days_to_close}d</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold tabular-nums">{formatCurrency(c.expected_revenue)}</div>
                      <div className="text-[10px] text-muted-foreground">of {formatCurrency(c.deal_value)}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const KpiCard = ({ icon: Icon, iconCls, label, value, subtitle, accent = 'violet', testId }) => {
  const cls = {
    violet: 'bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300',
    indigo: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300',
    emerald: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
    sky: 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
    rose: 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
    slate: 'bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300',
  }[accent] || 'bg-violet-50 text-violet-700';
  return (
    <Card data-testid={testId} className={cls}>
      <CardContent className="pt-5">
        <Icon className={`w-5 h-5 mb-1.5 ${iconCls || ''}`} />
        <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {subtitle && <div className="text-[11px] opacity-60 mt-0.5">{subtitle}</div>}
      </CardContent>
    </Card>
  );
};

const ForecastSkeleton = () => (
  <div className="space-y-6">
    <Skeleton className="h-10 w-80" />
    <Skeleton className="h-24 w-full rounded-xl" />
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
    </div>
    <Skeleton className="h-96 w-full rounded-xl" />
  </div>
);

export default PredictiveForecast;
