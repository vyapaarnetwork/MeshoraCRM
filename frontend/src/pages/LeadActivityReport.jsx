import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Loader2, Activity, ArrowUpRight, Trophy, XCircle, RefreshCw } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const fmt = (n) => {
  const num = Number(n || 0);
  if (num >= 10000000) return `₹${(num / 10000000).toFixed(2)} Cr`;
  if (num >= 100000) return `₹${(num / 100000).toFixed(2)} L`;
  return `₹${num.toLocaleString('en-IN')}`;
};

const ICONS = {
  won: { Icon: Trophy, cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' },
  lost: { Icon: XCircle, cls: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300' },
  updated: { Icon: RefreshCw, cls: 'bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300' },
};

const LeadActivityReport = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/reports/lead-activity-feed', { params: { limit: 200 } });
        setData(res.data);
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to load lead activity';
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>;
  if (!data) return null;

  const fmtDate = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return iso.slice(0, 19).replace('T', ' ');
    }
  };

  return (
    <div className="space-y-6 p-1" data-testid="lead-activity-report">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gradient-to-br from-blue-100 to-cyan-100 dark:from-blue-950/40 dark:to-cyan-950/40">
          <Activity className="w-6 h-6 text-blue-700 dark:text-blue-300" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Lead Activity</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Most recent updates across all leads ({data.count} entries)</p>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-lg">Recent activity</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.activities.map((a) => {
              const { Icon, cls } = ICONS[a.kind] || ICONS.updated;
              return (
                <div
                  key={`${a.id}-${a.updated_at}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/leads/${a.id}`)}
                  onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/leads/${a.id}`); }}
                  className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent hover:border-violet-300 cursor-pointer transition-colors"
                  data-testid={`activity-${a.id}`}
                >
                  <div className={`p-2 rounded-lg ${cls}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{a.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {a.customer_company || '—'} · <span style={{ color: a.status_color || undefined }}>{a.status_name || '—'}</span>
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300">{fmt(a.deal_value)}</p>
                    <p className="text-[10px] text-muted-foreground">{fmtDate(a.updated_at)}</p>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-muted-foreground" />
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LeadActivityReport;
