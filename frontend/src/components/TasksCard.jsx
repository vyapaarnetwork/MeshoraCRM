import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  ListChecks, Plus, Check, Trash2, Circle, Loader2, ChevronDown, Bell,
} from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import api, { formatDate, formatDateTime } from '../utils/api';
import { toast } from 'sonner';
import SearchableUserSelect from './SearchableUserSelect';

const PRIORITY_COLORS = {
  low: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  high: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
};
const STATUS_LABELS = { todo: 'To-do', in_progress: 'In progress', done: 'Done' };

const REMINDER_OPTIONS = [
  { value: 0, label: 'No email reminder' },
  { value: 30, label: 'Email 30 min before' },
  { value: 60, label: 'Email 1 hour before' },
  { value: 120, label: 'Email 2 hours before' },
  { value: 1440, label: 'Email 1 day before' },
];

const TasksCard = ({ leadId, refreshKey }) => {
  const [tasks, setTasks] = useState([]);
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [newTask, setNewTask] = useState({
    title: '', description: '', assignee_id: '', due_date: '', priority: 'medium', reminder_minutes_before: 0,
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchTasks = useCallback(async () => {
    try {
      const r = await api.get(`/tasks?lead_id=${leadId}`);
      setTasks(r.data || []);
    } catch (e) { /* noop */ }
  }, [leadId]);

  useEffect(() => {
    fetchTasks();
    // Phase 35 — unified assignee pool across ALL roles (customer / partner / associate / Vyapaar team)
    api.get('/users/assignable').then((r) => setUsers((r.data || []).filter(u => u.is_active !== false))).catch(() => {});
  }, [fetchTasks, refreshKey]);

  const handleCreate = async () => {
    if (!newTask.title.trim()) return toast.error('Action item title required');
    setSubmitting(true);
    try {
      const payload = { ...newTask, lead_id: leadId };
      if (!payload.assignee_id) delete payload.assignee_id;
      if (!payload.due_date) delete payload.due_date;
      await api.post('/tasks', payload);
      setNewTask({ title: '', description: '', assignee_id: '', due_date: '', priority: 'medium', reminder_minutes_before: 0 });
      setShowForm(false);
      toast.success('Action item created');
      fetchTasks();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create action item');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatus = async (taskId, status) => {
    try {
      await api.patch(`/tasks/${taskId}`, { status });
      fetchTasks();
    } catch (e) {
      toast.error('Failed to update task');
    }
  };

  const handleDelete = async (taskId) => {
    if (!window.confirm('Delete this action item?')) return;
    try {
      await api.delete(`/tasks/${taskId}`);
      fetchTasks();
      toast.success('Action item deleted');
    } catch (e) {
      toast.error('Failed to delete');
    }
  };

  const sorted = [...tasks].sort((a, b) => {
    const order = { todo: 0, in_progress: 1, done: 2 };
    if (order[a.status] !== order[b.status]) return order[a.status] - order[b.status];
    return (a.due_date || '').localeCompare(b.due_date || '');
  });

  return (
    <Card data-testid="tasks-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="w-5 h-5 text-primary" />
            Action Items ({tasks.length})
          </CardTitle>
          <Button size="sm" variant="outline" onClick={() => setShowForm(!showForm)} data-testid="add-task-btn">
            <Plus className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {showForm && (
          <div className="p-3 border rounded-lg space-y-2 bg-muted/40 animate-scale-in">
            <Input
              placeholder="Action item title"
              value={newTask.title}
              onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              data-testid="task-title-input"
            />
            <Textarea
              placeholder="Description (optional)"
              value={newTask.description}
              onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
              rows={2}
            />
            <div className="grid grid-cols-2 gap-2">
              <SearchableUserSelect
                value={newTask.assignee_id || ''}
                onChange={(v) => setNewTask({ ...newTask, assignee_id: v })}
                users={users}
                placeholder="Assign to…"
                emptyText="No teammates found."
                testId="task-assignee-select"
              />
              <Select value={newTask.priority} onValueChange={(v) => setNewTask({ ...newTask, priority: v })}>
                <SelectTrigger className="h-9" data-testid="task-priority-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Input
              type="datetime-local"
              value={newTask.due_date}
              onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
              data-testid="task-due-input"
            />
            <Select
              value={String(newTask.reminder_minutes_before || 0)}
              onValueChange={(v) => setNewTask({ ...newTask, reminder_minutes_before: parseInt(v, 10) })}
            >
              <SelectTrigger className="h-9" data-testid="task-reminder-select">
                <SelectValue placeholder="No email reminder" />
              </SelectTrigger>
              <SelectContent>
                {REMINDER_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={String(opt.value)}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} disabled={submitting} data-testid="save-task-btn">
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Create'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        )}
        {sorted.length === 0 ? (
          <p className="text-center text-muted-foreground text-sm py-3">No action items yet</p>
        ) : (
          sorted.map((t) => (
            <div
              key={t.id}
              className={`flex items-start gap-2 p-2.5 border rounded-md ${t.status === 'done' ? 'bg-muted/50 opacity-70' : 'bg-card'}`}
              data-testid={`task-row-${t.id}`}
            >
              <button
                type="button"
                onClick={() => handleStatus(t.id, t.status === 'done' ? 'todo' : 'done')}
                className="mt-0.5"
                data-testid={`task-toggle-${t.id}`}
                title={t.status === 'done' ? 'Mark as to-do' : 'Mark done'}
              >
                {t.status === 'done'
                  ? <Check className="w-4 h-4 text-green-600" />
                  : <Circle className="w-4 h-4 text-muted-foreground hover:text-primary" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-muted-foreground' : ''}`}>
                    {t.title}
                  </span>
                  <Badge className={`text-[10px] ${PRIORITY_COLORS[t.priority]}`}>{t.priority}</Badge>
                  {t.status === 'in_progress' && (
                    <Badge variant="outline" className="text-[10px]">In progress</Badge>
                  )}
                </div>
                {t.description && <p className="text-xs text-muted-foreground mt-0.5 break-words">{t.description}</p>}
                <div className="flex gap-3 text-xs text-muted-foreground mt-0.5 flex-wrap">
                  {t.assignee_name && <span>👤 {t.assignee_name}</span>}
                  {t.due_date && <span>📅 {t.due_date.includes('T') ? formatDateTime(t.due_date) : formatDate(t.due_date)}</span>}
                  {t.reminder_minutes_before > 0 && t.status !== 'done' && (
                    <span className="inline-flex items-center gap-0.5">
                      <Bell className="w-3 h-3" />
                      {t.reminder_minutes_before < 60
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
                  <Button size="sm" variant="ghost" className="h-7 px-2">
                    <ChevronDown className="w-3.5 h-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {Object.entries(STATUS_LABELS).map(([k, lbl]) => (
                    <DropdownMenuItem key={k} onClick={() => handleStatus(t.id, k)}>{lbl}</DropdownMenuItem>
                  ))}
                  <DropdownMenuItem onClick={() => handleDelete(t.id)} className="text-rose-600">
                    <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
};

export default TasksCard;
