import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import { Plus, Loader2, Pencil, Trash2, Percent } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const TaxRates = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', percent: 0, is_inclusive: false, is_default: false, is_active: true, sort_order: 99 });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/tax-rates?include_inactive=true');
      setItems(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load tax rates');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openCreate = () => {
    setEditing(null);
    setForm({ name: '', percent: 0, is_inclusive: false, is_default: false, is_active: true, sort_order: (items.length || 0) + 1 });
    setShowForm(true);
  };
  const openEdit = (r) => {
    setEditing(r);
    setForm({
      name: r.name, percent: r.percent ?? 0,
      is_inclusive: !!r.is_inclusive, is_default: !!r.is_default,
      is_active: r.is_active !== false, sort_order: r.sort_order ?? 99,
    });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        percent: Number(form.percent || 0),
        is_inclusive: form.is_inclusive,
        is_default: form.is_default,
        is_active: form.is_active,
        sort_order: Number(form.sort_order || 99),
      };
      if (editing) await api.patch(`/tax-rates/${editing.id}`, payload);
      else await api.post('/tax-rates', payload);
      toast.success(editing ? 'Tax rate updated' : 'Tax rate created');
      setShowForm(false);
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const remove = async (r) => {
    if (!window.confirm(`Delete "${r.name}"? Commercials already using it keep the reference.`)) return;
    try {
      const res = await api.delete(`/tax-rates/${r.id}`);
      toast.success(res.data?.deactivated ? `Deactivated — used by ${res.data.commercials + res.data.invoices} record(s)` : 'Tax rate deleted');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  return (
    <div className="space-y-5" data-testid="tax-rates-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Percent className="w-6 h-6 text-primary" />
            Tax Rates
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configurable flat-% tax master applied to each Commercial. Marked as default for new commercials.
          </p>
        </div>
        <Button onClick={openCreate} className="gap-2" data-testid="new-tax-rate-btn">
          <Plus className="w-4 h-4" /> New tax rate
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>Rates ({items.length})</span>
            {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {items.length === 0 && !loading ? (
            <p className="text-sm text-muted-foreground text-center py-8">No tax rates yet.</p>
          ) : items.map((r) => (
            <div key={r.id} className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/40" data-testid={`tax-row-${r.id}`}>
              <Percent className="w-3.5 h-3.5 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">{r.name}</span>
                  <Badge className="text-[10px]" variant="secondary">{r.percent}%</Badge>
                  {r.is_inclusive && <Badge className="text-[10px]" variant="outline">Inclusive</Badge>}
                  {r.is_default && <Badge className="text-[10px] bg-violet-600 text-white">Default</Badge>}
                  {!r.is_active && <Badge variant="outline" className="text-[10px]">Inactive</Badge>}
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => openEdit(r)} data-testid={`edit-${r.id}`}>
                <Pencil className="w-3.5 h-3.5" />
              </Button>
              <Button size="sm" variant="ghost" className="text-rose-600" onClick={() => remove(r)} data-testid={`delete-${r.id}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent data-testid="tax-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit tax rate' : 'New tax rate'}</DialogTitle>
            <DialogDescription>Flat % applied on invoices and commercial totals.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Name <span className="text-rose-500">*</span></Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. GST 18%, VAT 5%"
                data-testid="tax-name-input"
              />
            </div>
            <div>
              <Label className="text-xs">Percent</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={form.percent}
                onChange={(e) => setForm({ ...form, percent: e.target.value })}
                data-testid="tax-percent-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Sort order</Label>
                <Input
                  type="number"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-2 pt-5">
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_active} onCheckedChange={(v) => setForm({ ...form, is_active: v })} />
                  Active
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_default} onCheckedChange={(v) => setForm({ ...form, is_default: v })} />
                  Default
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_inclusive} onCheckedChange={(v) => setForm({ ...form, is_inclusive: v })} />
                  Tax-inclusive amount
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="tax-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editing ? 'Save changes' : 'Create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TaxRates;
