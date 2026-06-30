import { useEffect, useMemo, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Download, Filter, X, RefreshCw, Search, Activity,
  User, Clock,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import api from '../utils/api';
import { toast } from 'sonner';

const ACTION_COLOR = {
  commercial_approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  quick_setup: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  schedule_regenerated: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  event_updated: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
};

const actionLabel = (a) => {
  if (!a) return '—';
  if (a.startsWith('transition.')) return a.replace('transition.', '');
  return a.replace(/_/g, ' ');
};

const actionTone = (a) => {
  if (ACTION_COLOR[a]) return ACTION_COLOR[a];
  if ((a || '').startsWith('transition.')) return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300';
  return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200';
};

const fmtDateTime = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const FinanceAuditLog = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actions, setActions] = useState([]);
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({
    user_id: '',
    action: '',
    date_from: '',
    date_to: '',
  });

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const r = await api.get('/finance/audit-log', { params });
      setRows(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load audit log');
    } finally { setLoading(false); }
  }, [filters]);

  useEffect(() => {
    api.get('/finance/audit-log/distinct-actions').then((r) => setActions(r.data || [])).catch(() => {});
    api.get('/users').then((r) => setUsers(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((r) =>
      (r.message || '').toLowerCase().includes(q)
      || (r.user_name || '').toLowerCase().includes(q)
      || (r.action || '').toLowerCase().includes(q)
    );
  }, [rows, search]);

  // Group entries by date for visual scanning
  const grouped = useMemo(() => {
    const out = {};
    filtered.forEach((r) => {
      const day = (r.created_at || '').slice(0, 10) || 'Undated';
      if (!out[day]) out[day] = [];
      out[day].push(r);
    });
    return out;
  }, [filtered]);

  const exportCsv = () => {
    if (!filtered.length) return toast.info('Nothing to export.');
    const headers = ['Timestamp', 'User', 'Action', 'Message', 'Commercial ID', 'Revenue Event ID'];
    const lines = filtered.map((r) => [r.created_at, r.user_name || '', r.action || '', r.message || '', r.commercial_id || '', r.revenue_event_id || '']);
    const csv = [headers, ...lines].map((row) => row.map((c) => {
      const s = String(c ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `finance-audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => setFilters({ user_id: '', action: '', date_from: '', date_to: '' });
  const activeCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="space-y-5" data-testid="finance-audit-log">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link to="/finance"><Button variant="ghost" size="sm"><ArrowLeft className="w-3.5 h-3.5 mr-1" /> Dashboard</Button></Link>
          <h1 className="text-2xl font-bold tracking-tight mt-1">Finance Audit Log</h1>
          <p className="text-sm text-muted-foreground">Every financial action ever taken — searchable, filterable, exportable.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search message / user / action…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
            data-testid="audit-search"
          />
          <Button variant="outline" size="sm" onClick={fetchRows} disabled={loading} data-testid="audit-refresh-btn">
            <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={exportCsv} data-testid="audit-export-btn">
            <Download className="w-4 h-4 mr-1" /> Export CSV
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-3 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            <Filter className="w-4 h-4" /> Filters
            {activeCount > 0 && <Badge variant="outline" className="text-[10px]">{activeCount} active</Badge>}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-[11px] text-muted-foreground">User</label>
              <Select value={filters.user_id || 'all'} onValueChange={(v) => setFilters((s) => ({ ...s, user_id: v === 'all' ? '' : v }))}>
                <SelectTrigger data-testid="audit-filter-user"><SelectValue placeholder="Any user" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any user</SelectItem>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>{u.name || u.email}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground">Action</label>
              <Select value={filters.action || 'all'} onValueChange={(v) => setFilters((s) => ({ ...s, action: v === 'all' ? '' : v }))}>
                <SelectTrigger data-testid="audit-filter-action"><SelectValue placeholder="Any action" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any action</SelectItem>
                  {actions.map((a) => (
                    <SelectItem key={a} value={a}>{actionLabel(a)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground">From</label>
              <Input type="date" value={filters.date_from} onChange={(e) => setFilters((s) => ({ ...s, date_from: e.target.value }))} data-testid="audit-filter-from" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground">To</label>
              <Input type="date" value={filters.date_to} onChange={(e) => setFilters((s) => ({ ...s, date_to: e.target.value }))} data-testid="audit-filter-to" />
            </div>
          </div>
          <div className="flex justify-between items-center">
            <div className="text-xs text-muted-foreground">{loading ? 'Loading…' : `${filtered.length} entr${filtered.length === 1 ? 'y' : 'ies'}`}</div>
            <Button variant="ghost" size="sm" onClick={reset} data-testid="audit-reset-btn">
              <X className="w-3.5 h-3.5 mr-1" /> Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {loading ? (
          <div className="space-y-2">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : Object.entries(grouped).length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              <Search className="w-6 h-6 mx-auto mb-2 opacity-40" />
              No audit entries match these filters.
            </CardContent>
          </Card>
        ) : (
          Object.entries(grouped).map(([day, items]) => (
            <Card key={day}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="w-4 h-4 text-indigo-600" />
                  {day}
                  <Badge variant="outline" className="text-[10px]">{items.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {items.map((row) => (
                    <div
                      key={row.id}
                      className="flex items-start gap-3 text-sm border-l-2 border-indigo-200 dark:border-indigo-900 pl-3 py-2 hover:bg-muted/30 rounded-r-md"
                      data-testid={`audit-row-${row.id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge className={`${actionTone(row.action)} border-0 text-[10px]`}>
                            <Activity className="w-3 h-3 mr-1" />{actionLabel(row.action)}
                          </Badge>
                          <span className="font-medium">{row.message}</span>
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1"><User className="w-3 h-3" />{row.user_name || 'System'}</span>
                          <span>·</span>
                          <span>{fmtDateTime(row.created_at)}</span>
                          {row.revenue_event_id && (
                            <>
                              <span>·</span>
                              <Link
                                to={`/finance/events/${row.revenue_event_id}`}
                                className="text-indigo-600 dark:text-indigo-300 hover:underline"
                                data-testid={`audit-event-link-${row.id}`}
                              >
                                Open event →
                              </Link>
                            </>
                          )}
                          {row.commercial_id && !row.revenue_event_id && (
                            <>
                              <span>·</span>
                              <Link
                                to={`/commercials/${row.commercial_id}`}
                                className="text-indigo-600 dark:text-indigo-300 hover:underline"
                              >
                                Open commercial →
                              </Link>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default FinanceAuditLog;
