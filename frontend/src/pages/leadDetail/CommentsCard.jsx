import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Separator } from '../../components/ui/separator';
import { Avatar, AvatarFallback } from '../../components/ui/avatar';
import { ScrollArea } from '../../components/ui/scroll-area';
import { MessageSquare, Send } from 'lucide-react';
import { formatDateTime, getRoleLabel, getRoleColor } from '../../utils/api';

export const CommentsCard = ({ comments = [], newComment, setNewComment, submitting, onSubmit }) => (
  <Card data-testid="comments-section">
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-primary" />
        Comments ({comments.length})
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <form onSubmit={onSubmit} className="flex gap-2">
        <Input
          placeholder="Add a comment..."
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          disabled={submitting}
          data-testid="comment-input"
        />
        <Button
          type="submit"
          disabled={submitting || !newComment.trim()}
          data-testid="submit-comment-btn"
        >
          <Send className="w-4 h-4" />
        </Button>
      </form>
      <Separator />
      <ScrollArea className="h-[300px]">
        <div className="space-y-4">
          {comments.length > 0 ? (
            comments.slice().reverse().map((comment) => (
              <div key={comment.id} className="flex gap-3">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="text-xs bg-primary text-white">
                    {comment.user_name?.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">{comment.user_name}</span>
                    <Badge variant="secondary" className={`text-xs ${getRoleColor(comment.user_role)}`}>
                      {getRoleLabel(comment.user_role)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(comment.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{comment.content}</p>
                </div>
              </div>
            ))
          ) : (
            <p className="text-center text-muted-foreground py-8">
              No comments yet. Be the first to add one!
            </p>
          )}
        </div>
      </ScrollArea>
    </CardContent>
  </Card>
);

export default CommentsCard;
