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
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import {
  Swords, Play, Square, RefreshCw, Flame, AlertTriangle, Clock, DollarSign, Users,
  Moon, Trophy, Activity, MessageSquare, Calendar, ExternalLink, Sparkles, FileText,
  ChevronRight, TrendingDown, CheckCircle2, History, Heart, ClipboardList, Pin,
  Bookmark, BookmarkPlus, Trash2, Pencil, ChevronDown,
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
  // Phase 29.1: drag-and-drop state
  const [draggingLeadId, setDraggingLeadId] = useState(null);
  const [dragOverBucket, setDragOverBucket] = useState(null);
  // Phase 29.2: per-user bucket visibility filter (persisted in localStorage)
  const [hiddenBuckets, setHiddenBuckets] = useState(() => {
    try {
      const raw = localStorage.getItem('meshora.warRoom.hiddenBuckets');
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch (e) { return new Set(); }
  });

  const toggleBucket = (bucketId) => {
    setHiddenBuckets((prev) => {
      const next = new Set(prev);
      if (next.has(bucketId)) next.delete(bucketId);
      else next.add(bucketId);
      try { localStorage.setItem('meshora.warRoom.hiddenBuckets', JSON.stringify([...next])); } catch (e) {/* ignore */}
      return next;
    });
  };

  const resetFilter = () => {
    setHiddenBuckets(new Set());
    try { localStorage.removeItem('meshora.warRoom.hiddenBuckets'); } catch (e) {/* ignore */}
  };

  const showOnly = (bucketId) => {
    const all = new Set((board?.buckets || []).map((b) => b.id));
    all.delete(bucketId);
    setHiddenBuckets(all);
    try { localStorage.setItem('meshora.warRoom.hiddenBuckets', JSON.stringify([...all])); } catch (e) {/* ignore */}
  };

  // Phase 29.3: Saved views
  const [savedViews, setSavedViews] = useState([]);
  const [activeViewId, setActiveViewId] = useState(null);
  const [viewsMenuOpen, setViewsMenuOpen] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  const loadViews = useCallback(async () => {
    try {
      const r = await api.get('/war-room/views');
      setSavedViews(r.data || []);
    } catch (e) {/* ignore */}
  }, []);

  useEffect(() => { loadViews(); }, [loadViews]);

  const applyView = (view) => {
    const next = new Set(view.hidden_buckets || []);
    setHiddenBuckets(next);
    try { localStorage.setItem('meshora.warRoom.hiddenBuckets', JSON.stringify([...next])); } catch (e) {/* ignore */}
    setActiveViewId(view.id);
    setViewsMenuOpen(false);
    toast.success(`Applied: ${view.name}`);
  };

  const saveCurrentAsView = async () => {
    const name = saveViewName.trim();
    if (!name) { toast.error('Name is required'); return; }
    try {
      const r = await api.post('/war-room/views', { name, hidden_buckets: [...hiddenBuckets] });
      setSavedViews((s) => [r.data, ...s]);
      setActiveViewId(r.data.id);
      setShowSaveDialog(false);
      setSaveViewName('');
      toast.success(`Saved "${name}"`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    }
  };

  const renameView = async (viewId) => {
    const name = renameValue.trim();
    if (!name) return;
    try {
      const r = await api.patch(`/war-room/views/${viewId}`, { name });
      setSavedViews((s) => s.map((v) => v.id === viewId ? r.data : v));
      setRenamingId(null);
      toast.success('Renamed');
    } catch (e) { toast.error('Rename failed'); }
  };

  const deleteView = async (viewId, e) => {
    e?.stopPropagation();
    if (!window.confirm('Delete this saved view?')) return;
    try {
      await api.delete(`/war-room/views/${viewId}`);
      setSavedViews((s) => s.filter((v) => v.id !== viewId));
      if (activeViewId === viewId) setActiveViewId(null);
      toast.success('Deleted');
    } catch (err) { toast.error('Delete failed'); }
  };

  // Clear active view label when user manually changes filters away from it
  useEffect(() => {
    if (!activeViewId) return;
    const v = savedViews.find((x) => x.id === activeViewId);
    if (!v) return;
    const sameBuckets = (v.hidden_buckets || []).slice().sort().join(',') === [...hiddenBuckets].sort().join(',');
    if (!sameBuckets) setActiveViewId(null);
  }, [hiddenBuckets, savedViews, activeViewId]);

  const moveLeadToBucket = async (leadId, targetBucket, sourceBucket) => {
    if (!leadId || sourceBucket === targetBucket) return;
    // Optimistic move
    setBoard((prev) => {
      if (!prev) return prev;
      const buckets = prev.buckets.map((b) => ({ ...b, leads: [...b.leads] }));
      let card = null;
      for (const b of buckets) {
        const idx = b.leads.findIndex((l) => l.id === leadId);
        if (idx >= 0) { card = b.leads.splice(idx, 1)[0]; b.count = b.leads.length; b.total_value = b.leads.reduce((s,l)=>s+(l.deal_value||0),0); break; }
      }
      if (card) {
        const t = buckets.find((b) => b.id === targetBucket);
        if (t) { t.leads.unshift({ ...card, is_manual_override: true }); t.count = t.leads.length; t.total_value = t.leads.reduce((s,l)=>s+(l.deal_value||0),0); }
      }
      return { ...prev, buckets };
    });
    try {
      await api.patch(`/war-room/leads/${leadId}/bucket`, { bucket: targetBucket });
      toast.success('Pinned to ' + targetBucket.replace(/_/g, ' '));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Move failed — reverting');
      await loadBoard();
    }
  };

  const unpinLead = async (leadId, e) => {
    e?.stopPropagation();
    try {
      await api.patch(`/war-room/leads/${leadId}/bucket`, { bucket: null });
      toast.success('Unpinned — auto-classifier resumed');
      await loadBoard();
    } catch (err) {
      toast.error('Failed to unpin');
    }
  };

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
      // Stable reference for SummaryDialog before opening it (avoid mount race)
      window.__currentSummary = r.data;
      setHistory((h) => [r.data, ...h]);
      // Open dialog on next tick so the data is in place
      setTimeout(() => {
        setShowHistoryDialog(true);
        setSummaryOpen(true);
      }, 50);
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
              description="A live operations board that auto-sorts your open leads into 7 smart buckets based on what they need this week — not by pipeline stage. Drag any card to a different bucket to manually pin it (great for overriding the AI when you know something it doesn't)."
              howTo="Start a Weekly Review session, click cards to discuss them (they get logged), jot notes in the side panel. End the session — AI generates a structured summary and converts action items into Tasks automatically."
              tip="Drag a card between buckets to pin it. Click the 📌 'pinned' badge to clear and resume auto-classification. Mention #blocker in any comment to force a lead into the Blocked bucket."
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

      {/* Phase 29.2: Bucket visibility filter chips + Phase 29.3 saved views dropdown */}
      <Card data-testid="bucket-filter-row" className="bg-muted/30">
        <CardContent className="py-2.5 flex items-center gap-2 flex-wrap">
          {/* Saved Views selector */}
          <Popover open={viewsMenuOpen} onOpenChange={setViewsMenuOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white dark:bg-slate-900 border text-xs hover:shadow-sm transition-shadow"
                data-testid="saved-views-trigger"
              >
                <Bookmark className="w-3.5 h-3.5 text-violet-600" />
                <span className="font-medium max-w-[160px] truncate">
                  {activeViewId
                    ? (savedViews.find((v) => v.id === activeViewId)?.name || 'View')
                    : 'Saved views'}
                </span>
                {savedViews.length > 0 && (
                  <Badge variant="outline" className="text-[9px] py-0 px-1">{savedViews.length}</Badge>
                )}
                <ChevronDown className="w-3 h-3 text-muted-foreground" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-72 p-0">
              <div className="px-3 py-2 border-b flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Your views</span>
                <button
                  type="button"
                  onClick={() => { setViewsMenuOpen(false); setSaveViewName(''); setShowSaveDialog(true); }}
                  className="text-[11px] text-violet-600 hover:text-violet-700 hover:underline inline-flex items-center gap-1"
                  data-testid="save-current-view-btn"
                >
                  <BookmarkPlus className="w-3 h-3" /> Save current
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto">
                {savedViews.length === 0 ? (
                  <p className="px-3 py-6 text-xs text-center text-muted-foreground">
                    No saved views yet.<br />
                    Hide some buckets, then click <span className="font-medium">Save current</span> above.
                  </p>
                ) : (
                  savedViews.map((v) => (
                    <div
                      key={v.id}
                      className={`px-3 py-2 hover:bg-muted/50 cursor-pointer flex items-center gap-2 group ${activeViewId === v.id ? 'bg-violet-50 dark:bg-violet-950/30' : ''}`}
                      onClick={() => renamingId !== v.id && applyView(v)}
                      data-testid={`saved-view-${v.id}`}
                    >
                      {renamingId === v.id ? (
                        <Input
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') renameView(v.id);
                            if (e.key === 'Escape') setRenamingId(null);
                          }}
                          autoFocus
                          className="h-7 text-xs"
                        />
                      ) : (
                        <>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate flex items-center gap-1">
                              {v.name}
                              {activeViewId === v.id && <CheckCircle2 className="w-3 h-3 text-violet-600" />}
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                              {v.hidden_buckets?.length > 0 ? `Hides ${v.hidden_buckets.length} bucket(s)` : 'Shows all buckets'}
                            </div>
                          </div>
                          <div className="opacity-0 group-hover:opacity-100 flex gap-0.5 transition-opacity">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setRenamingId(v.id); setRenameValue(v.name); }}
                              className="p-1 rounded hover:bg-muted"
                              title="Rename"
                            >
                              <Pencil className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => deleteView(v.id, e)}
                              className="p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/40 text-rose-600"
                              title="Delete"
                              data-testid={`delete-view-${v.id}`}
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  ))
                )}
              </div>
            </PopoverContent>
          </Popover>

          <span className="w-px h-5 bg-border" />
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">Show</span>
          {board.buckets.map((bucket) => {
            const Icon = BUCKET_ICONS[bucket.id] || Activity;
            const isHidden = hiddenBuckets.has(bucket.id);
            return (
              <button
                key={bucket.id}
                type="button"
                onClick={() => toggleBucket(bucket.id)}
                onDoubleClick={() => showOnly(bucket.id)}
                title={isHidden ? 'Click to show this bucket. Double-click to show ONLY this bucket.' : 'Click to hide this bucket. Double-click to show ONLY this bucket.'}
                className={`group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs transition-all ${
                  isHidden
                    ? 'bg-transparent border-dashed border-muted-foreground/30 text-muted-foreground/50 hover:border-muted-foreground/60'
                    : 'border-transparent text-foreground hover:shadow-sm'
                }`}
                style={!isHidden ? { backgroundColor: bucket.color + '20', borderColor: bucket.color + '40' } : {}}
                data-testid={`filter-chip-${bucket.id}`}
              >
                <Icon className="w-3 h-3" style={!isHidden ? { color: bucket.color } : {}} />
                <span className={isHidden ? 'line-through' : ''}>{bucket.label.replace(/^[^\s]+\s/, '')}</span>
                <Badge variant="outline" className="text-[9px] py-0 px-1 ml-0.5">{bucket.count}</Badge>
              </button>
            );
          })}
          {hiddenBuckets.size > 0 && (
            <button
              type="button"
              onClick={resetFilter}
              className="ml-1 text-[11px] text-violet-600 hover:text-violet-700 hover:underline"
              data-testid="filter-reset-btn"
            >
              Reset
            </button>
          )}
          <span className="ml-auto text-[10px] text-muted-foreground">
            {hiddenBuckets.size > 0 ? `${board.buckets.length - hiddenBuckets.size}/${board.buckets.length} visible` : 'All visible'}
            <span className="hidden md:inline"> · double-click a chip to isolate</span>
          </span>
        </CardContent>
      </Card>

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
            {board.buckets.filter((b) => !hiddenBuckets.has(b.id)).length === 0 && (
              <Card className="w-full" data-testid="all-hidden-state">
                <CardContent className="py-12 text-center space-y-3">
                  <Moon className="w-8 h-8 mx-auto text-muted-foreground opacity-40" />
                  <p className="text-sm text-muted-foreground">All buckets are hidden.</p>
                  <Button size="sm" variant="outline" onClick={resetFilter}>Reset filters</Button>
                </CardContent>
              </Card>
            )}
            {board.buckets.filter((b) => !hiddenBuckets.has(b.id)).map((bucket) => {
              const Icon = BUCKET_ICONS[bucket.id] || Activity;
              return (
                <div
                  key={bucket.id}
                  className="w-[300px] shrink-0"
                  data-testid={`bucket-${bucket.id}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOverBucket(bucket.id); }}
                  onDragLeave={() => setDragOverBucket((b) => b === bucket.id ? null : b)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const fromBucket = e.dataTransfer.getData('source-bucket');
                    const leadId = e.dataTransfer.getData('lead-id');
                    setDragOverBucket(null);
                    setDraggingLeadId(null);
                    if (leadId) moveLeadToBucket(leadId, bucket.id, fromBucket);
                  }}
                >
                  <div className={`rounded-t-lg p-2.5 flex items-center gap-2 transition-all ${dragOverBucket === bucket.id ? 'ring-2 ring-violet-500 ring-offset-1' : ''}`} style={{ background: bucket.color + '14', borderTop: `3px solid ${bucket.color}` }}>
                    <Icon className="w-4 h-4" style={{ color: bucket.color }} />
                    <span className="text-sm font-semibold">{bucket.label.replace(/^[^\s]+\s/, '')}</span>
                    <Badge variant="outline" className="text-[10px] ml-auto">{bucket.count}</Badge>
                  </div>
                  <div className={`bg-muted/30 rounded-b-lg p-2 space-y-2 max-h-[680px] overflow-y-auto transition-colors ${dragOverBucket === bucket.id ? 'bg-violet-100/40 dark:bg-violet-950/30' : ''}`}>
                    {bucket.leads.length === 0 && (
                      <p className="text-[11px] text-muted-foreground text-center py-6 italic">{dragOverBucket === bucket.id ? 'Drop here to pin' : 'No leads in this bucket.'}</p>
                    )}
                    {bucket.leads.map((lead) => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        bucketColor={bucket.color}
                        bucketId={bucket.id}
                        reviewMode={isReviewMode}
                        discussed={discussed.has(lead.id)}
                        isDragging={draggingLeadId === lead.id}
                        onDragStart={(e) => {
                          e.dataTransfer.setData('lead-id', lead.id);
                          e.dataTransfer.setData('source-bucket', bucket.id);
                          e.dataTransfer.effectAllowed = 'move';
                          setDraggingLeadId(lead.id);
                        }}
                        onDragEnd={() => { setDraggingLeadId(null); setDragOverBucket(null); }}
                        onUnpin={(e) => unpinLead(lead.id, e)}
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

      {/* Phase 29.3: Save current view dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BookmarkPlus className="w-5 h-5 text-violet-600" /> Save view
            </DialogTitle>
            <DialogDescription>
              Saves your current bucket filter as a named preset.
              {hiddenBuckets.size === 0
                ? ' This view will show ALL buckets.'
                : ` This view will hide ${hiddenBuckets.size} bucket(s).`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <Input
              value={saveViewName}
              onChange={(e) => setSaveViewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') saveCurrentAsView(); }}
              placeholder="e.g. My Monday Standup"
              autoFocus
              maxLength={80}
              data-testid="save-view-name-input"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>Cancel</Button>
            <Button onClick={saveCurrentAsView} data-testid="confirm-save-view-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Start session dialog */}
      <Dialog open={showStartDialog} onOpenChange={setShowStartDialog}>        <DialogContent>
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

const LeadCard = ({ lead, bucketColor, bucketId, reviewMode, discussed, isDragging, onClick, onOpenLead, onDragStart, onDragEnd, onUnpin }) => {
  const HealthIcon = lead.health_band === 'hot' ? Flame : lead.health_band === 'at_risk' ? AlertTriangle : Heart;
  return (
    <div
      className={`group relative bg-white dark:bg-slate-900 rounded-md p-2.5 border-l-2 hover:shadow-md transition-all cursor-grab active:cursor-grabbing ${discussed ? 'opacity-60' : ''} ${isDragging ? 'opacity-40 scale-95' : ''}`}
      style={{ borderLeftColor: bucketColor }}
      onClick={onClick}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      data-testid={`war-room-card-${lead.id}`}
    >
      {lead.is_manual_override && (
        <button
          type="button"
          onClick={onUnpin}
          title="Manually pinned — click to unpin & resume auto-classification"
          className="absolute top-1 right-1 text-[9px] px-1 py-0.5 rounded bg-violet-100 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/60 transition-colors flex items-center gap-0.5 z-10"
          data-testid={`unpin-${lead.id}`}
        >
          <Pin className="w-2.5 h-2.5" /> pinned
        </button>
      )}
      <div className="flex items-start gap-2 mb-1">
        <div className="flex-1 min-w-0 pr-12">
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
