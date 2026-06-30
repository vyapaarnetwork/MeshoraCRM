import { Sparkles, ArrowRight, AlertOctagon, Clock, Zap } from 'lucide-react';
import { Button } from './ui/button';

const URGENCY_CONFIG = {
  critical: {
    bg: 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900',
    icon: AlertOctagon,
    iconCls: 'text-rose-600 dark:text-rose-400',
    label: 'Urgent',
    labelCls: 'bg-rose-600 text-white',
  },
  high: {
    bg: 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900',
    icon: Zap,
    iconCls: 'text-amber-600 dark:text-amber-400',
    label: 'High',
    labelCls: 'bg-amber-600 text-white',
  },
  medium: {
    bg: 'bg-violet-50 dark:bg-violet-950/40 border-violet-200 dark:border-violet-900',
    icon: Sparkles,
    iconCls: 'text-violet-600 dark:text-violet-400',
    label: 'Suggested',
    labelCls: 'bg-violet-600 text-white',
  },
  low: {
    bg: 'bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800',
    icon: Clock,
    iconCls: 'text-slate-600 dark:text-slate-400',
    label: 'Optional',
    labelCls: 'bg-slate-600 text-white',
  },
};

/** "Next Action" sticky card — sits at the top of the lead detail sidebar.
 *
 *  Optional `secondaryAction` renders an additional CTA below the primary one
 *  (e.g. "One-click setup" for setup_commercials).
 */
const NextActionCard = ({ nextAction, onAction, secondaryAction }) => {
  if (!nextAction) return null;
  const cfg = URGENCY_CONFIG[nextAction.urgency] || URGENCY_CONFIG.medium;
  const Icon = cfg.icon;

  return (
    <div
      className={`rounded-xl border p-4 ${cfg.bg}`}
      data-testid="next-action-card"
    >
      <div className="flex items-start gap-3">
        <div className={`shrink-0 p-2 rounded-lg bg-white/60 dark:bg-black/30 ${cfg.iconCls}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded ${cfg.labelCls}`}>
              {cfg.label}
            </span>
            <span className="text-xs uppercase tracking-wider text-muted-foreground">Next Action</span>
          </div>
          <div className="font-semibold text-sm" data-testid="next-action-label">
            {nextAction.label}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
            {nextAction.reason}
          </p>
          {secondaryAction && (
            <Button
              size="sm"
              className="mt-3 h-7 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
              onClick={secondaryAction.onClick}
              disabled={secondaryAction.loading}
              data-testid="next-action-primary-btn"
            >
              {secondaryAction.loading ? 'Setting up…' : secondaryAction.label}
              {!secondaryAction.loading && <ArrowRight className="w-3 h-3 ml-1" />}
            </Button>
          )}
          {onAction && (
            <Button
              size="sm"
              variant={secondaryAction ? "ghost" : "secondary"}
              className={`${secondaryAction ? 'mt-1 ml-1' : 'mt-3'} h-7 text-xs`}
              onClick={() => onAction(nextAction)}
              data-testid="next-action-btn"
            >
              {secondaryAction ? 'Open full wizard' : 'Take action'}
              {!secondaryAction && <ArrowRight className="w-3 h-3 ml-1" />}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default NextActionCard;
