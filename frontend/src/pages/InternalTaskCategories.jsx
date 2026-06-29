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
import { Plus, Loader2, Pencil, Trash2, ListTodo, GripVertical } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const PRESET_COLORS = ['#4f46e5', '#7c3aed', '#06b6d4', '#059669', '#f59e0b', '#dc2626', '#64748b', '#ec4899'];

const InternalTaskCategories = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', color: '#4f46e5', is_active: true, is_default: false, sort_order: 99 });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/internal-task-categories?include_inactive=true');
      setItems(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load categories');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openCreate = () => {
    setEditing(null);
    setForm({ name: '', color: '#4f46e5', is_active: true, is_default: false, sort_order: (items.length || 0) + 1 });
    setShowForm(true);
  };
  const openEdit = (cat) => {
    setEditing(cat);
    setForm({
      name: cat.name || '',
      color: cat.color || '#4f46e5',
      is_active: cat.is_active !== false,
      is_default: !!cat.is_default,
      sort_order: cat.sort_order ?? 99,
    });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        color: form.color,
        is_active: form.is_active,
        is_default: form.is_default,
        sort_order: Number(form.sort_order || 99),
      };
      if (editing) await api.patch(`/internal-task-categories/${editing.id}`, payload);
      else await api.post('/internal-task-categories', payload);
      toast.success(editing ? 'Category updated' : 'Category created');
      setShowForm(false);
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const remove = async (cat) => {
    if (!window.confirm(`Delete "${cat.name}"? Tasks already using it will keep the reference.`)) return;
    try {
      const r = await api.delete(`/internal-task-categories/${cat.id}`);
      toast.success(r.data?.deactivated ? `Deactivated — ${r.data.in_use} task(s) still reference it` : 'Category deleted');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  return (
    <div className="space-y-5" data-testid="internal-task-categories-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ListTodo className="w-6 h-6 text-primary" />
            Internal Task Categories
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Master list used by the Internal Tasks dropdown. Mark one as default for new tasks.
          </p>
        </div>
        <Button onClick={openCreate} className="gap-2" data-testid="new-category-btn">
          <Plus className="w-4 h-4" /> New category
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>Categories ({items.length})</span>
            {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {items.length === 0 && !loading ? (
            <p className="text-sm text-muted-foreground text-center py-8">No categories yet. Click "New category" to add one.</p>
          ) : items.map((c) => (
            <div key={c.id} className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/40" data-testid={`category-row-${c.id}`}>
              <GripVertical className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="w-3 h-3 rounded-full shrink-0" style={{ background: c.color || '#4f46e5' }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">{c.name}</span>
                  {c.is_default && <Badge className="text-[10px] bg-violet-600 text-white">Default</Badge>}
                  {!c.is_active && <Badge variant="outline" className="text-[10px]">Inactive</Badge>}
                  <span className="text-[11px] text-muted-foreground">order: {c.sort_order}</span>
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => openEdit(c)} data-testid={`edit-${c.id}`}>
                <Pencil className="w-3.5 h-3.5" />
              </Button>
              <Button size="sm" variant="ghost" className="text-rose-600" onClick={() => remove(c)} data-testid={`delete-${c.id}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent data-testid="category-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit category' : 'New category'}</DialogTitle>
            <DialogDescription>Master entry surfaced in the Internal Tasks form.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Name <span className="text-rose-500">*</span></Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="cat-name-input" />
            </div>
            <div>
              <Label className="text-xs">Color</Label>
              <div className="flex items-center gap-2 mt-1">
                {PRESET_COLORS.map((c) => (
                  <button
                    type="button"
                    key={c}
                    onClick={() => setForm((p) => ({ ...p, color: c }))}
                    className={`w-7 h-7 rounded-full border-2 transition-all ${form.color === c ? 'border-foreground scale-110' : 'border-transparent'}`}
                    style={{ background: c }}
                    aria-label={`Pick ${c}`}
                  />
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Sort order</Label>
                <Input
                  type="number"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                  data-testid="cat-sort-input"
                />
              </div>
              <div className="flex flex-col gap-2 pt-5">
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_active} onCheckedChange={(v) => setForm({ ...form, is_active: v })} data-testid="cat-active-switch" />
                  Active
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_default} onCheckedChange={(v) => setForm({ ...form, is_default: v })} data-testid="cat-default-switch" />
                  Default for new tasks
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="cat-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editing ? 'Save changes' : 'Create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default InternalTaskCategories;
