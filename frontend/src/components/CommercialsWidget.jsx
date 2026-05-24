import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { formatCurrency, formatDate } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Badge } from './ui/badge';
import { Briefcase, Repeat, TrendingUp, AlertCircle, ChevronRight, Wallet } from 'lucide-react';

const CommercialsWidget = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    // Trigger silent renewal scan first (idempotent), then load dashboard.
    (async () => {
      try {
        await api.post('/commercials/run-renewal-scan');
      } catch (e) {
        // Non-admin users will 403 — ignore.
      }
      try {
        const r = await api.get('/commercials/dashboard');
        setData(r.data);
      } catch (e) {
        setData(null);
      }
    })();
  }, []);

  if (!data) return null;

  const ot = data.one_time || {};
  const rc = data.recurring || {};
  const hasAny = (ot.project_count || 0) + (rc.total_contracts || 0) > 0;

  if (!hasAny) {
    return (
      <Card data-testid="commercials-widget">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Briefcase className="w-5 h-5 text-primary" /> Commercials</CardTitle>
          <CardDescription>Set up commercials on a won deal to see metrics here.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card data-testid="commercials-widget">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2"><Briefcase className="w-5 h-5 text-primary" /> Commercials snapshot</CardTitle>
            <CardDescription>Post-sales revenue & delivery health</CardDescription>
          </div>
          <Link to="/commercials" className="text-sm text-primary hover:underline flex items-center gap-1" data-testid="open-commercials-link">
            View all <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* One-time KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPI icon={Briefcase} label="One-time projects" value={ot.project_count || 0} />
          <KPI icon={TrendingUp} label="Project value" value={formatCurrency(ot.total_project_value || 0)} />
          <KPI icon={Wallet} label="Realized" value={formatCurrency(ot.revenue_realized || 0)} accent="text-green-600 dark:text-green-400" />
          <KPI icon={AlertCircle} label="Overdue invoices" value={ot.overdue_invoices || 0} accent={ot.overdue_invoices > 0 ? 'text-red-600 dark:text-red-400' : ''} />
        </div>
        {/* Recurring KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPI icon={Repeat} label="Active subscriptions" value={rc.active_subscriptions || 0} />
          <KPI icon={TrendingUp} label="MRR" value={formatCurrency(rc.mrr || 0)} />
          <KPI icon={TrendingUp} label="ARR" value={formatCurrency(rc.arr || 0)} accent="text-primary" />
          <KPI icon={AlertCircle} label="Renewals (60d)" value={(rc.upcoming_renewals || []).length} accent={(rc.upcoming_renewals || []).length > 0 ? 'text-amber-600 dark:text-amber-400' : ''} />
        </div>

        {/* Upcoming renewals list */}
        {(rc.upcoming_renewals || []).length > 0 && (
          <div className="border-t pt-3">
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Upcoming renewals</div>
            <ul className="space-y-1.5">
              {rc.upcoming_renewals.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between text-sm">
                  <Link to={`/commercials/${r.id}`} className="hover:underline">{r.lead_title}</Link>
                  <Badge variant="outline" className="text-xs">
                    {r.days_to_expiry}d · {formatDate(r.end_date)}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const KPI = ({ icon: Icon, label, value, accent = '' }) => (
  <div className="rounded-md border p-3">
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
      <Icon className="w-3 h-3" />
      {label}
    </div>
    <div className={`text-lg font-bold mt-1 ${accent}`}>{value}</div>
  </div>
);

export default CommercialsWidget;
