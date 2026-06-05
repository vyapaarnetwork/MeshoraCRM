import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { CalendarRange, Plus, Loader2, Trash2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const FREQ_LABEL = { daily: 'Daily', weekly: 'Weekly (Mondays)', monthly: 'Monthly (1st)' };

const ScheduledReports = () => {
  const [rows, setRows] = useState([]);
  const [saved, setSaved] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [savedReportId, setSavedReportId] = useState('');
  const [frequency, setFrequency] = useState('weekly');
  const [recipientsInput, setRecipientsInput] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        api.get('/reports/scheduled'),
        api.get('/reports/saved'),
      ]);
      setRows(r1.data);
      setSaved(r2.data);
    } catch (e) {
      const msg = e.response?.data?.detail || 'Failed to load scheduled reports';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const create = async () => {
    if (!savedReportId) { toast.error('Pick a saved report first'); return; }
    const recipients = recipientsInput.split(/[\s,;]+/).filter(Boolean);
    if (recipients.length === 0) { toast.error('At least one recipient email is required'); return; }
    setSaving(true);
    try {
      await api.post('/reports/scheduled', {
        saved_report_id: savedReportId,
        frequency,
        recipients,
        enabled: true,
      });
      toast.success('Schedule created');
      setOpen(false);
      setSavedReportId('');
      setRecipientsInput('');
      setFrequency('weekly');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create schedule');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this schedule?')) return;
    try {
      await api.delete(`/reports/scheduled/${id}`);
      toast.success('Deleted');
      fetchAll();
    } catch (e) {
      toast.error('Delete failed');
    }
  };

  return (
    <div className="space-y-6 p-1" data-testid="scheduled-reports">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-sky-100 to-indigo-100 dark:from-sky-950/40 dark:to-indigo-950/40">
            <CalendarRange className="w-6 h-6 text-sky-700 dark:text-sky-300" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Scheduled Reports</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Email reports on a recurring cadence</p>
          </div>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="new-schedule-btn">
          <Plus className="w-4 h-4 mr-2" /> New Schedule
        </Button>
      </div>

      <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
        <CardContent className="py-3 text-xs text-amber-800 dark:text-amber-200">
          ⚠ Heads up — schedule dispatch will land in a follow-up release. For now this page lets your team
          set up the cadence + recipient list so we know exactly what to wire when the cron lands.
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <CalendarRange className="w-10 h-10 mx-auto opacity-30 mb-2" />
            <p>No scheduled reports yet.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {rows.map((r) => (
            <Card key={r.id} data-testid={`schedule-row-${r.id}`}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-base">{r.saved_report?.name || '—'}</CardTitle>
                    <CardDescription className="text-xs flex items-center gap-2 mt-1">
                      <Badge variant="outline">{FREQ_LABEL[r.frequency] || r.frequency}</Badge>
                      {r.enabled ? <Badge className="bg-emerald-100 text-emerald-700">Enabled</Badge> : <Badge variant="secondary">Disabled</Badge>}
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => remove(r.id)} className="text-rose-600 hover:text-rose-700" data-testid={`schedule-delete-${r.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground mb-1">Recipients ({r.recipients?.length || 0})</p>
                <div className="flex flex-wrap gap-1">
                  {(r.recipients || []).map((email) => (
                    <Badge key={email} variant="outline" className="text-[10px]">{email}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule a recurring report</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="sched-report">Saved Report</Label>
              <Select value={savedReportId} onValueChange={setSavedReportId}>
                <SelectTrigger id="sched-report" data-testid="sched-saved-select">
                  <SelectValue placeholder={saved.length === 0 ? 'No saved reports yet — create one in My Reports first' : 'Pick a saved report'} />
                </SelectTrigger>
                <SelectContent>
                  {saved.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sched-freq">Frequency</Label>
              <Select value={frequency} onValueChange={setFrequency}>
                <SelectTrigger id="sched-freq" data-testid="sched-freq-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly (Mondays 9am IST)</SelectItem>
                  <SelectItem value="monthly">Monthly (1st of month 9am IST)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sched-recipients">Recipient emails</Label>
              <Input
                id="sched-recipients"
                placeholder="alice@example.com, bob@example.com"
                value={recipientsInput}
                onChange={(e) => setRecipientsInput(e.target.value)}
                data-testid="sched-recipients-input"
              />
              <p className="text-[11px] text-muted-foreground">Comma- or space-separated emails.</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={create} disabled={saving} data-testid="sched-save-btn">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
              Create Schedule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ScheduledReports;
