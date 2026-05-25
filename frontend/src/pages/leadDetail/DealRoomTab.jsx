import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { Switch } from '../../components/ui/switch';
import {
  Users, MessageSquare, CheckCircle2, XCircle, Clock, FileText, Lock, Send,
  ShieldCheck, AlertCircle, Plus, ExternalLink, Eye, Sparkles,
} from 'lucide-react';
import api, { formatCurrency, formatDateTime } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';

const DealRoomTab = ({ leadId, lead, onLeadRefresh }) => {
  const { user, isAdmin, isVyapaarOps, isSellingPartner, isCustomer } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [newApproval, setNewApproval] = useState({ title: '', description: '', assignee_role: 'customer', due_date: '' });
  const [toggling, setToggling] = useState(false);

  const canManage = isAdmin || isVyapaarOps || isSellingPartner;
  // Phase 27 fix (iter 15): keep a local optimistic flag so the UI flips immediately after a successful toggle,
  // even if the parent's lead prop hasn't refetched yet.
  const [localEnabled, setLocalEnabled] = useState(null);
  const enabled = localEnabled !== null ? localEnabled : !!lead?.deal_room_enabled;

  const loadDealRoom = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/leads/${leadId}/deal-room`);
      setData(r.data);
    } catch (e) {
      if (e.response?.status !== 403) toast.error(e.response?.data?.detail || 'Failed to load Deal Room');
      setData(null);
    } finally { setLoading(false); }
  }, [leadId]);

  useEffect(() => {
    if (enabled) loadDealRoom();
    else setLoading(false);
  }, [enabled, loadDealRoom]);

  const toggleDealRoom = async (newEnabled) => {
    setToggling(true);
    try {
      await api.post(`/leads/${leadId}/deal-room/toggle`, { enabled: newEnabled });
      toast.success(newEnabled ? 'Deal Room opened — customer can now collaborate.' : 'Deal Room closed.');
      // Optimistic local update — flip UI immediately
      setLocalEnabled(newEnabled);
      // Re-fetch parent lead so the deal_room_enabled flag propagates AND eagerly load the new view.
      if (onLeadRefresh) await onLeadRefresh();
      if (newEnabled) await loadDealRoom();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Toggle failed');
    } finally { setToggling(false); }
  };

  const postMessage = async () => {
    const content = newMessage.trim();
    if (!content) return;
    setPosting(true);
    try {
      await api.post(`/leads/${leadId}/deal-room/messages`, { content });
      setNewMessage('');
      await loadDealRoom();
      toast.success('Message posted');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to post');
    } finally { setPosting(false); }
  };

  const createApproval = async () => {
    if (!newApproval.title.trim()) {
      toast.error('Title is required');
      return;
    }
    try {
      await api.post(`/leads/${leadId}/approvals`, newApproval);
      setApprovalDialogOpen(false);
      setNewApproval({ title: '', description: '', assignee_role: 'customer', due_date: '' });
      await loadDealRoom();
      toast.success('Approval request sent');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create approval');
    }
  };

  const respondToApproval = async (approvalId, decision, note = '') => {
    try {
      await api.post(`/leads/${leadId}/approvals/${approvalId}/respond`, { decision, note });
      await loadDealRoom();
      toast.success(`Marked ${decision}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to respond');
    }
  };

  // ---------- Render: not enabled state ----------
  if (!enabled) {
    return (
      <Card data-testid="deal-room-disabled-card" className="border-dashed border-violet-200 dark:border-violet-900 bg-gradient-to-br from-violet-50/50 to-indigo-50/50 dark:from-violet-950/20 dark:to-indigo-950/20">
        <CardContent className="py-10 flex flex-col items-center text-center gap-3">
          <span className="p-3 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
            <Users className="w-6 h-6" />
          </span>
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2 justify-center">
              <Sparkles className="w-4 h-4 text-violet-600" /> Collaborative Deal Room
            </h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Open a shared workspace where the customer, selling partner, and Meshora team can chat, approve milestones, and review documents — all in one place.
            </p>
          </div>
          {canManage ? (
            <Button onClick={() => toggleDealRoom(true)} disabled={toggling} className="bg-gradient-to-r from-violet-500 to-indigo-500 text-white hover:opacity-90" data-testid="deal-room-open-btn">
              <ExternalLink className="w-4 h-4 mr-2" />
              {toggling ? 'Opening…' : 'Open Deal Room'}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Lock className="w-3 h-3" /> Deal Room not yet opened by the owner.
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  // ---------- Render: loading ----------
  if (loading) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">Loading Deal Room…</CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const { active_partners, public_comments, approvals, documents, commercial, is_internal_viewer } = data;

  return (
    <div className="space-y-4" data-testid="deal-room-tab">
      {/* Header strip */}
      <Card className="bg-gradient-to-r from-violet-500 to-indigo-500 text-white border-0">
        <CardContent className="py-4 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="p-2 rounded-md bg-white/15">
              <Users className="w-5 h-5" />
            </span>
            <div>
              <h3 className="font-semibold flex items-center gap-2">
                Deal Room
                <Badge variant="outline" className="bg-white/15 text-white border-white/30 text-[10px]">LIVE</Badge>
              </h3>
              <p className="text-xs opacity-90">
                {is_internal_viewer ? 'Customer-visible view · everything below is shared with the customer.' : 'Welcome — you can chat with the team, approve requests, and review documents here.'}
              </p>
            </div>
          </div>
          {canManage && (
            <div className="flex items-center gap-2">
              <Switch checked={enabled} onCheckedChange={toggleDealRoom} disabled={toggling} data-testid="deal-room-toggle-switch" className="data-[state=checked]:bg-emerald-500" />
              <span className="text-xs opacity-90">{enabled ? 'Open' : 'Closed'}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Deal summary + commercial */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card data-testid="deal-room-summary-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="w-4 h-4 text-violet-600" /> Project Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Project" value={data.lead.title} />
            <Row label="Category" value={data.lead.primary_category_name || '—'} />
            <Row label="Status" value={
              <Badge style={{ backgroundColor: data.lead.status_color + '20', color: data.lead.status_color }} className="border-0">
                {data.lead.status_name}
              </Badge>
            } />
            {data.lead.deal_value != null && <Row label="Deal Value" value={formatCurrency(data.lead.deal_value)} />}
            {active_partners.length > 0 && (
              <Row label="Partners" value={
                <div className="flex flex-wrap gap-1.5">
                  {active_partners.map((p, i) => (
                    <Badge key={i} variant="secondary" className="text-[10px]">{p.partner_name}</Badge>
                  ))}
                </div>
              } />
            )}
          </CardContent>
        </Card>

        {commercial && (
          <Card data-testid="deal-room-commercial-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" /> Commercial Agreement
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Type" value={<Badge variant="outline">{commercial.type === 'recurring' ? 'Recurring Contract' : 'One-Time Project'}</Badge>} />
              {commercial.project_value && <Row label="Value" value={`${commercial.currency} ${Number(commercial.project_value).toLocaleString('en-IN')}`} />}
              {commercial.contract_start_date && <Row label="Start" value={commercial.contract_start_date} />}
              {commercial.contract_end_date && <Row label="End" value={commercial.contract_end_date} />}
              {commercial.milestones_count > 0 && <Row label="Milestones" value={`${commercial.milestones_count} planned`} />}
              {commercial.invoices_count > 0 && <Row label="Invoices" value={`${commercial.invoices_count} raised`} />}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Approvals section */}
      <Card data-testid="deal-room-approvals-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Approvals
              {approvals.filter(a => a.status === 'pending').length > 0 && (
                <Badge className="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 ml-1">
                  {approvals.filter(a => a.status === 'pending').length} pending
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">Track formal sign-offs from the customer or selling partner.</CardDescription>
          </div>
          {canManage && (
            <Dialog open={approvalDialogOpen} onOpenChange={setApprovalDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" data-testid="new-approval-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Request Approval
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>New Approval Request</DialogTitle>
                  <DialogDescription>Visible inside the Deal Room. The assignee will receive a notification.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div className="space-y-1.5">
                    <Label>Title</Label>
                    <Input value={newApproval.title} onChange={(e) => setNewApproval({ ...newApproval, title: e.target.value })} placeholder="Approve project scope" data-testid="approval-title-input" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Description (optional)</Label>
                    <Textarea value={newApproval.description} onChange={(e) => setNewApproval({ ...newApproval, description: e.target.value })} rows={3} placeholder="Add context about what's being approved…" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>Assignee</Label>
                      <Select value={newApproval.assignee_role} onValueChange={(v) => setNewApproval({ ...newApproval, assignee_role: v })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="customer">Customer</SelectItem>
                          <SelectItem value="selling_partner">Selling Partner</SelectItem>
                          <SelectItem value="admin">Meshora Admin</SelectItem>
                          <SelectItem value="all">Anyone</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Due date (optional)</Label>
                      <Input type="date" value={newApproval.due_date} onChange={(e) => setNewApproval({ ...newApproval, due_date: e.target.value })} />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setApprovalDialogOpen(false)}>Cancel</Button>
                  <Button onClick={createApproval} data-testid="create-approval-btn">Send Request</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </CardHeader>
        <CardContent>
          {approvals.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No approval requests yet.</p>
          ) : (
            <div className="space-y-2">
              {approvals.map((a) => <ApprovalRow key={a.id} approval={a} currentRole={user?.role} canRespond={canRespondToApproval(a, user)} onRespond={respondToApproval} />)}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Documents section */}
      <Card data-testid="deal-room-documents-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="w-4 h-4 text-sky-600" /> Shared Documents
          </CardTitle>
          <CardDescription className="text-xs">Documents uploaded to this lead are visible to everyone in the Deal Room.</CardDescription>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No documents shared yet.</p>
          ) : (
            <div className="space-y-1.5">
              {documents.map((d) => (
                <div key={d.id} className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/40" data-testid={`deal-room-doc-${d.id}`}>
                  <FileText className="w-4 h-4 text-sky-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{d.original_filename || d.filename}</div>
                    <div className="text-[11px] text-muted-foreground">{d.tag || 'document'} · uploaded by {d.uploaded_by_name} · {d.size_kb ? `${d.size_kb}KB` : ''}</div>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    <Eye className="w-3 h-3 mr-1" /> Visible
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Messages / public thread */}
      <Card data-testid="deal-room-messages-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-violet-600" /> Conversation
            <Badge variant="outline" className="text-[10px] ml-1">{public_comments.length}</Badge>
          </CardTitle>
          <CardDescription className="text-xs">Shared with everyone in the Deal Room. Internal comments stay private on the lead's main thread.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {public_comments.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-2">No messages yet. Be the first to start the conversation.</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {public_comments.map((c) => (
                <div key={c.id} className="p-2.5 rounded-lg border bg-muted/30" data-testid={`deal-room-msg-${c.id}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">{c.user_name}</span>
                    <Badge variant="outline" className="text-[10px] capitalize">{(c.user_role || '').replace(/_/g, ' ')}</Badge>
                    <span className="text-[10px] text-muted-foreground ml-auto">{formatDateTime(c.created_at)}</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{c.content}</p>
                </div>
              ))}
            </div>
          )}
          <div className="border-t pt-3 space-y-2">
            <Textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              rows={2}
              placeholder={isCustomer ? "Share an update or ask a question…" : "Send a message visible to everyone in the Deal Room…"}
              data-testid="deal-room-message-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); postMessage(); }
              }}
            />
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Visible to customer, partners, and Meshora team. Press ⌘+Enter to send.
              </span>
              <Button size="sm" onClick={postMessage} disabled={!newMessage.trim() || posting} data-testid="deal-room-send-btn">
                <Send className="w-3.5 h-3.5 mr-1.5" /> {posting ? 'Sending…' : 'Send'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const canRespondToApproval = (approval, user) => {
  if (!user || approval.status !== 'pending') return false;
  if (user.role === 'super_admin' || user.is_vyapaar_ops) return true;
  if (approval.assignee_role === 'all') return true;
  if (approval.assignee_role === 'customer' && user.role === 'customer') return true;
  if (approval.assignee_role === 'selling_partner' && user.role === 'selling_partner') return true;
  if (approval.assignee_role === 'admin' && (user.role === 'super_admin' || user.is_vyapaar_ops)) return true;
  return false;
};

const ApprovalRow = ({ approval, canRespond, onRespond }) => {
  const statusCls = {
    pending: 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
    approved: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
    rejected: 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300',
  }[approval.status] || 'bg-slate-100 text-slate-800';
  const Icon = approval.status === 'approved' ? CheckCircle2 : approval.status === 'rejected' ? XCircle : Clock;
  return (
    <div className="p-3 rounded-lg border" data-testid={`approval-${approval.id}`}>
      <div className="flex items-start gap-3">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${approval.status === 'approved' ? 'text-emerald-600' : approval.status === 'rejected' ? 'text-rose-600' : 'text-amber-600'}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{approval.title}</span>
            <Badge className={`text-[10px] ${statusCls}`}>{approval.status}</Badge>
            <Badge variant="outline" className="text-[10px] capitalize">for {approval.assignee_role.replace(/_/g, ' ')}</Badge>
            {approval.due_date && <Badge variant="outline" className="text-[10px]">Due {approval.due_date}</Badge>}
          </div>
          {approval.description && <p className="text-xs text-muted-foreground mt-1">{approval.description}</p>}
          <div className="text-[10px] text-muted-foreground mt-1">
            Requested by {approval.created_by_name} · {formatDateTime(approval.created_at)}
          </div>
          {approval.responded_at && (
            <div className="mt-1.5 text-xs p-1.5 rounded bg-muted/40">
              <span className="font-medium capitalize">{approval.decision}</span> by {approval.responded_by_name} · {formatDateTime(approval.responded_at)}
              {approval.decision_note && <div className="mt-0.5 italic text-muted-foreground">"{approval.decision_note}"</div>}
            </div>
          )}
          {canRespond && approval.status === 'pending' && (
            <div className="flex gap-2 mt-2">
              <Button size="sm" onClick={() => onRespond(approval.id, 'approved')} className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs" data-testid={`approve-${approval.id}`}>
                <CheckCircle2 className="w-3 h-3 mr-1" /> Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => onRespond(approval.id, 'rejected')} className="h-7 text-xs" data-testid={`reject-${approval.id}`}>
                <XCircle className="w-3 h-3 mr-1" /> Reject
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Row = ({ label, value }) => (
  <div className="flex items-center gap-3">
    <span className="text-xs text-muted-foreground w-20 shrink-0">{label}</span>
    <span className="text-sm">{value}</span>
  </div>
);

export default DealRoomTab;
