import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Save as SaveIcon, Trash2, Plus, Loader2, ArrowUpRight } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const REPORT_TYPES = [
  { value: 'won_leads',          label: 'Won Leads',          route: '/reports/won-leads' },
  { value: 'pipeline',           label: 'Pipeline',           route: '/reports/pipeline' },
  { value: 'conversion',         label: 'Conversion',         route: '/reports/conversion' },
  { value: 'partner_performance',label: 'Partner Performance', route: '/reports/partner-performance' },
  { value: 'lead_activity',      label: 'Lead Activity',      route: '/reports/lead-activity' },
];

const SavedReports = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [reportType, setReportType] = useState('won_leads');
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const fetchRows = async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/saved');
      setRows(res.data);
    } catch (e) {
      toast.error('Failed to load saved reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRows(); }, []);

  const save = async () => {
    if (!name.trim()) { toast.error('Name is required'); return; }
    setSaving(true);
    try {
      await api.post('/reports/saved', { name: name.trim(), report_type: reportType, config: {} });
      toast.success('Saved!');
      setOpen(false);
      setName('');
      setReportType('won_leads');
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this saved report? Any schedules tied to it will also be removed.')) return;
    try {
      await api.delete(`/reports/saved/${id}`);
      toast.success('Deleted');
      fetchRows();
    } catch (e) {
      toast.error('Delete failed');
    }
  };

  const openReport = (row) => {
    const meta = REPORT_TYPES.find(r => r.value === row.report_type);
    if (meta) navigate(meta.route);
    else toast.error('Unknown report type');
  };

  return (
    <div className="space-y-6 p-1" data-testid="saved-reports">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-950/40 dark:to-fuchsia-950/40">
            <SaveIcon className="w-6 h-6 text-violet-700 dark:text-violet-300" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">My Reports</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Quick-access shortcuts to your favourite reports</p>
          </div>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="new-saved-report-btn">
              <Plus className="w-4 h-4 mr-2" />New Saved Report
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Save a report shortcut</DialogTitle>
              <CardDescription>Pin one of the existing reports for one-click access.</CardDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="sr-name">Name</Label>
                <Input id="sr-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q1 Won Leads" data-testid="saved-name-input" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sr-type">Report Type</Label>
                <Select value={reportType} onValueChange={setReportType}>
                  <SelectTrigger id="sr-type" data-testid="saved-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {REPORT_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={save} disabled={saving} data-testid="saved-save-btn">
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <SaveIcon className="w-4 h-4 mr-2" />}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <SaveIcon className="w-10 h-10 mx-auto opacity-30 mb-2" />
            <p>No saved reports yet. Click <strong>New Saved Report</strong> to pin one.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {rows.map((r) => {
            const meta = REPORT_TYPES.find(t => t.value === r.report_type);
            return (
              <Card key={r.id} className="hover:border-violet-300 transition-colors" data-testid={`saved-row-${r.id}`}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle className="text-base">{r.name}</CardTitle>
                      <CardDescription className="text-xs">{meta?.label || r.report_type}</CardDescription>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => remove(r.id)} className="text-rose-600 hover:text-rose-700" data-testid={`saved-delete-${r.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Button variant="outline" className="w-full" onClick={() => openReport(r)} data-testid={`saved-open-${r.id}`}>
                    <ArrowUpRight className="w-4 h-4 mr-2" /> Open Report
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SavedReports;
