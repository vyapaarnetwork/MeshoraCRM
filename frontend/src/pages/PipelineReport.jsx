import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Loader2, PieChart as PieChartIcon, IndianRupee } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const formatINR = (n) => {
  const num = Number(n || 0);
  if (num >= 10000000) return `₹${(num / 10000000).toFixed(2)} Cr`;
  if (num >= 100000) return `₹${(num / 100000).toFixed(2)} L`;
  return `₹${num.toLocaleString('en-IN')}`;
};

const PipelineReport = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/reports/pipeline');
        setData(res.data);
      } catch (e) {
        toast.error('Failed to load pipeline report');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>;
  if (!data) return null;

  const max = Math.max(1, ...data.stages.map(s => s.count));

  return (
    <div className="space-y-6 p-1" data-testid="pipeline-report">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gradient-to-br from-violet-100 to-indigo-100 dark:from-violet-950/40 dark:to-indigo-950/40">
          <PieChartIcon className="w-6 h-6 text-violet-700 dark:text-violet-300" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Pipeline Report</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Lead distribution by stage with deal value totals</p>
        </div>
      </div>

      <Card>
        <CardContent className="py-5 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Leads</p>
            <p className="text-3xl font-bold mt-1" data-testid="pipeline-total-count">{data.total_count}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Pipeline Value</p>
            <p className="text-3xl font-bold mt-1 text-emerald-700 dark:text-emerald-300" data-testid="pipeline-total-value">{formatINR(data.total_value)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Stages</p>
            <p className="text-3xl font-bold mt-1">{data.stages.length}</p>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {data.stages.map((s) => {
          const width = (s.count / max) * 100;
          return (
            <Card key={s.id} data-testid={`pipeline-stage-${s.id}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ background: s.color || '#94a3b8' }} />
                    {s.name}
                    {s.is_won && <span className="text-xs bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded">WON</span>}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-3">
                    <span className="font-semibold text-foreground">{s.count} leads</span>
                    <span className="text-emerald-700 dark:text-emerald-300 font-semibold">{formatINR(s.total_value)}</span>
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden mb-3">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${width}%`, background: s.color || '#7c3aed' }}
                  />
                </div>
                {s.leads.length > 0 && (
                  <div className="space-y-1">
                    {s.leads.slice(0, 5).map((l) => (
                      <div key={l.id} className="flex items-center justify-between text-sm gap-3 hover:bg-accent rounded-md px-2 py-1">
                        <span className="truncate">{l.title}</span>
                        <span className="text-xs text-muted-foreground truncate flex-1 text-right">{l.customer_company || '—'}</span>
                        <span className="font-medium shrink-0 inline-flex items-center"><IndianRupee className="w-3 h-3" />{l.deal_value.toLocaleString('en-IN')}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

export default PipelineReport;
