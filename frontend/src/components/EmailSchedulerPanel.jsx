import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import {
  Activity, Bell, CheckCircle2, AlertCircle, Mail, Loader2, RefreshCw, Power, PowerOff, Clock, Send,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { format, parseISO } from 'date-fns';

/** Phase 35 — Email Scheduler Management UI
 *  Admin dashboard for the background reminder loop: global on/off switch,
 *  liveness probe, 7-day send stats, pending reminders, last digest runs,
 *  and a tail of the 50 most recent email logs. */
const EmailSchedulerPanel = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [triggering, setTriggering] = useState(null);

  const fetchStatus = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await api.get('/admin/email-scheduler/status');
      setData(res.data);
    } catch (e) {
      if (!silent) toast.error(e.response?.data?.detail || 'Failed to load scheduler status');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(() => fetchStatus(true), 30000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  const toggle = async (next) => {
    setToggling(true);
    try {
      await api.put('/system-settings/email_scheduler_enabled', { value: next });
      toast.success(next ? 'Email scheduler enabled' : 'Email scheduler paused — no reminders will be sent');
      fetchStatus();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update');
    } finally {
      setToggling(false);
    }
  };

  const triggerDispatch = async (kind) => {
    setTriggering(kind);
    try {
      const endpoint = {
        followups: '/admin/dispatch-follow-up-reminders',
        tasks: '/admin/dispatch-task-reminders',
        weekly: '/admin/dispatch-weekly-war-room-digest',
        monthly: '/admin/dispatch-monthly-digest',
      }[kind];
      const res = await api.post(endpoint);
      const sent = res.data?.sent ?? res.data?.dispatched ?? 0;
      toast.success(`Triggered ${kind} dispatch — ${sent} sent`);
      fetchStatus();
    } catch (e) {
      toast.error(e.response?.data?.detail || `Failed to trigger ${kind}`);
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <Card data-testid="scheduler-panel-loading">
        <CardContent className="py-10 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }
  if (!data) return null;

  const enabled = !!data.enabled;
  const live = !!data.loop_running;
  const zepto = !!data.zeptomail_configured;

  return (
    <Card className="border-violet-200 dark:border-violet-900" data-testid="email-scheduler-panel">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-violet-600 dark:text-violet-400" />
              Email Scheduler
            </CardTitle>
            <CardDescription>
              Background loop that fires exact-time follow-up & action-item reminders, plus weekly/monthly digests.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm" variant="outline"
              onClick={() => fetchStatus()}
              disabled={refreshing}
              data-testid="scheduler-refresh-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md border bg-muted/40">
              <span className="text-xs font-medium">{enabled ? 'ON' : 'PAUSED'}</span>
              <Switch
                checked={enabled}
                onCheckedChange={toggle}
                disabled={toggling}
                data-testid="scheduler-toggle"
              />
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Status row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <StatusPill
            icon={enabled ? Power : PowerOff}
            label="Scheduler"
            value={enabled ? 'Enabled' : 'Paused'}
            ok={enabled}
            testId="scheduler-status-enabled"
          />
          <StatusPill
            icon={Activity}
            label="Loop"
            value={live ? 'Running' : 'Stopped'}
            ok={live}
            testId="scheduler-status-loop"
          />
          <StatusPill
            icon={Mail}
            label="ZeptoMail"
            value={zepto ? 'Configured' : 'Not configured'}
            ok={zepto}
            testId="scheduler-status-zepto"
          />
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Sent (7 days)" value={data.stats_7d?.sent ?? 0} accent="emerald" icon={CheckCircle2} />
          <StatCard label="Failed (7 days)" value={data.stats_7d?.failed ?? 0} accent="rose" icon={AlertCircle} />
          <StatCard label="Pending follow-up reminders" value={data.pending?.follow_up_reminders ?? 0} accent="amber" icon={Bell} />
          <StatCard label="Pending action item reminders" value={data.pending?.task_reminders ?? 0} accent="indigo" icon={Clock} />
        </div>

        {/* Manual dispatch */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Manual dispatch</p>
          <div className="flex flex-wrap gap-2">
            <DispatchBtn label="Follow-ups now" kind="followups" triggering={triggering} onClick={() => triggerDispatch('followups')} />
            <DispatchBtn label="Action items now" kind="tasks" triggering={triggering} onClick={() => triggerDispatch('tasks')} />
            <DispatchBtn label="Weekly War Room digest" kind="weekly" triggering={triggering} onClick={() => triggerDispatch('weekly')} />
            <DispatchBtn label="Monthly Won digest" kind="monthly" triggering={triggering} onClick={() => triggerDispatch('monthly')} />
          </div>
          <p className="text-[11px] text-muted-foreground mt-2">
            Dispatchers respect the global ON/OFF flag and ZeptoMail config — they will no-op when paused.
          </p>
        </div>

        {/* Recent logs */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Recent email log (50 most recent)</p>
          {(!data.recent_logs || data.recent_logs.length === 0) ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No emails sent yet.</p>
          ) : (
            <ScrollArea className="h-[320px] border rounded-md">
              <table className="w-full text-xs" data-testid="scheduler-log-table">
                <thead className="sticky top-0 bg-muted/80 backdrop-blur z-10">
                  <tr>
                    <th className="text-left p-2 font-medium">When</th>
                    <th className="text-left p-2 font-medium">Event</th>
                    <th className="text-left p-2 font-medium">To</th>
                    <th className="text-left p-2 font-medium">Subject</th>
                    <th className="text-left p-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_logs.map((l, i) => {
                    const ok = l.ok !== false;
                    let when = l.sent_at || '';
                    try { when = format(parseISO(l.sent_at), 'dd MMM, HH:mm'); } catch { /* keep raw */ }
                    return (
                      <tr key={i} className="border-t hover:bg-muted/40">
                        <td className="p-2 whitespace-nowrap text-muted-foreground">{when}</td>
                        <td className="p-2 whitespace-nowrap"><Badge variant="outline" className="text-[10px]">{l.event || '-'}</Badge></td>
                        <td className="p-2 truncate max-w-[180px]">{l.to_email || l.to || '-'}</td>
                        <td className="p-2 truncate max-w-[260px]">{l.subject || '-'}</td>
                        <td className="p-2">
                          {ok
                            ? <Badge className="text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">Sent</Badge>
                            : <Badge className="text-[10px] bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">Failed</Badge>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollArea>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

const StatusPill = ({ icon: Icon, label, value, ok, testId }) => (
  <div
    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border ${
      ok
        ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900'
        : 'bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900'
    }`}
    data-testid={testId}
  >
    <Icon className={`w-4 h-4 ${ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`} />
    <div className="flex-1">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  </div>
);

const STAT_ACCENT = {
  emerald: 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900',
  rose: 'bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900',
  amber: 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900',
  indigo: 'bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900',
};

const StatCard = ({ label, value, accent, icon: Icon }) => (
  <div className={`px-3 py-2.5 rounded-lg border ${STAT_ACCENT[accent]}`}>
    <div className="flex items-center justify-between">
      <p className="text-[10px] font-semibold uppercase tracking-wider opacity-80">{label}</p>
      <Icon className="w-3.5 h-3.5 opacity-80" />
    </div>
    <p className="text-2xl font-bold mt-1">{value}</p>
  </div>
);

const DispatchBtn = ({ label, kind, triggering, onClick }) => (
  <Button
    size="sm"
    variant="outline"
    onClick={onClick}
    disabled={triggering === kind}
    data-testid={`scheduler-dispatch-${kind}`}
  >
    {triggering === kind
      ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
      : <Send className="w-3.5 h-3.5 mr-1.5" />}
    {label}
  </Button>
);

export default EmailSchedulerPanel;
