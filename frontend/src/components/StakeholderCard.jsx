import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from './ui/dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from './ui/dropdown-menu';
import {
  Users2, UserPlus, Mail, Phone, MoreHorizontal, Edit, Trash2, ShieldCheck,
  Crown, Wrench, DollarSign, Ban, Star, User,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const ROLE_META = {
  decision_maker: { label: 'Decision Maker', icon: Crown, cls: 'bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300' },
  influencer: { label: 'Influencer', icon: ShieldCheck, cls: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300' },
  technical_evaluator: { label: 'Tech Evaluator', icon: Wrench, cls: 'bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300' },
  finance_approver: { label: 'Finance Approver', icon: DollarSign, cls: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300' },
  blocker: { label: 'Blocker', icon: Ban, cls: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300' },
  champion: { label: 'Champion', icon: Star, cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' },
  end_user: { label: 'End User', icon: User, cls: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300' },
  other: { label: 'Other', icon: User, cls: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300' },
};
const ENGAGEMENT_META = {
  supportive: { label: 'Supportive', cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900' },
  neutral: { label: 'Neutral', cls: 'bg-slate-50 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300 border-slate-200 dark:border-slate-800' },
  resistant: { label: 'Resistant', cls: 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300 border-rose-200 dark:border-rose-900' },
  unknown: { label: 'Unknown', cls: 'bg-slate-50 text-slate-500 dark:bg-slate-900/30 dark:text-slate-400 border-slate-200 dark:border-slate-800' },
};

const EMPTY_FORM = {
  name: '', role_type: 'decision_maker', email: '', phone: '', title: '', notes: '', engagement: 'neutral',
};

const StakeholderCard = ({ leadId, canEdit = true }) => {
  const [stakeholders, setStakeholders] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const fetch = useCallback(async () => {
    try {
      const r = await api.get(`/leads/${leadId}/stakeholders`);
      setStakeholders(r.data || []);
    } catch (e) { /* noop */ }
  }, [leadId]);

  useEffect(() => { fetch(); }, [fetch]);

  const openCreate = () => { setEditing(null); setForm(EMPTY_FORM); setDialogOpen(true); };
  const openEdit = (s) => { setEditing(s); setForm({ ...EMPTY_FORM, ...s }); setDialogOpen(true); };

  const handleSubmit = async () => {
    if (!form.name?.trim()) return toast.error('Name is required');
    setSubmitting(true);
    try {
      if (editing) {
        await api.patch(`/leads/${leadId}/stakeholders/${editing.id}`, form);
        toast.success('Stakeholder updated');
      } else {
        await api.post(`/leads/${leadId}/stakeholders`, form);
        toast.success('Stakeholder added');
      }
      setDialogOpen(false);
      fetch();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this stakeholder?')) return;
    try {
      await api.delete(`/leads/${leadId}/stakeholders/${id}`);
      toast.success('Stakeholder removed');
      fetch();
    } catch (e) { toast.error('Delete failed'); }
  };

  return (
    <Card data-testid="stakeholders-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Users2 className="w-5 h-5 text-violet-600" />
              Stakeholders ({stakeholders.length})
            </CardTitle>
            <CardDescription>Map decision-makers, champions, blockers & evaluators</CardDescription>
          </div>
          {canEdit && (
            <Button size="sm" variant="outline" onClick={openCreate} data-testid="add-stakeholder-btn">
              <UserPlus className="w-4 h-4 mr-1" />Add
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {stakeholders.length === 0 ? (
          <p className="text-center text-muted-foreground text-sm py-3">No stakeholders mapped yet</p>
        ) : (
          <div className="space-y-2">
            {stakeholders.map((s) => {
              const rm = ROLE_META[s.role_type] || ROLE_META.other;
              const em = ENGAGEMENT_META[s.engagement] || ENGAGEMENT_META.neutral;
              const Icon = rm.icon;
              return (
                <div key={s.id} className="flex items-start gap-3 p-3 border rounded-lg bg-card" data-testid={`stakeholder-${s.id}`}>
                  <div className={`shrink-0 p-2 rounded-md ${rm.cls.replace('text-', 'text-')}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
                      <span className="font-medium text-sm">{s.name}</span>
                      <Badge className={`text-[10px] ${rm.cls}`}>{rm.label}</Badge>
                      <Badge variant="outline" className={`text-[10px] ${em.cls}`}>{em.label}</Badge>
                    </div>
                    {s.title && <div className="text-xs text-muted-foreground">{s.title}</div>}
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
                      {s.email && <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{s.email}</span>}
                      {s.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{s.phone}</span>}
                    </div>
                    {s.notes && <p className="text-xs text-muted-foreground mt-1 italic">"{s.notes}"</p>}
                  </div>
                  {canEdit && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="ghost" className="h-7 px-2">
                          <MoreHorizontal className="w-3.5 h-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEdit(s)}>
                          <Edit className="w-3.5 h-3.5 mr-1.5" />Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDelete(s.id)} className="text-rose-600">
                          <Trash2 className="w-3.5 h-3.5 mr-1.5" />Remove
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Stakeholder' : 'Add Stakeholder'}</DialogTitle>
            <DialogDescription>Map who matters in this deal and how they feel about it.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="stakeholder-name-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Role</Label>
                <Select value={form.role_type} onValueChange={(v) => setForm({ ...form, role_type: v })}>
                  <SelectTrigger data-testid="stakeholder-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROLE_META).map(([k, m]) => (
                      <SelectItem key={k} value={k}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Engagement</Label>
                <Select value={form.engagement} onValueChange={(v) => setForm({ ...form, engagement: v })}>
                  <SelectTrigger data-testid="stakeholder-engagement-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(ENGAGEMENT_META).map(([k, m]) => (
                      <SelectItem key={k} value={k}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <Label>Title</Label>
              <Input value={form.title || ''} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. VP Sales" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Email</Label>
                <Input type="email" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="space-y-1">
                <Label>Phone</Label>
                <Input value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Notes</Label>
              <Textarea rows={2} value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="What we know about them…" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="save-stakeholder-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default StakeholderCard;
