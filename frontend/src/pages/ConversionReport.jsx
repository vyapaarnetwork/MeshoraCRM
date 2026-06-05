import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Loader2, Target, TrendingUp, Clock } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const ConversionReport = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/reports/conversion');
        setData(res.data);
      } catch (e) {
        toast.error('Failed to load conversion report');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>;
  if (!data) return null;

  const f = data.funnel;

  return (
    <div className="space-y-6 p-1" data-testid="conversion-report">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-950/40 dark:to-orange-950/40">
          <Target className="w-6 h-6 text-amber-700 dark:text-amber-300" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Conversion Report</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Win-rate and average days-to-close by category</p>
        </div>
      </div>

      {/* Funnel KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Total Leads', value: f.total, color: 'bg-slate-100 dark:bg-slate-900' },
          { label: 'Assigned', value: f.assigned, color: 'bg-blue-50 dark:bg-blue-950/40' },
          { label: 'Won', value: f.won, color: 'bg-emerald-50 dark:bg-emerald-950/40' },
          { label: 'Lost', value: f.lost, color: 'bg-rose-50 dark:bg-rose-950/40' },
          { label: 'Win-rate', value: `${f.win_rate}%`, color: 'bg-violet-50 dark:bg-violet-950/40' },
        ].map((k) => (
          <Card key={k.label} className={k.color} data-testid={`kpi-${k.label.toLowerCase().replace(/\s+/g, '-')}`}>
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">{k.label}</p>
              <p className="text-2xl font-bold mt-1">{k.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Avg days-to-close */}
      <Card className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border-emerald-200 dark:border-emerald-900">
        <CardContent className="py-5 flex items-center gap-3">
          <Clock className="w-7 h-7 text-emerald-700 dark:text-emerald-300" />
          <div>
            <p className="text-xs uppercase tracking-wider text-emerald-700 dark:text-emerald-300">Avg. Days to Close</p>
            <p className="text-2xl font-bold text-emerald-900 dark:text-emerald-100" data-testid="avg-days-to-close">
              {data.avg_days_to_close !== null ? `${data.avg_days_to_close} days` : 'No data yet'}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* By category */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Conversion by Category</CardTitle>
          <CardDescription>Win-rate per primary lead category</CardDescription>
        </CardHeader>
        <CardContent>
          {data.by_category.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No category data yet.</p>
          ) : (
            <div className="space-y-2">
              {data.by_category.map((c) => (
                <div key={c.category_id} className="flex flex-col gap-1 py-2 border-b last:border-0" data-testid={`cat-row-${c.category_id}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium truncate">{c.name}</span>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-muted-foreground">{c.total} total</span>
                      <span className="text-emerald-600 font-medium">{c.won} won</span>
                      <span className="text-rose-600">{c.lost} lost</span>
                      <span className="font-bold">{c.win_rate}%</span>
                    </div>
                  </div>
                  <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded">
                    <div className="h-full rounded bg-gradient-to-r from-emerald-500 to-teal-500" style={{ width: `${c.win_rate}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ConversionReport;
