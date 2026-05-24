import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { formatCurrency, formatDate } from '../utils/api';
import { Card, CardContent } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
import { Briefcase, Repeat } from 'lucide-react';
import { toast } from 'sonner';

const CommercialsKanban = () => {
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/commercials/kanban').then((r) => setColumns(r.data.columns || [])).catch(() => toast.error('Failed to load kanban')).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-64" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="commercials-kanban-page">
      <div>
        <h1 className="text-2xl font-bold">Commercials Kanban</h1>
        <p className="text-sm text-muted-foreground">Pipeline view of every contract & project, grouped by status.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {columns.filter(c => c.items.length > 0).map((col) => (
          <div key={col.key} className="space-y-2" data-testid={`kanban-column-${col.key}`}>
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: col.color }} />
                <h3 className="font-semibold text-sm uppercase tracking-wider">{col.label}</h3>
              </div>
              <Badge variant="secondary" className="text-xs">{col.items.length}</Badge>
            </div>
            <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
              {col.items.map((c) => (
                <Link key={c.id} to={`/commercials/${c.id}`} className="block group" data-testid={`kanban-card-${c.id}`}>
                  <Card className="transition-shadow group-hover:shadow-md cursor-pointer">
                    <CardContent className="p-3 space-y-2">
                      <div className="flex items-center gap-1 text-xs">
                        {c.type === 'one_time' ? <Briefcase className="w-3 h-3" /> : <Repeat className="w-3 h-3" />}
                        <span className="text-muted-foreground">{c.customer_name || '—'}</span>
                      </div>
                      <div className="font-medium text-sm leading-tight">{c.lead_title}</div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">
                          {c.type === 'one_time' ? `${(c.milestones || []).length} milestones` : (c.billing_frequency || '').replace('_', ' ')}
                        </span>
                        <span className="font-semibold">
                          {formatCurrency(c.type === 'one_time' ? c.total_value : c.contract_value)}
                        </span>
                      </div>
                      {c.type === 'recurring' && c.contract_end_date && (
                        <div className="text-[10px] text-muted-foreground">Ends {formatDate(c.contract_end_date)}</div>
                      )}
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      {columns.every(c => c.items.length === 0) && (
        <Card><CardContent className="py-12 text-center text-muted-foreground">No commercials yet.</CardContent></Card>
      )}
    </div>
  );
};

export default CommercialsKanban;
