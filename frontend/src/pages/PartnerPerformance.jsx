import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Loader2, Trophy } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const fmt = (n) => {
  const num = Number(n || 0);
  if (num >= 10000000) return `₹${(num / 10000000).toFixed(2)} Cr`;
  if (num >= 100000) return `₹${(num / 100000).toFixed(2)} L`;
  return `₹${num.toLocaleString('en-IN')}`;
};

const PartnerPerformance = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/reports/partner-performance');
        setData(res.data);
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to load partner performance';
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-6 p-1" data-testid="partner-performance">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gradient-to-br from-yellow-100 to-amber-100 dark:from-yellow-950/40 dark:to-amber-950/40">
          <Trophy className="w-6 h-6 text-amber-700 dark:text-amber-300" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Partner Performance</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Leaderboard of selling partner companies by closed revenue</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{data.total_companies} partner companies</CardTitle>
        </CardHeader>
        <CardContent>
          {data.rows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No partner data yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase tracking-wider text-muted-foreground border-b">
                  <tr>
                    <th className="text-left py-2 pr-3">Rank</th>
                    <th className="text-left py-2 pr-3">Partner Company</th>
                    <th className="text-right py-2 pr-3">Total Leads</th>
                    <th className="text-right py-2 pr-3">Won</th>
                    <th className="text-right py-2 pr-3">Win-rate</th>
                    <th className="text-right py-2 pr-3">Avg Deal</th>
                    <th className="text-right py-2">Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r, idx) => (
                    <tr key={r.company_id} className="border-b last:border-0 hover:bg-accent" data-testid={`partner-row-${r.company_id}`}>
                      <td className="py-3 pr-3">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                          idx === 0 ? 'bg-amber-100 text-amber-700' :
                          idx === 1 ? 'bg-slate-200 text-slate-700' :
                          idx === 2 ? 'bg-orange-100 text-orange-700' :
                          'bg-muted text-muted-foreground'
                        }`}>{idx + 1}</span>
                      </td>
                      <td className="py-3 pr-3 font-medium">{r.company_name}</td>
                      <td className="py-3 pr-3 text-right text-muted-foreground">{r.total}</td>
                      <td className="py-3 pr-3 text-right text-emerald-700 dark:text-emerald-300 font-medium">{r.won}</td>
                      <td className="py-3 pr-3 text-right font-bold">{r.win_rate}%</td>
                      <td className="py-3 pr-3 text-right">{fmt(r.avg_deal)}</td>
                      <td className="py-3 text-right font-bold text-emerald-700 dark:text-emerald-300">{fmt(r.revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PartnerPerformance;
