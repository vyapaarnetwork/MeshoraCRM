import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { ArrowLeft, Edit, Briefcase } from 'lucide-react';
import { DocumentUploadDialog, LEAD_DOCUMENT_TAGS } from '../components/DocumentUpload';
import ClosedWonWizard from '../components/ClosedWonWizard';
import api from '../utils/api';
import { toast } from 'sonner';
import { format } from 'date-fns';

import {
  LeadOverviewCard, CustomerInfoCard, CommissionBreakdownCard,
} from './leadDetail/LeadOverviewCards';
import { CommentsCard } from './leadDetail/CommentsCard';
import { AssignedPartnersCard, AssignPartnerDialog } from './leadDetail/AssignedPartners';
import { DocumentsCard } from './leadDetail/DocumentsCard';
import { FollowUpsCard } from './leadDetail/FollowUpsCard';

const LeadDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin, isSalesAssociate, canEditLeadsCompanies, canAccessCommercials } = useAuth();
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);

  // Comments
  const [newComment, setNewComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);

  // Follow-ups
  const [newFollowUp, setNewFollowUp] = useState({ date: null, notes: '', pending_with: '' });
  const [showFollowUpForm, setShowFollowUpForm] = useState(false);

  // Documents
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [documentTags, setDocumentTags] = useState(LEAD_DOCUMENT_TAGS);

  // Partners
  const [showAssignPartnerDialog, setShowAssignPartnerDialog] = useState(false);
  const [partners, setPartners] = useState([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState('');

  // Commercials
  const [commercial, setCommercial] = useState(null);
  const [showCommercialsWizard, setShowCommercialsWizard] = useState(false);
  const [wizardAutoOpenedForLead, setWizardAutoOpenedForLead] = useState(null);

  useEffect(() => {
    fetchLead();
    fetchDocuments();
    fetchDocumentTags();
    if (canEditLeadsCompanies) fetchPartners();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, canEditLeadsCompanies]);

  useEffect(() => {
    if (!lead || !canAccessCommercials) return;
    let cancelled = false;
    api.get(`/commercials/by-lead/${lead.id}`).then((r) => {
      if (cancelled) return;
      setCommercial(r.data || null);
      if (lead.status_is_won && !r.data && wizardAutoOpenedForLead !== lead.id && isAdmin) {
        setShowCommercialsWizard(true);
        setWizardAutoOpenedForLead(lead.id);
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [lead, canAccessCommercials, isAdmin, wizardAutoOpenedForLead]);

  const fetchLead = async () => {
    try {
      const res = await api.get(`/leads/${id}`);
      setLead(res.data);
    } catch (e) {
      console.error('Failed to fetch lead:', e);
      toast.error('Failed to load lead details');
      navigate('/leads');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await api.get(`/documents/entity/lead/${id}`);
      setDocuments(res.data);
    } catch (e) {
      console.error('Failed to fetch documents:', e);
    }
  };

  const fetchDocumentTags = async () => {
    try {
      const res = await api.get('/master/document-tags?entity_type=lead');
      if (res.data && res.data.length > 0) {
        setDocumentTags(res.data.map(t => ({ value: t.tag_key, label: t.name })));
      }
    } catch (e) { /* fallback to defaults */ }
  };

  const fetchPartners = async () => {
    try {
      const res = await api.get('/users?role=selling_partner');
      setPartners(res.data.filter(p => p.is_active));
    } catch (e) {
      console.error('Failed to fetch partners:', e);
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!canEditLeadsCompanies) return;
    try {
      await api.delete(`/documents/${docId}`);
      toast.success('Document deleted');
      fetchDocuments();
    } catch (e) {
      toast.error('Failed to delete document');
    }
  };

  const handleAssignPartner = async () => {
    if (!selectedPartnerId) {
      toast.error('Please select a partner');
      return;
    }
    try {
      await api.post(`/leads/${id}/assign-partner`, { partner_id: selectedPartnerId });
      toast.success('Partner assigned successfully');
      setShowAssignPartnerDialog(false);
      setSelectedPartnerId('');
      fetchLead();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to assign partner');
    }
  };

  const handleMarkPartnerWon = async (partnerId) => {
    if (!window.confirm('Mark this partner as the winner? Other active partners will be marked as lost.')) return;
    try {
      await api.post(`/leads/${id}/mark-partner-won`, { partner_id: partnerId });
      toast.success('Partner marked as winner');
      fetchLead();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to mark partner as won');
    }
  };

  const handleRemovePartner = async (partnerId) => {
    if (!window.confirm('Remove this partner from the lead?')) return;
    try {
      await api.post(`/leads/${id}/remove-partner`, { partner_id: partnerId });
      toast.success('Partner removed from lead');
      fetchLead();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to remove partner');
    }
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setSubmittingComment(true);
    try {
      const res = await api.post(`/leads/${id}/comments`, { content: newComment });
      setLead(res.data);
      setNewComment('');
      toast.success('Comment added');
    } catch (err) {
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
      const res = await api.post(`/leads/${id}/follow-ups`, {
        scheduled_date: format(newFollowUp.date, 'yyyy-MM-dd'),
        notes: newFollowUp.notes,
        pending_with: newFollowUp.pending_with || null,
      });
      setLead(res.data);
      setNewFollowUp({ date: null, notes: '', pending_with: '' });
      setShowFollowUpForm(false);
      toast.success('Follow-up scheduled');
    } catch (e) {
      toast.error('Failed to schedule follow-up');
    }
  };

  const handleCompleteFollowUp = async (fid) => {
    try {
      const res = await api.put(`/leads/${id}/follow-ups/${fid}/complete`);
      setLead(res.data);
      toast.success('Follow-up marked as complete');
    } catch (e) {
      toast.error('Failed to update follow-up');
    }
  };

  if (loading) return <LeadDetailSkeleton />;
  if (!lead) return null;

  return (
    <div className="space-y-6" data-testid="lead-detail-page">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/leads')} data-testid="back-btn">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Leads
        </Button>
        <div className="flex-1" />
        {(isAdmin || canAccessCommercials) && (
          <Button
            variant={commercial ? 'outline' : 'default'}
            onClick={() => setShowCommercialsWizard(true)}
            data-testid="setup-commercials-btn"
          >
            <Briefcase className="w-4 h-4 mr-2" />
            {commercial ? 'Open Commercials' : 'Set Up Commercials'}
          </Button>
        )}
        {canEditLeadsCompanies && !isSalesAssociate && (
          <Button onClick={() => navigate(`/leads/${id}/edit`)} data-testid="edit-lead-btn">
            <Edit className="w-4 h-4 mr-2" />
            Edit Lead
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <LeadOverviewCard lead={lead} />
          <CustomerInfoCard lead={lead} />
          <CommissionBreakdownCard lead={lead} />
          <CommentsCard
            comments={lead.comments || []}
            newComment={newComment}
            setNewComment={setNewComment}
            submitting={submittingComment}
            onSubmit={handleAddComment}
          />
          <DocumentsCard
            documents={documents}
            canDelete={canEditLeadsCompanies}
            onDelete={handleDeleteDocument}
            onUploadClick={() => setShowUploadDialog(true)}
          />
          {canEditLeadsCompanies && (
            <AssignedPartnersCard
              lead={lead}
              onAssignClick={() => setShowAssignPartnerDialog(true)}
              onMarkWon={handleMarkPartnerWon}
              onRemove={handleRemovePartner}
            />
          )}
        </div>

        <div className="space-y-6">
          <FollowUpsCard
            followUps={lead.follow_ups || []}
            showFollowUpForm={showFollowUpForm}
            setShowFollowUpForm={setShowFollowUpForm}
            newFollowUp={newFollowUp}
            setNewFollowUp={setNewFollowUp}
            onAdd={handleAddFollowUp}
            onComplete={handleCompleteFollowUp}
          />
        </div>
      </div>

      <DocumentUploadDialog
        open={showUploadDialog}
        onOpenChange={setShowUploadDialog}
        entityType="lead"
        entityId={id}
        tags={documentTags}
        onUploadComplete={fetchDocuments}
      />

      <AssignPartnerDialog
        open={showAssignPartnerDialog}
        onOpenChange={setShowAssignPartnerDialog}
        partners={partners}
        selectedPartnerId={selectedPartnerId}
        setSelectedPartnerId={setSelectedPartnerId}
        lead={lead}
        onConfirm={handleAssignPartner}
      />

      <ClosedWonWizard
        open={showCommercialsWizard}
        onOpenChange={setShowCommercialsWizard}
        lead={lead}
        existingCommercial={commercial}
      />
    </div>
  );
};

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
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>
);

export default LeadDetail;
