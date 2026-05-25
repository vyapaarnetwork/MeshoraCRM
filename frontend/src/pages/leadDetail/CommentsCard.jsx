import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Separator } from '../../components/ui/separator';
import { Avatar, AvatarFallback } from '../../components/ui/avatar';
import { ScrollArea } from '../../components/ui/scroll-area';
import { MessageSquare, CornerDownRight, Reply, X } from 'lucide-react';
import { formatDateTime, getRoleLabel, getRoleColor } from '../../utils/api';
import CommentInputWithMentions from '../../components/CommentInputWithMentions';

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
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const CommentsCard = ({ comments = [], newComment, setNewComment, submitting, onSubmit, onSubmitReply }) => {
  const [replyingTo, setReplyingTo] = useState(null);
  const [newReply, setNewReply] = useState('');
  const [submittingReply, setSubmittingReply] = useState(false);

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
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          Comments ({comments.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <CommentInputWithMentions
          value={newComment}
          onChange={setNewComment}
          submitting={submitting}
          onSubmit={onSubmit}
        />
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
                />
              ))
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No comments yet. Use <code>@</code> to mention a teammate.
              </p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default CommentsCard;
