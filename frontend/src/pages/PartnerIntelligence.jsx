import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  Trophy, Users, TrendingUp, Sparkles, Loader2, Target, Activity, Zap, RefreshCw,
  Star, AlertTriangle, GraduationCap, ChevronRight,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';

const PartnerIntelligence = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [coachingPartnerId, setCoachingPartnerId] = useState(null);
  const [coachingData, setCoachingData] = useState(null);
  const [coachingLoading, setCoachingLoading] = useState(false);
  const navigate = useNavigate();

  const fetch = async () => {
    setLoading(true);
    try {
      const r = await api.get('/dashboard/partner-intelligence');
      setData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load partner intelligence');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetch(); }, []);

  const openCoaching = async (partnerId) => {
    setCoachingPartnerId(partnerId);
    setCoachingData(null);
    setCoachingLoading(true);
    try {
      const r = await api.post(`/partners/${partnerId}/ai/coaching`);
      setCoachingData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Coaching analysis failed');
      setCoachingPartnerId(null);
    } finally { setCoachingLoading(false); }
  };

  if (loading) return <PartnerIntelligenceSkeleton />;
  if (!data) return null;

  const { kpis, leaderboard, top_categories } = data;

  return (
    <div className="space-y-6" data-testid="partner-intelligence-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <Trophy className="w-7 h-7 text-amber-500" />
            Partner Intelligence
          </h1>
          <p className="text-muted-foreground mt-1">
            Ranked performance + AI coaching for your selling partner network.
          </p>
        </div>
        <Button variant="outline" onClick={fetch} size="sm" data-testid="pi-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-1.5" />Refresh
        </Button>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Users} label="Total Partners" value={kpis.total_partners} accent="violet" testId="pi-kpi-total" />
        <KpiCard icon={Activity} label="Active" value={kpis.active_partners} accent="emerald" subtitle="With ≥1 deal" testId="pi-kpi-active" />
        <KpiCard icon={Trophy} label="Total Won Revenue" value={formatCurrency(kpis.total_won_revenue)} accent="amber" testId="pi-kpi-revenue" />
        <KpiCard icon={Target} label="Avg Win Rate" value={`${kpis.avg_win_rate}%`} accent="sky" testId="pi-kpi-winrate" />
      </div>

      <Card data-testid="pi-leaderboard-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500" />
            Leaderboard
          </CardTitle>
          <CardDescription>
            Composite score = 40% revenue + 30% win-rate + 20% engagement + 10% speed. Click a partner for AI coaching.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {leaderboard.length === 0 ? (
            <p className="text-center text-muted-foreground text-sm py-6">No partner data yet</p>
          ) : (
            <div className="space-y-2">
              {leaderboard.map((p, i) => {
                const topCats = top_categories[p.partner_id] || [];
                return (
                  <div key={p.partner_id} className="rounded-lg border p-3 hover:shadow-sm transition-shadow" data-testid={`partner-row-${p.partner_id}`}>
                    <div className="flex items-center gap-3">
                      <div className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white ${
                        i === 0 ? 'bg-gradient-to-br from-amber-400 to-orange-500' :
                        i === 1 ? 'bg-gradient-to-br from-slate-400 to-slate-500' :
                        i === 2 ? 'bg-gradient-to-br from-orange-300 to-amber-600' :
                        'bg-gradient-to-br from-violet-500 to-indigo-500'
                      }`}>
                        {i + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{p.partner_name}</span>
                          {p.company_name && <Badge variant="outline" className="text-xs">{p.company_name}</Badge>}
                          <Badge className="text-xs bg-gradient-to-r from-violet-100 to-indigo-100 dark:from-violet-950/40 dark:to-indigo-950/40 text-violet-700 dark:text-violet-300">
                            <Zap className="w-3 h-3 mr-1" /> Score {p.composite_score}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                          <span>📊 {p.assigned} assigned · {p.won} won · {p.lost} lost</span>
                          <span>🎯 {p.win_rate}% win rate</span>
                          <span>💰 {formatCurrency(p.won_revenue)} earned</span>
                          <span>📈 {formatCurrency(p.open_pipeline)} open</span>
                          {p.avg_cycle_days && <span>⏱️ {p.avg_cycle_days}d cycle</span>}
                        </div>
                        {topCats.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {topCats.slice(0, 4).map((c) => (
                              <Badge key={c.category} variant="secondary" className="text-[10px]">
                                {c.category} × {c.won_count}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <Button size="sm" variant="outline" onClick={() => openCoaching(p.partner_id)} data-testid={`coach-btn-${p.partner_id}`}>
                        <Sparkles className="w-3.5 h-3.5 mr-1.5 text-violet-600" />
                        AI Coach
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <CoachingDialog
        open={!!coachingPartnerId}
        onOpenChange={(o) => { if (!o) { setCoachingPartnerId(null); setCoachingData(null); } }}
        loading={coachingLoading}
        data={coachingData}
        onOpenLead={(id) => { setCoachingPartnerId(null); navigate(`/leads/${id}`); }}
      />
    </div>
  );
};

const KpiCard = ({ icon: Icon, label, value, accent = 'violet', subtitle, testId }) => {
  const cls = {
    violet: 'bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300',
    indigo: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300',
    emerald: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
    sky: 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
    rose: 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  }[accent];
  return (
    <Card data-testid={testId} className={cls}>
      <CardContent className="pt-5">
        <Icon className="w-5 h-5 mb-1.5" />
        <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {subtitle && <div className="text-[11px] opacity-60 mt-0.5">{subtitle}</div>}
      </CardContent>
    </Card>
  );
};

const CoachingDialog = ({ open, onOpenChange, loading, data, onOpenLead }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
            <GraduationCap className="w-4 h-4" />
          </span>
          AI Coaching · {data?.partner?.name || '…'}
        </DialogTitle>
        <DialogDescription>
          Personalized strengths, weaknesses, and next-step coaching tips based on historical performance.
        </DialogDescription>
      </DialogHeader>

      {loading && (
        <div className="py-10 flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-violet-600" />
          <p className="text-sm text-muted-foreground">Analyzing partner performance…</p>
        </div>
      )}

      {!loading && data && (
        <div className="space-y-4" data-testid="ai-coaching-result">
          <div className="rounded-lg bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/40 dark:to-indigo-950/40 border border-violet-200 dark:border-violet-900 p-3">
            <p className="text-sm leading-relaxed">{data.summary}</p>
            <div className="flex flex-wrap gap-2 mt-2 text-xs">
              <Badge variant="outline">{data.stats.won} won</Badge>
              <Badge variant="outline">{data.stats.lost} lost</Badge>
              <Badge variant="outline">{data.stats.open} open</Badge>
              <Badge variant="outline">{data.stats.win_rate}% win rate</Badge>
              <Badge variant="outline">Confidence {data.confidence}%</Badge>
            </div>
          </div>

          {data.strengths?.length > 0 && (
            <Section title="Strengths" icon={Star} iconCls="text-emerald-600">
              <ul className="space-y-1 text-sm">
                {data.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2"><span className="text-emerald-600 font-bold">+</span>{s}</li>
                ))}
              </ul>
            </Section>
          )}

          {data.weaknesses?.length > 0 && (
            <Section title="Weaknesses" icon={AlertTriangle} iconCls="text-amber-600">
              <ul className="space-y-1 text-sm">
                {data.weaknesses.map((s, i) => (
                  <li key={i} className="flex items-start gap-2"><span className="text-amber-600 font-bold">!</span>{s}</li>
                ))}
              </ul>
            </Section>
          )}

          {data.coaching_tips?.length > 0 && (
            <Section title="Coaching tips" icon={GraduationCap} iconCls="text-violet-600">
              <ol className="space-y-1.5 text-sm">
                {data.coaching_tips.map((t, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-violet-600 font-bold">{i + 1}.</span>{t}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {data.leads_to_focus?.length > 0 && (
            <Section title="Leads to focus on" icon={Target} iconCls="text-sky-600">
              <div className="space-y-1.5">
                {data.leads_to_focus.map((l, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => onOpenLead(l.lead_id)}
                    className="w-full text-left p-2 rounded-md hover:bg-accent flex items-start gap-2 text-sm"
                    data-testid={`focus-lead-${i}`}
                  >
                    <ChevronRight className="w-3.5 h-3.5 mt-0.5 text-sky-600 shrink-0" />
                    <div className="flex-1">
                      <div className="font-medium">{l.title}</div>
                      <div className="text-xs text-muted-foreground">{l.why_focus}</div>
                    </div>
                  </button>
                ))}
              </div>
            </Section>
          )}

          {data.next_training_topic && (
            <div className="rounded-lg border border-dashed p-3 text-sm flex items-start gap-2">
              <GraduationCap className="w-4 h-4 mt-0.5 text-violet-600" />
              <div>
                <span className="font-medium">Recommended training topic: </span>
                <span className="text-muted-foreground">{data.next_training_topic}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </DialogContent>
  </Dialog>
);

const Section = ({ icon: Icon, iconCls, title, children }) => (
  <div className="space-y-1.5">
    <h4 className="text-sm font-semibold flex items-center gap-1.5">
      <Icon className={`w-4 h-4 ${iconCls}`} />
      {title}
    </h4>
    {children}
  </div>
);

const PartnerIntelligenceSkeleton = () => (
  <div className="space-y-6">
    <Skeleton className="h-10 w-80" />
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
    </div>
    <Skeleton className="h-96 w-full rounded-xl" />
  </div>
);

export default PartnerIntelligence;
