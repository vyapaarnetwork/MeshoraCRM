import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  ListTodo, Plus, Loader2, ChevronDown, Trash2, AlertTriangle, Check,
  Clock, Users, Calendar, Send, Briefcase, Coins,
} from 'lucide-react';
import api, { formatDate, formatDateTime, getRoleLabel } from '../utils/api';
import { toast } from 'sonner';
import SearchableUserSelect from '../components/SearchableUserSelect';

const PRIORITY_STYLES = {
  low: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  high: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  urgent: 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950/40 dark:text-fuchsia-300',
};
const STATUS_STYLES = {
  todo: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  in_progress: 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300',
  blocked: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  done: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  cancelled: 'bg-slate-100 text-slate-500 line-through',
};
const STATUS_LABELS = {
  todo: 'To-do', in_progress: 'In progress', blocked: 'Blocked', done: 'Done', cancelled: 'Cancelled',
};
const CATEGORY_LABELS = {
  operations: 'Operations',
  partner_coordination: 'Partner coordination',
  sales_associate: 'Sales associate',
  finance: 'Finance',
  onboarding: 'Onboarding',
  other: 'Other',
};
const REMINDER_OPTIONS = [
  { value: 0, label: 'No email reminder' },
  { value: 30, label: '30 min before' },
  { value: 60, label: '1 hour before' },
  { value: 120, label: '2 hours before' },
  { value: 1440, label: '1 day before' },
  { value: 2880, label: '2 days before' },
];

const InternalTasks = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState([]);
  const [filters, setFilters] = useState({ status: 'all', category: 'all', priority: 'all', mine: false, q: '' });
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);

  const blankForm = () => ({
    title: '', description: '', assignee_id: '', due_date: '',
    priority: 'medium', category: 'operations', reminder_minutes_before: 0,
    related_partner_id: '', related_lead_id: '', tags: '',
  });
  const [form, setForm] = useState(blankForm());

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.status !== 'all') params.set('status', filters.status);
      if (filters.category !== 'all') params.set('category', filters.category);
      if (filters.priority !== 'all') params.set('priority', filters.priority);
      if (filters.mine) params.set('mine', 'true');
      if (filters.q.trim()) params.set('q', filters.q.trim());
      const res = await api.get(`/internal-tasks?${params.toString()}`);
      setItems(res.data?.items || []);
      setCounts(res.data?.counts || {});
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load internal tasks');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    api.get('/internal-tasks/_meta/assignable-users')
      .then((r) => setUsers(r.data || []))
      .catch(() => {});
  }, []);

  const openCreate = () => {
    setEditing(null);
    setForm(blankForm());
    setShowForm(true);
  };
  const openEdit = (t) => {
    setEditing(t);
    setForm({
      title: t.title || '',
      description: t.description || '',
      assignee_id: t.assignee_id || '',
      due_date: t.due_date || '',
      priority: t.priority || 'medium',
      category: t.category || 'operations',
      reminder_minutes_before: t.reminder_minutes_before || 0,
      related_partner_id: t.related_partner_id || '',
      related_lead_id: t.related_lead_id || '',
      tags: (t.tags || []).join(', '),
    });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.title.trim()) return toast.error('Title is required');
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        assignee_id: form.assignee_id || null,
        due_date: form.due_date || null,
        priority: form.priority,
        category: form.category,
        reminder_minutes_before: Number(form.reminder_minutes_before || 0),
        related_partner_id: form.related_partner_id || null,
        related_lead_id: form.related_lead_id || null,
        tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      };
      if (editing) {
        await api.patch(`/internal-tasks/${editing.id}`, payload);
        toast.success('Task updated');
      } else {
        await api.post('/internal-tasks', payload);
        toast.success('Task created');
      }
      setShowForm(false);
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const changeStatus = async (t, status) => {
    try {
      await api.patch(`/internal-tasks/${t.id}`, { status });
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update status');
    }
  };

  const remove = async (t) => {
    if (!window.confirm(`Delete "${t.title}"?`)) return;
    try {
      await api.delete(`/internal-tasks/${t.id}`);
      toast.success('Task deleted');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  const ringStats = useMemo(() => ([
    { key: 'todo', label: 'To-do', value: counts.todo || 0, icon: ListTodo, accent: 'text-slate-700 bg-slate-50 border-slate-200 dark:bg-slate-900/40 dark:border-slate-800' },
    { key: 'in_progress', label: 'In progress', value: counts.in_progress || 0, icon: Clock, accent: 'text-blue-700 bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-900' },
    { key: 'overdue', label: 'Overdue', value: counts.overdue || 0, icon: AlertTriangle, accent: 'text-rose-700 bg-rose-50 border-rose-200 dark:bg-rose-950/30 dark:border-rose-900' },
    { key: 'due_today', label: 'Due today', value: counts.due_today || 0, icon: Calendar, accent: 'text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900' },
  ]), [counts]);

  return (
    <div className="space-y-6" data-testid="internal-tasks-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <ListTodo className="w-6 h-6 text-primary" />
            Internal Tasks
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Track Vyapaar operations & partner-coordination work. Weekly Monday 9&nbsp;AM&nbsp;IST snapshot is emailed to every internal user.
          </p>
        </div>
        <Button onClick={openCreate} data-testid="new-internal-task-btn" size="lg" className="gap-2">
          <Plus className="w-4 h-4" /> New task
        </Button>
      </div>

      {/* Stat ring */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {ringStats.map((s) => (
          <Card key={s.key} className={`border ${s.accent}`} data-testid={`stat-${s.key}`}>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-wider opacity-80">{s.label}</p>
                <s.icon className="w-4 h-4 opacity-80" />
              </div>
              <p className="text-2xl font-bold mt-1">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-3 flex flex-wrap items-center gap-2">
          <Input
            placeholder="Search by title…"
            value={filters.q}
            onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))}
            className="max-w-xs"
            data-testid="filter-search"
          />
          <Select value={filters.status} onValueChange={(v) => setFilters((p) => ({ ...p, status: v }))}>
            <SelectTrigger className="w-36" data-testid="filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.category} onValueChange={(v) => setFilters((p) => ({ ...p, category: v }))}>
            <SelectTrigger className="w-44" data-testid="filter-category"><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.priority} onValueChange={(v) => setFilters((p) => ({ ...p, priority: v }))}>
            <SelectTrigger className="w-32" data-testid="filter-priority"><SelectValue placeholder="Priority" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All priorities</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant={filters.mine ? 'default' : 'outline'}
            onClick={() => setFilters((p) => ({ ...p, mine: !p.mine }))}
            data-testid="filter-mine-toggle"
            size="sm"
          >
            <Users className="w-3.5 h-3.5 mr-1" /> {filters.mine ? 'Mine only' : 'Everyone'}
          </Button>
        </CardContent>
      </Card>

      {/* List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>Tasks ({counts.total || 0})</span>
            {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <ListTodo className="w-10 h-10 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No internal tasks match your filters.</p>
            </div>
          ) : items.map((t) => (
            <div
              key={t.id}
              className={`group flex items-start gap-3 p-3 border rounded-lg hover:bg-muted/40 transition-colors ${
                t.is_overdue ? 'border-rose-200 bg-rose-50/40 dark:border-rose-900 dark:bg-rose-950/20' : ''
              }`}
              data-testid={`internal-task-row-${t.id}`}
            >
              <button
                type="button"
                onClick={() => changeStatus(t, t.status === 'done' ? 'todo' : 'done')}
                className="mt-0.5 shrink-0"
                title={t.status === 'done' ? 'Mark as to-do' : 'Mark done'}
                data-testid={`toggle-status-${t.id}`}
              >
                {t.status === 'done'
                  ? <Check className="w-4 h-4 text-emerald-600" />
                  : <span className="w-4 h-4 rounded-full border-2 border-muted-foreground/40 inline-block" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    onClick={() => openEdit(t)}
                    className={`text-sm font-medium hover:underline text-left ${t.status === 'done' ? 'line-through text-muted-foreground' : ''}`}
                    data-testid={`edit-task-${t.id}`}
                  >
                    {t.title}
                  </button>
                  <Badge className={`text-[10px] ${PRIORITY_STYLES[t.priority]}`}>{t.priority}</Badge>
                  <Badge className={`text-[10px] ${STATUS_STYLES[t.status]}`}>{STATUS_LABELS[t.status]}</Badge>
                  <Badge variant="outline" className="text-[10px]">
                    {CATEGORY_LABELS[t.category] || t.category}
                  </Badge>
                  {t.is_overdue && (
                    <Badge className="text-[10px] bg-rose-600 text-white">Overdue</Badge>
                  )}
                </div>
                {t.description && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{t.description}</p>
                )}
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
                  {t.assignee_name && (
                    <span className="inline-flex items-center gap-1">
                      <Users className="w-3 h-3" /> {t.assignee_name}
                      {t.assignee_role && <span className="opacity-60">· {getRoleLabel(t.assignee_role)}</span>}
                    </span>
                  )}
                  {t.due_date && (
                    <span className="inline-flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {t.due_date.includes('T') ? formatDateTime(t.due_date) : formatDate(t.due_date)}
                    </span>
                  )}
                  {t.related_partner_name && (
                    <span className="inline-flex items-center gap-1">
                      <Briefcase className="w-3 h-3" /> {t.related_partner_name}
                    </span>
                  )}
                  {t.related_lead_title && (
                    <button
                      onClick={() => navigate(`/leads/${t.related_lead_id}`)}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <Coins className="w-3 h-3" /> {t.related_lead_title}
                    </button>
                  )}
                  {t.reminder_minutes_before > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <Send className="w-3 h-3" />
                      Email {t.reminder_minutes_before < 60
                        ? `${t.reminder_minutes_before}m`
                        : t.reminder_minutes_before < 1440
                          ? `${Math.round(t.reminder_minutes_before / 60)}h`
                          : `${Math.round(t.reminder_minutes_before / 1440)}d`} before
                    </span>
                  )}
                </div>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="ghost" className="h-7 px-2" data-testid={`row-menu-${t.id}`}>
                    <ChevronDown className="w-3.5 h-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {Object.entries(STATUS_LABELS).map(([k, v]) => (
                    <DropdownMenuItem key={k} onClick={() => changeStatus(t, k)}>{v}</DropdownMenuItem>
                  ))}
                  <DropdownMenuItem onClick={() => openEdit(t)}>Edit</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => remove(t)} className="text-rose-600">
                    <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Create / Edit Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl" data-testid="internal-task-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit internal task' : 'New internal task'}</DialogTitle>
            <DialogDescription>
              {editing ? 'Update the task details below.' : 'Assign internal Vyapaar work — operations, partner coordination, finance, onboarding etc.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Title <span className="text-rose-500">*</span></Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Reconcile June commissions"
                data-testid="form-title"
              />
            </div>
            <div>
              <Label className="text-xs">Description</Label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                data-testid="form-description"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Assignee</Label>
                <SearchableUserSelect
                  value={form.assignee_id}
                  onChange={(v) => setForm({ ...form, assignee_id: v })}
                  users={users}
                  placeholder="Pick a teammate…"
                  testId="form-assignee"
                />
              </div>
              <div>
                <Label className="text-xs">Priority</Label>
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger data-testid="form-priority"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Category</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger data-testid="form-category"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Due (date &amp; optional time)</Label>
                <Input
                  type="datetime-local"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                  data-testid="form-due"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Email reminder</Label>
              <Select
                value={String(form.reminder_minutes_before || 0)}
                onValueChange={(v) => setForm({ ...form, reminder_minutes_before: parseInt(v, 10) })}
              >
                <SelectTrigger data-testid="form-reminder"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {REMINDER_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={String(o.value)}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Tags (comma-separated)</Label>
              <Input
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="e.g. q3, urgent, partner-acme"
                data-testid="form-tags"
              />
            </div>
            {editing && (
              <div>
                <Label className="text-xs">Status</Label>
                <Select
                  value={form.status || editing.status || 'todo'}
                  onValueChange={(v) => setForm({ ...form, status: v })}
                >
                  <SelectTrigger data-testid="form-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(STATUS_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="form-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editing ? 'Save changes' : 'Create task')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default InternalTasks;
