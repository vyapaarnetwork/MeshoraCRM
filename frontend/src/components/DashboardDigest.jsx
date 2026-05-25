import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  AlarmClock, Snowflake, MessageCircle, ListChecks, Flame, AlertTriangle, ArrowRight,
} from 'lucide-react';
import api from '../utils/api';

const Tile = ({ icon: Icon, label, value, accent = 'violet', onClick, testId, subtitle }) => {
  const accentMap = {
    violet: 'from-violet-500 to-indigo-500 text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40',
    amber: 'from-amber-500 to-orange-500 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40',
    rose: 'from-rose-500 to-pink-500 text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40',
    sky: 'from-sky-500 to-cyan-500 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/40',
    emerald: 'from-emerald-500 to-teal-500 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40',
    slate: 'from-slate-400 to-slate-500 text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/40',
  };
  const cls = accentMap[accent] || accentMap.violet;
  const clickable = !!onClick;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      className={`text-left rounded-xl border p-4 transition-all ${cls} ${clickable ? 'hover:shadow-md cursor-pointer hover:-translate-y-0.5' : ''}`}
      data-testid={testId}
    >
      <div className="flex items-start justify-between mb-2">
        <Icon className="w-5 h-5" />
        {clickable && <ArrowRight className="w-3.5 h-3.5 opacity-50" />}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
      {subtitle && <div className="text-[11px] mt-1 opacity-60">{subtitle}</div>}
    </button>
  );
};

const DashboardDigest = () => {
  const navigate = useNavigate();
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/dashboard/digest')
      .then((r) => setDigest(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card data-testid="dashboard-digest-loading">
        <CardContent className="pt-6">
          <div className="h-24 bg-muted animate-pulse rounded-md" />
        </CardContent>
      </Card>
    );
  }

  if (!digest) return null;

  const { leads, follow_ups, mentions, tasks } = digest;
  const hasUrgent =
    follow_ups.overdue > 0 || leads.at_risk > 0 || mentions.unread > 0 || tasks.overdue > 0;

  return (
    <Card data-testid="dashboard-digest">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Flame className="w-5 h-5 text-violet-600" />
              Your daily pulse
            </h2>
            <p className="text-xs text-muted-foreground">
              {hasUrgent
                ? `${follow_ups.overdue + leads.at_risk + mentions.unread + tasks.overdue} item(s) need your attention today.`
                : 'All caught up — nice work.'}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tile
            icon={AlarmClock}
            label="Overdue Follow-ups"
            value={follow_ups.overdue}
            accent={follow_ups.overdue > 0 ? 'rose' : 'slate'}
            onClick={() => navigate('/leads')}
            testId="digest-overdue-followups"
            subtitle={follow_ups.today > 0 ? `${follow_ups.today} due today` : null}
          />
          <Tile
            icon={AlertTriangle}
            label="At-Risk Leads"
            value={leads.at_risk}
            accent={leads.at_risk > 0 ? 'amber' : 'slate'}
            onClick={() => navigate('/leads')}
            testId="digest-at-risk"
            subtitle={leads.gone_cold_this_week > 0 ? `${leads.gone_cold_this_week} went cold this week` : null}
          />
          <Tile
            icon={MessageCircle}
            label="Unread Mentions"
            value={mentions.unread}
            accent={mentions.unread > 0 ? 'violet' : 'slate'}
            onClick={() => navigate('/notifications')}
            testId="digest-mentions"
          />
          <Tile
            icon={ListChecks}
            label="My Open Tasks"
            value={tasks.open}
            accent={tasks.overdue > 0 ? 'rose' : tasks.open > 0 ? 'sky' : 'slate'}
            testId="digest-tasks"
            subtitle={tasks.overdue > 0 ? `${tasks.overdue} overdue` : null}
          />
        </div>

        {/* Health distribution mini-bar */}
        {leads.total > 0 && (
          <div className="mt-4 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Lead health distribution</span>
              <span className="text-muted-foreground">{leads.total} total</span>
            </div>
            <div className="flex h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800">
              {leads.hot > 0 && (
                <div className="bg-gradient-to-r from-red-500 to-orange-500" style={{ width: `${(leads.hot / leads.total) * 100}%` }} title={`${leads.hot} hot`} />
              )}
              {leads.warm > 0 && (
                <div className="bg-gradient-to-r from-amber-400 to-yellow-400" style={{ width: `${(leads.warm / leads.total) * 100}%` }} title={`${leads.warm} warm`} />
              )}
              {leads.cold > 0 && (
                <div className="bg-gradient-to-r from-sky-400 to-blue-400" style={{ width: `${(leads.cold / leads.total) * 100}%` }} title={`${leads.cold} cold`} />
              )}
              {leads.at_risk > 0 && (
                <div className="bg-gradient-to-r from-rose-500 to-pink-500" style={{ width: `${(leads.at_risk / leads.total) * 100}%` }} title={`${leads.at_risk} at risk`} />
              )}
            </div>
            <div className="flex flex-wrap gap-3 text-[10px] uppercase tracking-wider text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Hot {leads.hot}</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /> Warm {leads.warm}</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sky-400" /> Cold {leads.cold}</span>
              <span className="flex items-center gap-1 text-rose-600 dark:text-rose-400"><span className="w-2 h-2 rounded-full bg-rose-500" /> At Risk {leads.at_risk}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DashboardDigest;
