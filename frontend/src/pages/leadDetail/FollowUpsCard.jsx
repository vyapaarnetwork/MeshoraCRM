import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Calendar } from '../../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  CalendarIcon, Plus, Check, Clock, UserCheck, MoreHorizontal, AlarmClock, Bell,
} from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { format, addDays, addWeeks, addMonths } from 'date-fns';
import api, { formatDate, formatDateTime } from '../../utils/api';
import SearchableUserSelect from '../../components/SearchableUserSelect';

const REMINDER_OPTIONS = [
  { value: 0, label: 'No reminder' },
  { value: 30, label: '30 min before' },
  { value: 60, label: '1 hour before' },
  { value: 120, label: '2 hours before' },
  { value: 240, label: '4 hours before' },
  { value: 1440, label: '1 day before' },
];

const isOverdue = (f) => {
  if (f.is_completed || !f.scheduled_date) return false;
  try {
    // Phase 35 — exact-time follow-ups: compare against the actual datetime
    if (f.scheduled_date.includes('T')) return new Date(f.scheduled_date) < new Date();
    return new Date(f.scheduled_date) < new Date(new Date().toDateString());
  } catch { return false; }
};

const PRESETS = [
  { label: 'Tomorrow', getDate: () => addDays(new Date(), 1) },
  { label: '+3 days', getDate: () => addDays(new Date(), 3) },
  { label: 'Next week', getDate: () => addWeeks(new Date(), 1) },
  { label: '+2 weeks', getDate: () => addWeeks(new Date(), 2) },
  { label: 'Next month', getDate: () => addMonths(new Date(), 1) },
];

export const FollowUpsCard = ({
  followUps = [],
  showFollowUpForm,
  setShowFollowUpForm,
  newFollowUp,
  setNewFollowUp,
  onAdd,
  onComplete,
  onSnooze,
}) => {
  // Phase 30: load assignable users (caller's company peers) for the assignee picker.
  const [assignableUsers, setAssignableUsers] = useState([]);
  useEffect(() => {
    let cancelled = false;
    if (showFollowUpForm) {
      api.get('/users/assignable').then((res) => {
        if (!cancelled) setAssignableUsers(res.data || []);
      }).catch(() => { if (!cancelled) setAssignableUsers([]); });
    }
    return () => { cancelled = true; };
  }, [showFollowUpForm]);
  // sort: overdue first, then pending, then completed; within group by scheduled_date asc
  const sorted = [...followUps].sort((a, b) => {
    const aOver = isOverdue(a), bOver = isOverdue(b);
    if (aOver !== bOver) return aOver ? -1 : 1;
    if (a.is_completed !== b.is_completed) return a.is_completed ? 1 : -1;
    return (a.scheduled_date || '').localeCompare(b.scheduled_date || '');
  });

  return (
    <Card data-testid="followups-section">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-primary" />
            Customer Follow-Ups
          </CardTitle>
          <Button
            size="sm" variant="outline"
            onClick={() => setShowFollowUpForm(!showFollowUpForm)}
            data-testid="add-followup-btn"
          >
            <Plus className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {showFollowUpForm && (
          <div className="p-4 border rounded-lg space-y-3 bg-muted/50 animate-scale-in">
            {/* Quick presets */}
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <Button
                  key={p.label}
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="h-7 text-xs"
                  onClick={() => setNewFollowUp({ ...newFollowUp, date: p.getDate() })}
                  data-testid={`preset-${p.label.toLowerCase().replace(/\s|\+/g, '-')}`}
                >
                  {p.label}
                </Button>
              ))}
            </div>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start">
                  <CalendarIcon className="w-4 h-4 mr-2" />
                  {newFollowUp.date ? format(newFollowUp.date, 'PPP') : 'Pick a date'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={newFollowUp.date}
                  onSelect={(date) => setNewFollowUp({ ...newFollowUp, date })}
                  disabled={(date) => date < new Date()}
                />
              </PopoverContent>
            </Popover>

            {/* Phase 35 — exact-time follow-ups */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Time (optional — enables exact-time reminders)</label>
              <Input
                type="time"
                value={newFollowUp.time || ''}
                onChange={(e) => setNewFollowUp({ ...newFollowUp, time: e.target.value })}
                data-testid="followup-time-input"
              />
            </div>
            <Select
              value={newFollowUp.pending_with}
              onValueChange={(v) => setNewFollowUp({ ...newFollowUp, pending_with: v })}
            >
              <SelectTrigger data-testid="pending-with-select">
                <SelectValue placeholder="Pending with (optional)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="customer">Customer</SelectItem>
                <SelectItem value="selling_partner">Selling Partner</SelectItem>
              </SelectContent>
            </Select>

            {/* Phase 30: assignee picker — who is responsible for doing this follow-up */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Assigned to</label>
              <SearchableUserSelect
                value={newFollowUp.assignee_id || ''}
                onChange={(v) => setNewFollowUp({ ...newFollowUp, assignee_id: v })}
                users={assignableUsers}
                placeholder="Pick a teammate (optional)"
                emptyText="No teammates found in your company."
                testId="followup-assignee-select"
              />
            </div>

            {/* Phase 30: reminder lead-time */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Reminder</label>
              <Select
                value={String(newFollowUp.reminder_minutes_before ?? 120)}
                onValueChange={(v) => setNewFollowUp({ ...newFollowUp, reminder_minutes_before: parseInt(v, 10) })}
              >
                <SelectTrigger data-testid="reminder-select">
                  <SelectValue placeholder="Reminder lead time" />
                </SelectTrigger>
                <SelectContent>
                  {REMINDER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={String(opt.value)}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Textarea
              placeholder="Notes (optional)"
              value={newFollowUp.notes}
              onChange={(e) => setNewFollowUp({ ...newFollowUp, notes: e.target.value })}
              rows={2}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={onAdd} data-testid="save-followup-btn">Schedule</Button>
              <Button size="sm" variant="outline" onClick={() => setShowFollowUpForm(false)}>Cancel</Button>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {sorted.length > 0 ? (
            sorted.map((f) => <FollowUpRow key={f.id} f={f} onComplete={onComplete} onSnooze={onSnooze} />)
          ) : (
            <p className="text-center text-muted-foreground py-4 text-sm">
              No follow-ups scheduled
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

const FollowUpRow = ({ f, onComplete, onSnooze }) => {
  const overdue = isOverdue(f);
  return (
    <div
      className={`p-3 border rounded-lg ${
        f.is_completed ? 'bg-muted/50' :
        overdue ? 'bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900' :
        'bg-white dark:bg-card'
      }`}
      data-testid={`followup-row-${f.id}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {f.is_completed
            ? <Check className="w-4 h-4 text-green-600" />
            : overdue
              ? <AlarmClock className="w-4 h-4 text-rose-600" />
              : <Clock className="w-4 h-4 text-orange-500" />}
          <span className={`font-medium text-sm ${f.is_completed ? 'line-through text-muted-foreground' : ''}`}>
            {f.scheduled_date?.includes('T') ? formatDateTime(f.scheduled_date) : formatDate(f.scheduled_date)}
          </span>
          {overdue && (
            <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-rose-600 text-white">
              Overdue
            </span>
          )}
          {f.snoozed_at && !f.is_completed && (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">snoozed</span>
          )}
        </div>
        {!f.is_completed && (
          <div className="flex items-center gap-1">
            <Button
              size="sm" variant="ghost"
              onClick={() => onComplete(f.id)}
              data-testid={`complete-followup-${f.id}`}
              title="Mark complete"
            >
              <Check className="w-4 h-4" />
            </Button>
            {onSnooze && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="ghost" data-testid={`snooze-followup-${f.id}`} title="Snooze">
                    <MoreHorizontal className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {PRESETS.map((p) => (
                    <DropdownMenuItem
                      key={p.label}
                      onClick={() => onSnooze(f.id, p.getDate())}
                      data-testid={`snooze-to-${p.label.toLowerCase().replace(/\s|\+/g, '-')}-${f.id}`}
                    >
                      <AlarmClock className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                      Snooze to {p.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        )}
      </div>
      {f.pending_with && (
        <div className="flex items-center gap-1 text-xs text-blue-600 mt-1">
          <UserCheck className="w-3 h-3" />
          Pending with: {f.pending_with === 'customer' ? 'Customer' : 'Selling Partner'}
        </div>
      )}
      {f.assignee_name && (
        <div className="flex items-center gap-1 text-xs text-purple-600 mt-1" data-testid={`followup-assignee-${f.id}`}>
          <UserCheck className="w-3 h-3" />
          Assigned to: {f.assignee_name}
        </div>
      )}
      {f.reminder_minutes_before > 0 && !f.is_completed && (
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground mt-1">
          <Bell className="w-3 h-3" />
          Reminder {f.reminder_minutes_before < 60
            ? `${f.reminder_minutes_before} min`
            : f.reminder_minutes_before < 1440
              ? `${Math.round(f.reminder_minutes_before / 60)} hour${f.reminder_minutes_before >= 120 ? 's' : ''}`
              : `${Math.round(f.reminder_minutes_before / 1440)} day${f.reminder_minutes_before >= 2880 ? 's' : ''}`} before
        </div>
      )}
      {f.notes && <p className="text-xs text-muted-foreground mt-1">{f.notes}</p>}
      {f.is_completed && f.completed_at && (
        <p className="text-xs text-green-600 mt-1">
          Completed on {formatDate(f.completed_at)}
        </p>
      )}
    </div>
  );
};

export default FollowUpsCard;
