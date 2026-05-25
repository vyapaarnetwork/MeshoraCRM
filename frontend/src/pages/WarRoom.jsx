import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Skeleton } from '../components/ui/skeleton';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../components/ui/sheet';
import {
  Swords, Play, Square, RefreshCw, Flame, AlertTriangle, Clock, DollarSign, Users,
  Moon, Trophy, Activity, MessageSquare, Calendar, ExternalLink, Sparkles, FileText,
  ChevronRight, TrendingDown, CheckCircle2, History, Heart, ClipboardList,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import FeatureInfo from '../components/FeatureInfo';

const BUCKET_ICONS = {
  high_priority: Flame, blocked: AlertTriangle, followup_pending: Clock,
  commercial_pending: DollarSign, partner_coordination: Users, inactive: Moon, recently_won: Trophy,
};

const HEALTH_CLS = {
  hot: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  warm: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  cold: 'bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300',
  at_risk: 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300',
};

const WarRoom = () => {
  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeSession, setActiveSession] = useState(null);
  const [showStartDialog, setShowStartDialog] = useState(false);
  const [sessionTitle, setSessionTitle] = useState('');
  const [activeLeadCard, setActiveLeadCard] = useState(null);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [history, setHistory] = useState([]);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const navigate = useNavigate();
  const { user } = useAuth();
  const notesTimer = useRef(null);

  const loadBoard = useCallback(async () => {
    try {
      const r = await api.get('/war-room/board');
      setBoard(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load War Room');
    }
  }, []);

  const loadActiveSession = useCallback(async () => {
    try {
      const r = await api.get('/war-room/sessions/active');
      setActiveSession(r.data || null);
    } catch (e) {/* ignore */}
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadBoard(), loadActiveSession()]);
      setLoading(false);
    })();
  }, [loadBoard, loadActiveSession]);

  const refresh = async () => {
    setRefreshing(true);
    await loadBoard();
    setRefreshing(false);
  };

  const startSession = async () => {
    try {
      const r = await api.post('/war-room/sessions/start', { title: sessionTitle.trim() || undefined });
      setActiveSession(r.data);
      setSessionTitle('');
      setShowStartDialog(false);
      toast.success('Weekly Review started — focus mode is on');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to start');
    }
  };

  const endSession = async () => {
    if (!activeSession) return;
    if (!window.confirm('End this Weekly Review? AI will generate a summary and create tasks from action items.')) return;
    setEndingSession(true);
    try {
      const r = await api.post(`/war-room/sessions/${activeSession.id}/end`);
      setActiveSession(null);
      toast.success(`Session ended. ${r.data.materialized_task_count || 0} tasks created.`);
      // Show summary dialog
      setHistory((h) => [r.data, ...h]);
      setShowHistoryDialog(true);
      setSummaryOpen(true);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to end session');
    } finally { setEndingSession(false); }
  };

  const updateNotes = (text) => {
    setActiveSession((s) => s ? { ...s, notes: text } : s);
    // Debounced save
    if (notesTimer.current) clearTimeout(notesTimer.current);
    notesTimer.current = setTimeout(async () => {
      if (!activeSession) return;
      try { await api.patch(`/war-room/sessions/${activeSession.id}/notes`, { notes: text }); }
      catch (e) {/* ignore */}
    }, 800);
  };

  const markDiscussed = async (leadId, note = '') => {
    if (!activeSession) return;
    try {
      await api.post(`/war-room/sessions/${activeSession.id}/discuss`, { lead_id: leadId, note });
      setActiveSession((s) => ({
        ...s,
        discussed_lead_ids: Array.from(new Set([...(s.discussed_lead_ids || []), leadId])),
      }));
    } catch (e) {/* ignore */}
  };

  const loadHistory = async () => {
    try {
      const r = await api.get('/war-room/sessions?limit=20');
      setHistory(r.data || []);
      setShowHistoryDialog(true);
    } catch (e) {/* ignore */}
  };

  if (loading) return <WarRoomSkeleton />;
  if (!board) return null;

  const isReviewMode = !!activeSession;
  const discussed = new Set(activeSession?.discussed_lead_ids || []);

  return (
    <div className="space-y-5" data-testid="war-room-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <Swords className="w-7 h-7 text-violet-600" />
            Weekly War Room
            <FeatureInfo
              size="lg"
              title="What is the War Room?"
              description="A live operations board that auto-sorts your open leads into 7 smart buckets based on what they need this week — not by pipeline stage. Replaces spreadsheet-based weekly reviews with focus, intelligence, and one-click AI summaries."
              howTo="Start a Weekly Review session, click cards to discuss them (they get logged), jot notes in the side panel. End the session — AI generates a structured summary and converts action items into Tasks automatically."
              tip="Mention #blocker in any comment to force a lead into the Blocked bucket — useful for things AI can't infer."
            />
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Collaboration that converts — your weekly business operating board.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={loadHistory} data-testid="history-btn">
            <History className="w-4 h-4 mr-1.5" /> Past Reviews
          </Button>
          <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {isReviewMode ? (
            <Button onClick={endSession} disabled={endingSession} variant="destructive" data-testid="end-session-btn">
              <Square className="w-4 h-4 mr-1.5" /> {endingSession ? 'Generating summary…' : 'End Review'}
            </Button>
          ) : (
            <Button onClick={() => setShowStartDialog(true)} className="bg-gradient-to-r from-violet-500 to-indigo-500 text-white" data-testid="start-session-btn">
              <Play className="w-4 h-4 mr-1.5" /> Start Weekly Review
            </Button>
          )}
        </div>
      </div>

      {/* Revenue Intelligence Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KpiCard icon={Activity} label="Open Leads" value={board.kpis.total_leads} sub="In review buckets" />
        <KpiCard icon={DollarSign} label="Pipeline" value={formatCurrency(board.kpis.total_pipeline)} sub="Total open" accent="violet" />
        <KpiCard icon={Sparkles} label="Weighted" value={formatCurrency(board.kpis.weighted_pipeline)} sub="Probability-adjusted" accent="indigo" />
        <KpiCard icon={TrendingDown} label="At Risk" value={formatCurrency(board.kpis.at_risk_pipeline)} sub="Needs attention" accent="rose" />
        <KpiCard icon={Moon} label="Inactive Value" value={formatCurrency(board.kpis.inactive_pipeline)} sub="Stale 21d+" accent="slate" />
      </div>

      {/* Review session banner */}
      {isReviewMode && (
        <Card className="border-violet-300 dark:border-violet-800 bg-gradient-to-r from-violet-100/60 to-indigo-100/60 dark:from-violet-950/30 dark:to-indigo-950/30" data-testid="review-mode-banner">
          <CardContent className="py-3 flex items-center gap-3 flex-wrap">
            <div className="p-2 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-[200px]">
              <div className="text-sm font-semibold">{activeSession.title}</div>
              <div className="text-[11px] text-muted-foreground">
                {discussed.size} lead{discussed.size === 1 ? '' : 's'} discussed · Started {new Date(activeSession.started_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
            <Badge variant="outline" className="bg-violet-200/60 dark:bg-violet-900/50 border-violet-300 dark:border-violet-700">LIVE</Badge>
          </CardContent>
        </Card>
      )}

      {/* Main layout: review mode = 2-col, else = full-width board */}
      <div className={`grid gap-4 ${isReviewMode ? 'lg:grid-cols-[1fr_360px]' : 'grid-cols-1'}`}>
        {/* Board */}
        <div className="overflow-x-auto">
          <div className="flex gap-3 min-w-max pb-3">
            {board.buckets.map((bucket) => {
              const Icon = BUCKET_ICONS[bucket.id] || Activity;
              return (
                <div key={bucket.id} className="w-[300px] shrink-0" data-testid={`bucket-${bucket.id}`}>
                  <div className="rounded-t-lg p-2.5 flex items-center gap-2" style={{ background: bucket.color + '14', borderTop: `3px solid ${bucket.color}` }}>
                    <Icon className="w-4 h-4" style={{ color: bucket.color }} />
                    <span className="text-sm font-semibold">{bucket.label.replace(/^[^\s]+\s/, '')}</span>
                    <Badge variant="outline" className="text-[10px] ml-auto">{bucket.count}</Badge>
                  </div>
                  <div className="bg-muted/30 rounded-b-lg p-2 space-y-2 max-h-[680px] overflow-y-auto">
                    {bucket.leads.length === 0 && (
                      <p className="text-[11px] text-muted-foreground text-center py-6 italic">No leads in this bucket.</p>
                    )}
                    {bucket.leads.map((lead) => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        bucketColor={bucket.color}
                        reviewMode={isReviewMode}
                        discussed={discussed.has(lead.id)}
                        onClick={() => {
                          if (isReviewMode) {
                            setActiveLeadCard(lead);
                            markDiscussed(lead.id);
                          } else {
                            navigate(`/leads/${lead.id}`);
                          }
                        }}
                        onOpenLead={() => navigate(`/leads/${lead.id}`)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Review notes panel */}
        {isReviewMode && (
          <div className="space-y-3" data-testid="review-notes-panel">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2"><FileText className="w-4 h-4 text-violet-600" /> Meeting Notes</CardTitle>
                <CardDescription className="text-xs">Auto-saved. Click a lead card to log it as discussed.</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={activeSession.notes || ''}
                  onChange={(e) => updateNotes(e.target.value)}
                  rows={14}
                  placeholder={`Discussion points, decisions, action items…\n\nExamples:\n- Hardik to send proposal by Thursday\n- Escalate Acme deal to leadership\n- Blocked on legal review for Globex`}
                  className="font-mono text-xs"
                  data-testid="session-notes-textarea"
                />
              </CardContent>
            </Card>

            {activeLeadCard && (
              <Card className="border-violet-200 dark:border-violet-900" data-testid="active-lead-context">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center justify-between gap-2">
                    <span className="truncate">{activeLeadCard.title}</span>
                    <Button size="sm" variant="ghost" className="h-6 px-2 -mr-2" onClick={() => navigate(`/leads/${activeLeadCard.id}`)}>
                      Open <ExternalLink className="w-3 h-3 ml-1" />
                    </Button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs space-y-1.5">
                  <KV k="Company" v={activeLeadCard.customer_company} />
                  <KV k="Value" v={formatCurrency(activeLeadCard.deal_value)} />
                  <KV k="Stage" v={activeLeadCard.status_name} />
                  <KV k="Partner" v={activeLeadCard.selling_partner_name || '—'} />
                  <KV k="Health" v={<Badge className={`text-[10px] ${HEALTH_CLS[activeLeadCard.health_band] || ''}`}>{activeLeadCard.health_band}</Badge>} />
                  <KV k="Inactive" v={`${activeLeadCard.days_inactive ?? 0} day(s)`} />
                  {activeLeadCard.next_action_label && (
                    <div className="mt-2 p-2 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-200 text-[11px] border border-amber-200 dark:border-amber-900/50">
                      <strong>Suggested:</strong> {activeLeadCard.next_action_label}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>

      {/* Start session dialog */}
      <Dialog open={showStartDialog} onOpenChange={setShowStartDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start Weekly Review</DialogTitle>
            <DialogDescription>The board enters focus mode. Click cards to log them as discussed. At the end, AI generates a structured summary and creates tasks from action items.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label className="text-xs font-medium text-muted-foreground">Title (optional)</label>
            <Input value={sessionTitle} onChange={(e) => setSessionTitle(e.target.value)} placeholder={`Weekly Review ${new Date().toLocaleDateString('en-IN')}`} data-testid="session-title-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStartDialog(false)}>Cancel</Button>
            <Button onClick={startSession} data-testid="confirm-start-session-btn">Start Review</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History sheet */}
      <Sheet open={showHistoryDialog} onOpenChange={setShowHistoryDialog}>
        <SheetContent className="w-[460px] sm:max-w-md overflow-y-auto" data-testid="history-sheet">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2"><History className="w-5 h-5 text-violet-600" /> Past Reviews</SheetTitle>
            <SheetDescription>Click a session to view its AI-generated summary and action items.</SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-3">
            {history.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-6">No past sessions yet.</p>
            )}
            {history.map((s) => (
              <Card key={s.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => { setSummaryOpen(true); window.__currentSummary = s; }} data-testid={`history-session-${s.id}`}>
                <CardContent className="py-3 space-y-1">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                    <span className="text-sm font-semibold">{s.title}</span>
                    {!s.ended_at && <Badge variant="outline" className="text-[10px] ml-auto">Active</Badge>}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {new Date(s.started_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                    {s.materialized_task_count > 0 && ` · ${s.materialized_task_count} tasks created`}
                  </p>
                  {s.summary?.executive_summary && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{s.summary.executive_summary}</p>
                  )}
                  <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-violet-600 mt-1" onClick={(e) => { e.stopPropagation(); window.__currentSummary = s; setSummaryOpen(true); }}>
                    View summary <ChevronRight className="w-3 h-3 ml-0.5" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </SheetContent>
      </Sheet>

      {/* Summary dialog */}
      {summaryOpen && window.__currentSummary && (
        <SummaryDialog session={window.__currentSummary} onClose={() => { setSummaryOpen(false); }} />
      )}
    </div>
  );
};

const LeadCard = ({ lead, bucketColor, reviewMode, discussed, onClick, onOpenLead }) => {
  const HealthIcon = lead.health_band === 'hot' ? Flame : lead.health_band === 'at_risk' ? AlertTriangle : Heart;
  return (
    <div
      className={`bg-white dark:bg-slate-900 rounded-md p-2.5 border-l-2 hover:shadow-md transition-all cursor-pointer ${discussed ? 'opacity-60' : ''}`}
      style={{ borderLeftColor: bucketColor }}
      onClick={onClick}
      data-testid={`war-room-card-${lead.id}`}
    >
      <div className="flex items-start gap-2 mb-1">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium leading-tight line-clamp-2">{lead.title}</h4>
          {lead.customer_company && (
            <p className="text-[11px] text-muted-foreground truncate">{lead.customer_company}</p>
          )}
        </div>
        {discussed && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />}
      </div>
      <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
        {lead.deal_value > 0 && (
          <span className="text-xs font-semibold tabular-nums">{formatCurrency(lead.deal_value)}</span>
        )}
        {lead.primary_category_name && (
          <Badge variant="outline" className="text-[9px] py-0 px-1">{lead.primary_category_name}</Badge>
        )}
        <Badge className={`text-[9px] py-0 px-1 ${HEALTH_CLS[lead.health_band] || ''}`}>
          <HealthIcon className="w-2.5 h-2.5 mr-0.5" />
          {lead.health_band}
        </Badge>
      </div>
      <div className="text-[10px] text-muted-foreground flex flex-wrap gap-x-2 gap-y-0.5">
        {lead.selling_partner_name && <span title="Selling partner">🤝 {lead.selling_partner_name.split(' ')[0]}</span>}
        {(lead.days_inactive ?? 0) > 0 && (
          <span className={lead.days_inactive > 14 ? 'text-rose-600' : ''}>
            <Clock className="w-2.5 h-2.5 inline -mt-0.5 mr-0.5" />{lead.days_inactive}d
          </span>
        )}
        {lead.overdue_count > 0 && (
          <span className="text-rose-600 font-medium">{lead.overdue_count} overdue</span>
        )}
        {lead.comment_count > 0 && (
          <span><MessageSquare className="w-2.5 h-2.5 inline -mt-0.5 mr-0.5" />{lead.comment_count}</span>
        )}
        {lead.pending_approvals > 0 && (
          <span className="text-amber-600 font-medium">{lead.pending_approvals} approval{lead.pending_approvals === 1 ? '' : 's'}</span>
        )}
      </div>
      {reviewMode && lead.next_action_label && (
        <div className="mt-2 p-1.5 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-200 text-[10px] border border-amber-200 dark:border-amber-900/50 line-clamp-2">
          💡 {lead.next_action_label}
        </div>
      )}
    </div>
  );
};

const SummaryDialog = ({ session, onClose }) => {
  const s = session.summary || {};
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="summary-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-600" />
            {session.title} — AI Summary
          </DialogTitle>
          <DialogDescription>
            {session.materialized_task_count > 0 && (
              <span className="text-emerald-600 font-medium">✨ {session.materialized_task_count} task(s) created from action items.</span>
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {s.executive_summary && (
            <Section title="Executive Summary" icon={Sparkles}>
              <p className="text-sm leading-relaxed">{s.executive_summary}</p>
            </Section>
          )}
          {s.leads_progressed?.length > 0 && (
            <Section title="Leads Progressed" icon={Activity}>
              <ListItems items={s.leads_progressed} />
            </Section>
          )}
          {s.high_risk_leads?.length > 0 && (
            <Section title="High-Risk Leads" icon={AlertTriangle} color="rose">
              <ListItems items={s.high_risk_leads} />
            </Section>
          )}
          {s.blocked_opportunities?.length > 0 && (
            <Section title="Blocked Opportunities" icon={AlertTriangle} color="amber">
              <ListItems items={s.blocked_opportunities} />
            </Section>
          )}
          {s.revenue_updates && (
            <Section title="Revenue Updates" icon={DollarSign} color="emerald">
              <p className="text-sm leading-relaxed">{s.revenue_updates}</p>
            </Section>
          )}
          {s.partner_dependencies?.length > 0 && (
            <Section title="Partner Dependencies" icon={Users} color="violet">
              <ListItems items={s.partner_dependencies} />
            </Section>
          )}
          {s.action_items?.length > 0 && (
            <Section title="Action Items" icon={ClipboardList} color="indigo">
              <div className="space-y-1.5">
                {s.action_items.map((a, i) => (
                  <div key={i} className="text-sm p-2 rounded border bg-indigo-50/30 dark:bg-indigo-950/20" data-testid={`action-item-${i}`}>
                    <div className="font-medium">{typeof a === 'string' ? a : a.action}</div>
                    {typeof a === 'object' && (
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        {a.owner && <>👤 {a.owner} </>}
                        {a.due_date && <>📅 {a.due_date}</>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}
          {s.upcoming_followups?.length > 0 && (
            <Section title="Upcoming Follow-ups" icon={Calendar} color="sky">
              <ListItems items={s.upcoming_followups} />
            </Section>
          )}
        </div>
        <DialogFooter>
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const Section = ({ title, icon: Icon, color = 'slate', children }) => {
  const map = {
    rose: 'text-rose-600', amber: 'text-amber-600', emerald: 'text-emerald-600',
    violet: 'text-violet-600', indigo: 'text-indigo-600', sky: 'text-sky-600', slate: 'text-slate-600',
  };
  return (
    <div>
      <h4 className={`text-sm font-semibold mb-1.5 flex items-center gap-1.5 ${map[color]}`}>
        <Icon className="w-4 h-4" /> {title}
      </h4>
      {children}
    </div>
  );
};

const ListItems = ({ items }) => (
  <ul className="space-y-1 ml-1">
    {items.map((item, i) => (
      <li key={i} className="text-sm leading-relaxed flex gap-2">
        <span className="text-muted-foreground">•</span>
        <span>{typeof item === 'string' ? item : JSON.stringify(item)}</span>
      </li>
    ))}
  </ul>
);

const KpiCard = ({ icon: Icon, label, value, sub, accent = 'slate' }) => {
  const cls = {
    violet: 'bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300',
    indigo: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300',
    rose: 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
    slate: 'bg-slate-50 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300',
  }[accent];
  return (
    <Card className={cls}>
      <CardContent className="pt-4">
        <Icon className="w-4 h-4 mb-1 opacity-70" />
        <div className="text-[10px] uppercase tracking-wider opacity-80">{label}</div>
        <div className="text-lg font-bold tabular-nums">{value}</div>
        {sub && <div className="text-[10px] opacity-60 mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
};

const KV = ({ k, v }) => (
  <div className="flex justify-between gap-2">
    <span className="text-muted-foreground">{k}</span>
    <span className="font-medium text-right">{v}</span>
  </div>
);

const WarRoomSkeleton = () => (
  <div className="space-y-4">
    <Skeleton className="h-10 w-80" />
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{[1,2,3,4,5].map(i=><Skeleton key={i} className="h-20 rounded-xl" />)}</div>
    <div className="flex gap-3">{[1,2,3,4,5,6,7].map(i=><Skeleton key={i} className="w-[300px] h-96 shrink-0 rounded-lg" />)}</div>
  </div>
);

export default WarRoom;
