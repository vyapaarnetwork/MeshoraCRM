import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Skeleton } from '../components/ui/skeleton';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { Calendar } from '../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { ScrollArea } from '../components/ui/scroll-area';
import { 
  ArrowLeft, 
  Edit, 
  Building2, 
  Mail, 
  Phone, 
  User,
  Tag,
  DollarSign,
  Percent,
  CalendarIcon,
  MessageSquare,
  Plus,
  Check,
  Clock,
  Send
} from 'lucide-react';
import api, { formatCurrency, formatDate, formatDateTime, getRoleLabel, getRoleColor } from '../utils/api';
import { toast } from 'sonner';
import { format } from 'date-fns';

const LeadDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin, isSalesAssociate } = useAuth();
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [newFollowUp, setNewFollowUp] = useState({ date: null, notes: '' });
  const [showFollowUpForm, setShowFollowUpForm] = useState(false);

  useEffect(() => {
    fetchLead();
  }, [id]);

  const fetchLead = async () => {
    try {
      const response = await api.get(`/leads/${id}`);
      setLead(response.data);
    } catch (error) {
      console.error('Failed to fetch lead:', error);
      toast.error('Failed to load lead details');
      navigate('/leads');
    } finally {
      setLoading(false);
    }
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    
    setSubmittingComment(true);
    try {
      const response = await api.post(`/leads/${id}/comments`, { content: newComment });
      setLead(response.data);
      setNewComment('');
      toast.success('Comment added');
    } catch (error) {
      toast.error('Failed to add comment');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleAddFollowUp = async () => {
    if (!newFollowUp.date) {
      toast.error('Please select a date');
      return;
    }
    
    try {
      const response = await api.post(`/leads/${id}/follow-ups`, {
        scheduled_date: format(newFollowUp.date, 'yyyy-MM-dd'),
        notes: newFollowUp.notes
      });
      setLead(response.data);
      setNewFollowUp({ date: null, notes: '' });
      setShowFollowUpForm(false);
      toast.success('Follow-up scheduled');
    } catch (error) {
      toast.error('Failed to schedule follow-up');
    }
  };

  const handleCompleteFollowUp = async (followUpId) => {
    try {
      const response = await api.put(`/leads/${id}/follow-ups/${followUpId}/complete`);
      setLead(response.data);
      toast.success('Follow-up marked as complete');
    } catch (error) {
      toast.error('Failed to update follow-up');
    }
  };

  if (loading) {
    return <LeadDetailSkeleton />;
  }

  if (!lead) {
    return null;
  }

  return (
    <div className="space-y-6" data-testid="lead-detail-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <Button 
          variant="ghost" 
          onClick={() => navigate('/leads')}
          data-testid="back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Leads
        </Button>
        <div className="flex-1" />
        {!isSalesAssociate && (
          <Button 
            onClick={() => navigate(`/leads/${id}/edit`)}
            data-testid="edit-lead-btn"
          >
            <Edit className="w-4 h-4 mr-2" />
            Edit Lead
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Lead Overview */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">{lead.title}</CardTitle>
                  <CardDescription className="mt-1">
                    Created {formatDateTime(lead.created_at)} by {lead.created_by_name}
                  </CardDescription>
                </div>
                <Badge 
                  className="text-sm"
                  style={{ 
                    backgroundColor: `${lead.status_color}20`,
                    color: lead.status_color,
                    borderColor: lead.status_color
                  }}
                >
                  {lead.status_name || 'New'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {lead.description && (
                <p className="text-muted-foreground">{lead.description}</p>
              )}
              
              <div className="grid sm:grid-cols-2 gap-4">
                <InfoItem icon={Tag} label="Category" value={lead.primary_category_name} />
                {lead.secondary_category_name && (
                  <InfoItem icon={Tag} label="Sub-category" value={lead.secondary_category_name} />
                )}
                <InfoItem icon={DollarSign} label="Deal Value" value={formatCurrency(lead.deal_value)} />
                {lead.selling_partner_name && (
                  <InfoItem icon={Building2} label="Selling Partner" value={lead.selling_partner_name} />
                )}
                {lead.sales_associate_name && (
                  <InfoItem icon={User} label="Sales Associate" value={lead.sales_associate_name} />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Customer Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5 text-primary" />
                Customer Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid sm:grid-cols-2 gap-4">
                <InfoItem icon={User} label="Name" value={lead.customer_name} />
                <InfoItem icon={Mail} label="Email" value={lead.customer_email} />
                {lead.customer_phone && (
                  <InfoItem icon={Phone} label="Phone" value={lead.customer_phone} />
                )}
                {lead.customer_company && (
                  <InfoItem icon={Building2} label="Company" value={lead.customer_company} />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Commission Breakdown */}
          {lead.commission_breakdown && lead.deal_value > 0 && (
            <Card data-testid="commission-breakdown">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Percent className="w-5 h-5 text-primary" />
                  Commission Breakdown
                </CardTitle>
                <CardDescription>
                  Transparent view of how commission is distributed
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-2">
                    <span className="text-muted-foreground">Total Deal Value</span>
                    <span className="font-semibold text-lg">
                      {formatCurrency(lead.commission_breakdown.total_deal_value)}
                    </span>
                  </div>
                  <Separator />
                  <div className="flex justify-between items-center py-2">
                    <span className="text-muted-foreground">
                      Vyapaar Network ({lead.commission_breakdown.vyapaar_percentage}%)
                    </span>
                    <span className="font-medium text-primary">
                      {formatCurrency(lead.commission_breakdown.vyapaar_share)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-2">
                    <span className="text-muted-foreground">Selling Partner Share</span>
                    <span className="font-medium text-green-600">
                      {formatCurrency(lead.commission_breakdown.selling_partner_share)}
                    </span>
                  </div>
                  {lead.commission_breakdown.sales_associate_share && (
                    <div className="flex justify-between items-center py-2">
                      <span className="text-muted-foreground">
                        Sales Associate ({lead.commission_breakdown.sales_associate_percentage}% of Vyapaar share)
                      </span>
                      <span className="font-medium text-purple-600">
                        {formatCurrency(lead.commission_breakdown.sales_associate_share)}
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          <Card data-testid="comments-section">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-primary" />
                Comments ({lead.comments?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Comment Form */}
              <form onSubmit={handleAddComment} className="flex gap-2">
                <Input
                  placeholder="Add a comment..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  disabled={submittingComment}
                  data-testid="comment-input"
                />
                <Button 
                  type="submit" 
                  disabled={submittingComment || !newComment.trim()}
                  data-testid="submit-comment-btn"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </form>

              <Separator />

              {/* Comments List */}
              <ScrollArea className="h-[300px]">
                <div className="space-y-4">
                  {lead.comments?.length > 0 ? (
                    lead.comments.slice().reverse().map((comment) => (
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
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Follow-ups */}
          <Card data-testid="followups-section">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <CalendarIcon className="w-5 h-5 text-primary" />
                  Follow-ups
                </CardTitle>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => setShowFollowUpForm(!showFollowUpForm)}
                  data-testid="add-followup-btn"
                >
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Add Follow-up Form */}
              {showFollowUpForm && (
                <div className="p-4 border rounded-lg space-y-3 bg-muted/50 animate-scale-in">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start">
                        <CalendarIcon className="w-4 h-4 mr-2" />
                        {newFollowUp.date ? format(newFollowUp.date, 'PPP') : 'Pick a date'}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={newFollowUp.date}
                        onSelect={(date) => setNewFollowUp({ ...newFollowUp, date })}
                        disabled={(date) => date < new Date()}
                      />
                    </PopoverContent>
                  </Popover>
                  <Textarea
                    placeholder="Notes (optional)"
                    value={newFollowUp.notes}
                    onChange={(e) => setNewFollowUp({ ...newFollowUp, notes: e.target.value })}
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <Button 
                      size="sm" 
                      onClick={handleAddFollowUp}
                      data-testid="save-followup-btn"
                    >
                      Schedule
                    </Button>
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => setShowFollowUpForm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {/* Follow-ups List */}
              <div className="space-y-3">
                {lead.follow_ups?.length > 0 ? (
                  lead.follow_ups.map((followUp) => (
                    <div 
                      key={followUp.id} 
                      className={`p-3 border rounded-lg ${followUp.is_completed ? 'bg-muted/50' : 'bg-white'}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {followUp.is_completed ? (
                            <Check className="w-4 h-4 text-green-600" />
                          ) : (
                            <Clock className="w-4 h-4 text-orange-500" />
                          )}
                          <span className={`font-medium text-sm ${followUp.is_completed ? 'line-through text-muted-foreground' : ''}`}>
                            {formatDate(followUp.scheduled_date)}
                          </span>
                        </div>
                        {!followUp.is_completed && (
                          <Button 
                            size="sm" 
                            variant="ghost"
                            onClick={() => handleCompleteFollowUp(followUp.id)}
                            data-testid={`complete-followup-${followUp.id}`}
                          >
                            <Check className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                      {followUp.notes && (
                        <p className="text-xs text-muted-foreground">{followUp.notes}</p>
                      )}
                      {followUp.is_completed && followUp.completed_at && (
                        <p className="text-xs text-green-600 mt-1">
                          Completed on {formatDate(followUp.completed_at)}
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-center text-muted-foreground py-4 text-sm">
                    No follow-ups scheduled
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

// Info Item Component
const InfoItem = ({ icon: Icon, label, value }) => (
  <div className="flex items-start gap-3">
    <Icon className="w-4 h-4 text-muted-foreground mt-0.5" />
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value || '-'}</p>
    </div>
  </div>
);

// Loading Skeleton
const LeadDetailSkeleton = () => (
  <div className="space-y-6">
    <Skeleton className="h-10 w-32" />
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-8 w-64 mb-2" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-4 w-4" />
                  <div className="flex-1">
                    <Skeleton className="h-3 w-16 mb-1" />
                    <Skeleton className="h-4 w-24" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>
);

export default LeadDetail;
