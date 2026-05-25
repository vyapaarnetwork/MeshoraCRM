import { Flame, Sun, Snowflake, AlertTriangle } from 'lucide-react';

const BAND_CONFIG = {
  hot: {
    label: 'Hot',
    icon: Flame,
    cls: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900',
    bar: 'from-red-500 to-orange-500',
  },
  warm: {
    label: 'Warm',
    icon: Sun,
    cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900',
    bar: 'from-amber-400 to-yellow-400',
  },
  cold: {
    label: 'Cold',
    icon: Snowflake,
    cls: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-900',
    bar: 'from-sky-400 to-blue-400',
  },
  at_risk: {
    label: 'At Risk',
    icon: AlertTriangle,
    cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900',
    bar: 'from-rose-500 to-pink-500',
  },
};

/** Compact lead health badge — for use in lead detail header and list rows. */
export const HealthScoreBadge = ({ health, size = 'md' }) => {
  if (!health) return null;
  const cfg = BAND_CONFIG[health.band] || BAND_CONFIG.cold;
  const Icon = cfg.icon;
  const compact = size === 'sm';
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border ${cfg.cls} ${compact ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'}`}
      title={`Health score: ${health.score}/100${health.days_inactive != null ? ` • Last activity ${health.days_inactive}d ago` : ''}`}
      data-testid="health-score-badge"
    >
      <Icon className={compact ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      <span className="font-semibold">{cfg.label}</span>
      <span className={`opacity-70 ${compact ? 'text-[10px]' : 'text-xs'}`}>· {health.score}</span>
    </div>
  );
};

/** Full health card — for the lead detail sidebar/main area. Shows bar + factors. */
export const HealthScoreCard = ({ health }) => {
  if (!health) return null;
  const cfg = BAND_CONFIG[health.band] || BAND_CONFIG.cold;
  const Icon = cfg.icon;
  return (
    <div className="rounded-xl border bg-card p-4 space-y-3" data-testid="health-score-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-md ${cfg.cls.replace('border-', 'border ')}`}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Lead Health</div>
            <div className="font-semibold">{cfg.label} · {health.score}/100</div>
          </div>
        </div>
        {health.days_inactive != null && (
          <span className="text-xs text-muted-foreground">
            {health.days_inactive < 1 ? 'Active today' : `${Math.round(health.days_inactive)}d quiet`}
          </span>
        )}
      </div>
      <div className="h-1.5 rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full bg-gradient-to-r ${cfg.bar} transition-all`}
          style={{ width: `${health.score}%` }}
        />
      </div>
      {health.factors?.length > 0 && (
        <ul className="space-y-1 text-xs">
          {health.factors.map((f, i) => (
            <li key={i} className="flex items-center justify-between">
              <span className="text-muted-foreground">{f.name}</span>
              <span className={f.impact > 0 ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-rose-600 dark:text-rose-400 font-medium'}>
                {f.impact > 0 ? `+${f.impact}` : f.impact}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default HealthScoreBadge;
