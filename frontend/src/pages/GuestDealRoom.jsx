import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import {
  Users, MessageSquare, CheckCircle2, XCircle, Clock, FileText, Send, ShieldCheck,
  AlertCircle, Sparkles, Lock,
} from 'lucide-react';
import { toast, Toaster } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const formatDateTime = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch (e) { return iso; }
};

const GuestDealRoom = () => {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [posting, setPosting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/deal-room/access/${token}`);
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e.response?.data?.detail || 'This link is no longer valid.');
      setData(null);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const postMessage = async () => {
    const content = newMessage.trim();
    if (!content) return;
    setPosting(true);
    try {
      await axios.post(`${BACKEND_URL}/api/deal-room/access/${token}/messages`, { content });
      setNewMessage('');
      await load();
      toast.success('Message sent');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send');
    } finally { setPosting(false); }
  };

  const respondToApproval = async (approvalId, decision) => {
    try {
      await axios.post(`${BACKEND_URL}/api/deal-room/access/${token}/approvals/${approvalId}/respond`, { decision });
      await load();
      toast.success(`Marked ${decision}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to respond');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-violet-50 dark:from-slate-950 dark:to-violet-950">
        <div className="text-sm text-muted-foreground">Loading your Deal Room…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-rose-50 dark:from-slate-950 dark:to-rose-950 p-4">
        <Card className="max-w-md w-full" data-testid="guest-deal-room-error">
          <CardContent className="py-10 text-center space-y-3">
            <span className="inline-flex p-3 rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950/40">
              <Lock className="w-6 h-6" />
            </span>
            <h2 className="text-lg font-semibold">Access denied</h2>
            <p className="text-sm text-muted-foreground">{error || 'This invitation link is invalid or has expired.'}</p>
            <p className="text-xs text-muted-foreground">Ask the person who shared this link to send you a fresh invite.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { invite, lead, active_partners, public_comments, approvals, documents } = data;
  const canComment = invite.permissions.includes('comment');
  const canApprove = invite.permissions.includes('approve');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-violet-50 dark:from-slate-950 dark:to-violet-950" data-testid="guest-deal-room">
      <Toaster richColors position="top-center" />
      {/* Header */}
      <header className="bg-white/70 dark:bg-slate-900/70 backdrop-blur border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
              <Sparkles className="w-4 h-4" />
            </span>
            <div>
              <h1 className="text-sm font-semibold leading-tight">Meshora Deal Room</h1>
              <p className="text-[11px] text-muted-foreground leading-tight">{invite.invited_by_name ? `Invited by ${invite.invited_by_name}` : 'Guest access'}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs font-medium" data-testid="guest-name">{invite.name}</div>
            <div className="text-[10px] text-muted-foreground">Access expires {new Date(invite.expires_at).toLocaleDateString()}</div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-4">
        {/* Hero card */}
        <Card className="bg-gradient-to-r from-violet-500 to-indigo-500 text-white border-0">
          <CardContent className="py-5">
            <div className="flex items-center gap-3 mb-2">
              <Badge variant="outline" className="bg-white/15 text-white border-white/30 text-[10px]">LIVE</Badge>
              <Badge style={{ backgroundColor: 'rgba(255,255,255,0.15)' }} className="text-white border-white/30 border text-[10px]">{lead.status_name}</Badge>
            </div>
            <h2 className="text-xl font-semibold">{lead.title}</h2>
            <p className="text-sm opacity-90 mt-1">
              {lead.customer_company || lead.customer_name} · {lead.primary_category_name || 'Project'}
            </p>
          </CardContent>
        </Card>

        {/* Partners */}
        {active_partners.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><Users className="w-4 h-4 text-violet-600" /> Working with</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {active_partners.map((p, i) => (
                <Badge key={i} variant="secondary" className="text-xs">{p.partner_name}{p.company_name ? ` · ${p.company_name}` : ''}</Badge>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Approvals */}
        {approvals.length > 0 && (
          <Card data-testid="guest-approvals-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600" /> Approvals</CardTitle>
              <CardDescription className="text-xs">Sign-offs requested from you or other stakeholders.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {approvals.map((a) => {
                const cls = {
                  pending: 'bg-amber-100 text-amber-800',
                  approved: 'bg-emerald-100 text-emerald-800',
                  rejected: 'bg-rose-100 text-rose-800',
                }[a.status] || 'bg-slate-100 text-slate-800';
                const Icon = a.status === 'approved' ? CheckCircle2 : a.status === 'rejected' ? XCircle : Clock;
                return (
                  <div key={a.id} className="p-3 rounded-lg border" data-testid={`guest-approval-${a.id}`}>
                    <div className="flex items-start gap-3">
                      <Icon className={`w-4 h-4 mt-0.5 ${a.status === 'approved' ? 'text-emerald-600' : a.status === 'rejected' ? 'text-rose-600' : 'text-amber-600'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{a.title}</span>
                          <Badge className={`text-[10px] ${cls}`}>{a.status}</Badge>
                          {a.due_date && <Badge variant="outline" className="text-[10px]">Due {a.due_date}</Badge>}
                        </div>
                        {a.description && <p className="text-xs text-muted-foreground mt-1">{a.description}</p>}
                        <div className="text-[10px] text-muted-foreground mt-1">Requested by {a.created_by_name} · {formatDateTime(a.created_at)}</div>
                        {a.responded_at && (
                          <div className="mt-1.5 text-xs p-1.5 rounded bg-muted/40">
                            <span className="font-medium capitalize">{a.decision}</span> by {a.responded_by_name} · {formatDateTime(a.responded_at)}
                          </div>
                        )}
                        {canApprove && a.status === 'pending' && (
                          <div className="flex gap-2 mt-2">
                            <Button size="sm" onClick={() => respondToApproval(a.id, 'approved')} className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs" data-testid={`guest-approve-${a.id}`}>
                              <CheckCircle2 className="w-3 h-3 mr-1" /> Approve
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => respondToApproval(a.id, 'rejected')} className="h-7 text-xs">
                              <XCircle className="w-3 h-3 mr-1" /> Reject
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}

        {/* Documents */}
        {documents.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><FileText className="w-4 h-4 text-sky-600" /> Shared Documents</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {documents.map((d) => (
                <div key={d.id} className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/40">
                  <FileText className="w-4 h-4 text-sky-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{d.original_filename || d.filename}</div>
                    <div className="text-[11px] text-muted-foreground">{d.tag || 'document'} · {d.uploaded_by_name}</div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Conversation */}
        <Card data-testid="guest-conversation-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2"><MessageSquare className="w-4 h-4 text-violet-600" /> Conversation <Badge variant="outline" className="text-[10px] ml-1">{public_comments.length}</Badge></CardTitle>
            <CardDescription className="text-xs">Messages here are visible to everyone in the Deal Room.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {public_comments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-2">No messages yet.</p>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {public_comments.map((c) => (
                  <div key={c.id} className="p-2.5 rounded-lg border bg-muted/30">
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
            {canComment ? (
              <div className="border-t pt-3 space-y-2">
                <Textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  rows={2}
                  placeholder="Share an update or ask a question…"
                  data-testid="guest-message-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); postMessage(); }
                  }}
                />
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" /> Posted as <strong>{invite.name} (Guest)</strong>
                  </span>
                  <Button size="sm" onClick={postMessage} disabled={!newMessage.trim() || posting} data-testid="guest-send-btn">
                    <Send className="w-3.5 h-3.5 mr-1.5" /> {posting ? 'Sending…' : 'Send'}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="border-t pt-3 text-xs text-muted-foreground flex items-center gap-1.5">
                <AlertCircle className="w-3 h-3" /> Your invite is view-only.
              </div>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-[10px] text-muted-foreground py-4">
          Powered by Meshora — a Collaborative Revenue OS
        </p>
      </main>
    </div>
  );
};

export default GuestDealRoom;
