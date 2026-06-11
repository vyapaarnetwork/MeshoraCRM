import { useState, useMemo, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Separator } from '../../components/ui/separator';
import { Avatar, AvatarFallback } from '../../components/ui/avatar';
import { ScrollArea } from '../../components/ui/scroll-area';
import { MessageSquare, CornerDownRight, Reply, X, Sparkles, AlertTriangle, Lightbulb, ArrowRight, Loader2 } from 'lucide-react';
import api, { formatDateTime, getRoleLabel, getRoleColor } from '../../utils/api';
import { toast } from 'sonner';
import CommentInputWithMentions from '../../components/CommentInputWithMentions';
import AIActionSuggestions from '../../components/AIActionSuggestions';

const SENTIMENT_BADGES = {
  positive: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  neutral: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  negative: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  mixed: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
};

const MeetingSummaryRender = ({ summary }) => (
  <div className="mt-2 rounded-lg border border-violet-200 dark:border-violet-900 bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/30 dark:to-indigo-950/30 p-3 space-y-2">
    <div className="flex items-center gap-1.5">
      <Sparkles className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
      <span className="text-xs font-semibold uppercase tracking-wider text-violet-700 dark:text-violet-300">AI Meeting Summary</span>
      {summary.sentiment && (
        <Badge className={`text-[10px] ml-auto ${SENTIMENT_BADGES[summary.sentiment] || SENTIMENT_BADGES.neutral}`}>
          {summary.sentiment}
        </Badge>
      )}
    </div>
    <p className="text-sm leading-relaxed">{summary.summary}</p>
    {summary.risks?.length > 0 && (
      <div className="text-xs">
        <span className="flex items-center gap-1 font-semibold text-rose-700 dark:text-rose-400 mb-0.5">
          <AlertTriangle className="w-3 h-3" /> Risks
        </span>
        <ul className="pl-3 space-y-0.5 list-disc text-muted-foreground">
          {summary.risks.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    )}
    {summary.opportunities?.length > 0 && (
      <div className="text-xs">
        <span className="flex items-center gap-1 font-semibold text-amber-700 dark:text-amber-400 mb-0.5">
          <Lightbulb className="w-3 h-3" /> Opportunities
        </span>
        <ul className="pl-3 space-y-0.5 list-disc text-muted-foreground">
          {summary.opportunities.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    )}
    {summary.next_steps?.length > 0 && (
      <div className="text-xs">
        <span className="flex items-center gap-1 font-semibold text-sky-700 dark:text-sky-400 mb-0.5">
          <ArrowRight className="w-3 h-3" /> Next steps
        </span>
        <ul className="pl-3 space-y-0.5 list-disc text-muted-foreground">
          {summary.next_steps.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    )}
  </div>
);

const renderCommentBody = (text = '') => {
  const parts = text.split(/(@[a-zA-Z][a-zA-Z0-9_.\-]{1,40})/g);
  return parts.map((p, i) =>
    p.startsWith('@')
      ? <span key={i} className="text-violet-600 dark:text-violet-400 font-medium">{p}</span>
      : <span key={i}>{p}</span>
  );
};

const CommentItem = (props) => {
  const {
    comment, depth = 0, onReply, replyingTo, newReply, setNewReply,
    submittingReply, onSubmitReply, onCancelReply, replies = [],
    onAIAnalyze, aiBusyId,
  } = props;
  const isReplying = replyingTo === comment.id;
  return (
    <div className={depth > 0 ? 'pl-5 border-l border-slate-200 dark:border-slate-700 ml-3' : ''}>
      <div className="flex gap-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs bg-primary text-white">
            {comment.user_name?.charAt(0)}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium text-sm">{comment.user_name}</span>
            <Badge variant="secondary" className={`text-xs ${getRoleColor(comment.user_role)}`}>
              {getRoleLabel(comment.user_role)}
            </Badge>
            <span className="text-xs text-muted-foreground">{formatDateTime(comment.created_at)}</span>
          </div>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words">
            {renderCommentBody(comment.content)}
          </p>
          {comment.meeting_summary && <MeetingSummaryRender summary={comment.meeting_summary} />}
          {!isReplying && depth < 3 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground hover:text-primary mt-0.5"
              onClick={() => onReply(comment.id)}
              data-testid={`reply-btn-${comment.id}`}
            >
              <Reply className="w-3 h-3 mr-1" />
              Reply
            </Button>
          )}
          {!isReplying && onAIAnalyze && !comment.meeting_summary && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 hover:bg-violet-50 dark:hover:bg-violet-950/40 mt-0.5"
              onClick={() => onAIAnalyze(comment)}
              disabled={aiBusyId === comment.id}
              data-testid={`ai-actions-btn-${comment.id}`}
            >
              {aiBusyId === comment.id
                ? <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                : <Sparkles className="w-3 h-3 mr-1" />}
              AI actions
            </Button>
          )}
          {isReplying && (
            <div className="mt-2 space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CornerDownRight className="w-3 h-3" />
                Replying to <span className="font-medium">{comment.user_name}</span>
                <button
                  type="button"
                  onClick={onCancelReply}
                  className="hover:text-foreground ml-1"
                  data-testid="cancel-reply-btn"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <CommentInputWithMentions
                value={newReply}
                onChange={setNewReply}
                submitting={submittingReply}
                onSubmit={onSubmitReply}
                placeholder="Write a reply… use @ to mention"
              />
            </div>
          )}
        </div>
      </div>
      {replies.length > 0 && (
        <div className="mt-3 space-y-3">
          {replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              depth={depth + 1}
              onReply={onReply}
              replyingTo={replyingTo}
              newReply={newReply}
              setNewReply={setNewReply}
              submittingReply={submittingReply}
              onSubmitReply={onSubmitReply}
              onCancelReply={onCancelReply}
              replies={reply._children || []}
              onAIAnalyze={onAIAnalyze}
              aiBusyId={aiBusyId}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const CommentsCard = ({
  comments = [], newComment, setNewComment, submitting, onSubmit, onSubmitReply,
  leadId, onActionsCreated, autoAnalyze,
}) => {
  const [replyingTo, setReplyingTo] = useState(null);
  const [newReply, setNewReply] = useState('');
  const [submittingReply, setSubmittingReply] = useState(false);

  // Phase 35 — AI-driven one-click Action Item / Follow-Up generation
  const [aiData, setAiData] = useState(null);
  const [aiBusyId, setAiBusyId] = useState(null);
  const [aiAutoLoading, setAiAutoLoading] = useState(false);
  const lastAutoTs = useRef(null);

  const analyze = async (text, { silent = false, commentId = null } = {}) => {
    if (!leadId || !text?.trim()) return;
    if (commentId) setAiBusyId(commentId); else setAiAutoLoading(true);
    try {
      const r = await api.post(`/leads/${leadId}/ai/suggest-actions`, { text });
      const n = (r.data?.tasks?.length || 0) + (r.data?.follow_ups?.length || 0);
      if (n > 0) setAiData(r.data);
      else if (!silent) toast.info('No actionable items found in this discussion');
    } catch (e) {
      if (!silent) toast.error(e.response?.data?.detail || 'AI analysis failed');
    } finally {
      setAiBusyId(null);
      setAiAutoLoading(false);
    }
  };

  // Auto-analyze a freshly posted discussion (silent — only shows panel when items found)
  useEffect(() => {
    if (autoAnalyze?.ts && autoAnalyze.ts !== lastAutoTs.current) {
      lastAutoTs.current = autoAnalyze.ts;
      analyze(autoAnalyze.text, { silent: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAnalyze]);

  // Build thread tree
  const tree = useMemo(() => {
    const byId = {};
    comments.forEach((c) => { byId[c.id] = { ...c, _children: [] }; });
    const roots = [];
    comments.forEach((c) => {
      const node = byId[c.id];
      if (c.parent_comment_id && byId[c.parent_comment_id]) {
        byId[c.parent_comment_id]._children.push(node);
      } else {
        roots.push(node);
      }
    });
    // newest first at root level
    return roots.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  }, [comments]);

  const handleReplySubmit = async (e) => {
    e?.preventDefault?.();
    if (!newReply.trim() || !replyingTo) return;
    setSubmittingReply(true);
    try {
      await onSubmitReply(newReply, replyingTo);
      setNewReply('');
      setReplyingTo(null);
    } finally {
      setSubmittingReply(false);
    }
  };

  return (
    <Card data-testid="comments-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2" data-testid="discussions-title">
          <MessageSquare className="w-5 h-5 text-primary" />
          Discussions ({comments.length})
          {aiAutoLoading && (
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-normal text-violet-600 dark:text-violet-400" data-testid="ai-analyzing-chip">
              <Loader2 className="w-3 h-3 animate-spin" />
              AI analyzing…
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <CommentInputWithMentions
          value={newComment}
          onChange={setNewComment}
          submitting={submitting}
          onSubmit={onSubmit}
        />
        {aiData && (
          <AIActionSuggestions
            leadId={leadId}
            data={aiData}
            onDismiss={() => setAiData(null)}
            onCreated={onActionsCreated}
          />
        )}
        <Separator />
        <ScrollArea className="h-[360px]">
          <div className="space-y-4">
            {tree.length > 0 ? (
              tree.map((c) => (
                <CommentItem
                  key={c.id}
                  comment={c}
                  depth={0}
                  onReply={(id) => { setReplyingTo(id); setNewReply(''); }}
                  replyingTo={replyingTo}
                  newReply={newReply}
                  setNewReply={setNewReply}
                  submittingReply={submittingReply}
                  onSubmitReply={handleReplySubmit}
                  onCancelReply={() => { setReplyingTo(null); setNewReply(''); }}
                  replies={c._children || []}
                  onAIAnalyze={leadId ? (cm) => analyze(cm.content, { commentId: cm.id }) : null}
                  aiBusyId={aiBusyId}
                />
              ))
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No discussions yet. Use <code>@</code> to mention a teammate.
              </p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default CommentsCard;
