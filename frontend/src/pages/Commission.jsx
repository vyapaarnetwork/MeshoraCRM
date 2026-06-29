import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Plus, Edit, Trash2, Percent, Loader2 } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import api from '../utils/api';
import { toast } from 'sonner';

const Commission = () => {
  const { isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({ name: '', vyapaar_percentage: '', description: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await api.get('/master/commission-templates');
      setTemplates(response.data);
    } catch (error) {
      toast.error('Failed to load commission templates');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (item = null) => {
    setEditingItem(item);
    setFormData(item ? {
      name: item.name,
      vyapaar_percentage: item.vyapaar_percentage.toString(),
      description: item.description || ''
    } : { name: '', vyapaar_percentage: '', description: '' });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.vyapaar_percentage) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        vyapaar_percentage: parseFloat(formData.vyapaar_percentage),
        description: formData.description || null
      };

      if (editingItem) {
        await api.put(`/master/commission-templates/${editingItem.id}`, payload);
        toast.success('Template updated successfully');
      } else {
        await api.post('/master/commission-templates', payload);
        toast.success('Template created successfully');
      }

      fetchTemplates();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this template?')) return;

    try {
      await api.delete(`/master/commission-templates/${id}`);
      toast.success('Template deleted successfully');
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to delete template');
    }
  };

  if (loading) return <CommissionSkeleton />;

  return (
    <div className="space-y-6" data-testid="commission-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Commission Templates</h1>
        <p className="text-muted-foreground mt-1">
          Manage commission percentage templates for partners
        </p>
      </div>

      {/* Info Card */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Percent className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold mb-1">How Commission Works</h3>
              <p className="text-sm text-muted-foreground">
                Commission templates define the percentage Vyapaar Network earns from each deal. 
                These templates can be applied to selling partners, and can be overridden at the individual lead level.
                Sales Associates or Selling Partners can be set as the lead's referrer, and earn a percentage of Vyapaar's share when they refer a lead.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Phase 36.3 — Two tabs: Vyapaar Templates + Referral Levels */}
      <Tabs defaultValue="templates" className="w-full" data-testid="commission-tabs">
        <TabsList>
          <TabsTrigger value="templates" data-testid="tab-vyapaar-templates">Vyapaar Commission Templates</TabsTrigger>
          <TabsTrigger value="referral" data-testid="tab-referral-levels">Referral Commission Levels</TabsTrigger>
        </TabsList>
        <TabsContent value="templates" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Percent className="w-5 h-5 text-primary" />
                  Commission Templates
                </CardTitle>
            <CardDescription>
              Pre-defined commission rates for different partner tiers
            </CardDescription>
          </div>
          <Button onClick={() => openDialog()} data-testid="add-template-btn">
            <Plus className="w-4 h-4 mr-2" />
            Add Template
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Template Name</TableHead>
                <TableHead>Vyapaar Commission</TableHead>
                <TableHead>Partner Share</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.map((template) => (
                <TableRow key={template.id} data-testid={`template-row-${template.id}`}>
                  <TableCell className="font-medium">{template.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-primary/10 text-primary">
                      {template.vyapaar_percentage}%
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-green-100 text-green-700">
                      {100 - template.vyapaar_percentage}%
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {template.description || '-'}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => openDialog(template)}
                        data-testid={`edit-template-${template.id}`}
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => handleDelete(template.id)}
                        className="text-destructive"
                        data-testid={`delete-template-${template.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {templates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    No commission templates found. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {/* /Vyapaar Commission Templates */}
        </TabsContent>

        {/* === Phase 36.3 — Referral Commission Levels === */}
        <TabsContent value="referral" className="mt-4">
          <ReferralCommissionsTab />
        </TabsContent>
      </Tabs>

      {/* Example Calculation */}
      <Card>
        <CardHeader>
          <CardTitle>Commission Calculation Example</CardTitle>
          <CardDescription>How commissions are distributed on a ₹1,00,000 deal</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Template</TableHead>
                  <TableHead className="text-right">Deal Value</TableHead>
                  <TableHead className="text-right">Vyapaar Gets</TableHead>
                  <TableHead className="text-right">Partner Gets</TableHead>
                  <TableHead className="text-right">SA Gets (10% of Vyapaar)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.map((template) => {
                  const dealValue = 100000;
                  const vyapaarShare = dealValue * (template.vyapaar_percentage / 100);
                  const partnerShare = dealValue - vyapaarShare;
                  const saShare = vyapaarShare * 0.1;
                  
                  return (
                    <TableRow key={template.id}>
                      <TableCell className="font-medium">{template.name}</TableCell>
                      <TableCell className="text-right">₹1,00,000</TableCell>
                      <TableCell className="text-right text-primary font-medium">
                        ₹{vyapaarShare.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right text-green-600 font-medium">
                        ₹{partnerShare.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right text-purple-600 font-medium">
                        ₹{saShare.toLocaleString('en-IN')}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingItem ? 'Edit' : 'Add'} Commission Template
            </DialogTitle>
            <DialogDescription>
              Define a commission percentage for partners
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Template Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Standard, Premium Partner"
                data-testid="template-name-input"
              />
            </div>
            <div className="space-y-2">
              <Label>Vyapaar Commission Percentage *</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.vyapaar_percentage}
                  onChange={(e) => setFormData({ ...formData, vyapaar_percentage: e.target.value })}
                  placeholder="15"
                  data-testid="template-percentage-input"
                />
                <span className="text-muted-foreground">%</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Partner will receive {100 - (parseFloat(formData.vyapaar_percentage) || 0)}% of deal value
              </p>
            </div>
            <div className="space-y-2">
              <Label>Description (Optional)</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of this template"
                data-testid="template-description-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="template-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Template'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const CommissionSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-64 mb-2" />
      <Skeleton className="h-4 w-48" />
    </div>
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="h-20 w-full" />
      </CardContent>
    </Card>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48 mb-2" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default Commission;

// ----------------------------------------------------------------------------
// Phase 36.3 — Referral Commission Levels tab (rendered inside Commission.jsx)
// ----------------------------------------------------------------------------
const ReferralCommissionsTab = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', percent: 0, meaning: '', is_active: true, is_default: false, sort_order: 99 });

  const fetchAll = async () => {
    setLoading(true);
    try {
      const r = await api.get('/referral-commissions?include_inactive=true');
      setItems(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load referral levels');
    } finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []);

  const open = (rc = null) => {
    setEditing(rc);
    setForm(rc ? {
      name: rc.name, percent: rc.percent, meaning: rc.meaning || '',
      is_active: rc.is_active !== false, is_default: !!rc.is_default,
      sort_order: rc.sort_order ?? 99,
    } : { name: '', percent: 0, meaning: '', is_active: true, is_default: false, sort_order: items.length + 1 });
    setDialogOpen(true);
  };
  const submit = async () => {
    if (!form.name.trim()) return toast.error('Name is required');
    setSaving(true);
    try {
      const payload = { ...form, percent: parseFloat(form.percent) || 0, sort_order: parseInt(form.sort_order, 10) || 99 };
      if (editing) await api.patch(`/referral-commissions/${editing.id}`, payload);
      else await api.post('/referral-commissions', payload);
      toast.success(editing ? 'Level updated' : 'Level created');
      setDialogOpen(false);
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };
  const remove = async (rc) => {
    if (!window.confirm(`Delete "${rc.name}"?`)) return;
    try {
      const r = await api.delete(`/referral-commissions/${rc.id}`);
      toast.success(r.data?.deactivated ? `Deactivated — ${r.data.in_use} lead(s) still reference it` : 'Level deleted');
      fetchAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  return (
    <>
      <Card className="bg-indigo-50/40 dark:bg-indigo-950/20 border-indigo-200/60 dark:border-indigo-900/60 mb-3">
        <CardContent className="pt-5">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/40 rounded-md">
              <Percent className="w-5 h-5 text-indigo-600 dark:text-indigo-300" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">5-tier Referral Commission</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Each lead can be tagged with one level. The picked % is what Vyapaar pays back to the referrer (sales associate / selling partner) on closure.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Percent className="w-5 h-5 text-indigo-600" />
              Referral Commission Levels
            </CardTitle>
            <CardDescription>5 tiers, from Lead Scout (10%) to Strategic Partner (50%).</CardDescription>
          </div>
          <Button onClick={() => open()} data-testid="add-referral-btn">
            <Plus className="w-4 h-4 mr-2" /> Add Level
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">Order</TableHead>
                <TableHead>Level</TableHead>
                <TableHead className="w-[110px]">Commission</TableHead>
                <TableHead>Meaning</TableHead>
                <TableHead className="w-[140px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((rc) => (
                <TableRow key={rc.id} data-testid={`referral-row-${rc.id}`}>
                  <TableCell className="text-muted-foreground">{rc.sort_order}</TableCell>
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      {rc.name}
                      {rc.is_default && <Badge className="text-[10px] bg-indigo-600 text-white">Default</Badge>}
                      {!rc.is_active && <Badge variant="outline" className="text-[10px]">Inactive</Badge>}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">{rc.percent}%</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">{rc.meaning || '-'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" onClick={() => open(rc)} data-testid={`edit-referral-${rc.id}`}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button size="icon" variant="ghost" onClick={() => remove(rc)} className="text-destructive" data-testid={`delete-referral-${rc.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">No referral levels yet.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="referral-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit referral level' : 'New referral level'}</DialogTitle>
            <DialogDescription>Used by the Lead form's Referral Commission dropdown.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Level name <span className="text-rose-500">*</span></Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="ref-name" placeholder="e.g. Lead Scout" />
            </div>
            <div>
              <Label className="text-xs">Commission %</Label>
              <Input type="number" step="0.01" min="0" max="100" value={form.percent} onChange={(e) => setForm({ ...form, percent: e.target.value })} data-testid="ref-percent" />
            </div>
            <div>
              <Label className="text-xs">Meaning</Label>
              <Input value={form.meaning} onChange={(e) => setForm({ ...form, meaning: e.target.value })} placeholder="What does this level mean?" data-testid="ref-meaning" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Sort order</Label>
                <Input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: e.target.value })} />
              </div>
              <div className="flex flex-col gap-2 pt-5">
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_active} onCheckedChange={(v) => setForm({ ...form, is_active: v })} /> Active
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={form.is_default} onCheckedChange={(v) => setForm({ ...form, is_default: v })} /> Default for new leads
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={submit} disabled={saving} data-testid="ref-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editing ? 'Save' : 'Create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

