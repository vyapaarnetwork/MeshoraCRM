/**
 * Phase 40.3 — 3-level Invoice Files panel for a single Commercial.
 *
 * Renders three stacked sections, each representing a distinct invoice flow:
 *   1. Selling Partner invoice — what the partner raises on Vyapaar
 *   2. Vyapaar Commission invoice — Vyapaar's invoice to the customer for the commission share
 *   3. Referral Partner invoice — any referral payout invoice received from a sales associate
 *
 * Each section supports: upload (PDF/image), list with original filename + size +
 * uploader + date, download (signed-url), delete, and an optional link to a
 * Revenue Event so the Finance team can match an uploaded invoice to a specific
 * billing cycle / milestone.
 *
 * RBAC: backend already restricts uploads to super_admin / is_finance /
 * is_vyapaar_ops. Non-Vyapaar users see read-only.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Upload, Download, Trash2, Building2, Briefcase, Users, FileText, Loader2, Link2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import api from '../utils/api';
import { toast } from 'sonner';

const SECTIONS = [
  {
    key: 'commercial:selling_partner',
    title: 'Selling Partner Invoice',
    description: 'Invoice raised by the Selling Partner on the customer / Vyapaar.',
    icon: Briefcase,
    tone: 'border-indigo-200 dark:border-indigo-900',
    accent: 'text-indigo-700 dark:text-indigo-300',
  },
  {
    key: 'commercial:vyapaar_commission',
    title: 'Vyapaar Commission Invoice',
    description: 'Vyapaar Network\u2019s commission invoice for this deal.',
    icon: Building2,
    tone: 'border-emerald-200 dark:border-emerald-900',
    accent: 'text-emerald-700 dark:text-emerald-300',
  },
  {
    key: 'commercial:referral_partner',
    title: 'Referral Partner Invoice',
    description: 'Invoice received from the Sales Associate / Selling Partner who referred this lead.',
    icon: Users,
    tone: 'border-rose-200 dark:border-rose-900',
    accent: 'text-rose-700 dark:text-rose-300',
  },
];

const fmtSize = (b) => {
  if (!b) return '';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(2)} MB`;
};

const InvoiceSection = ({ section, commercialId, docs, revenueEvents, onUploaded, onDeleted, canEdit, highlight, defaultRevenueEventId }) => {
  const [uploading, setUploading] = useState(false);
  const [revenueEventId, setRevenueEventId] = useState(defaultRevenueEventId || '');
  const inputRef = useRef(null);
  const cardRef = useRef(null);

  useEffect(() => {
    if (defaultRevenueEventId) setRevenueEventId(defaultRevenueEventId);
  }, [defaultRevenueEventId]);

  useEffect(() => {
    if (highlight && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlight]);

  const handleSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = '';
  };

  const handleUpload = async (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      return toast.error('File too large (max 10 MB)');
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('entity_type', section.key);
      fd.append('entity_id', commercialId);
      fd.append('tag', section.key.split(':')[1] || 'invoice');
      fd.append('description', section.title);
      if (revenueEventId) fd.append('revenue_event_id', revenueEventId);
      const res = await api.post('/documents/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(`Uploaded ${file.name}`);
      onUploaded(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); }
  };

  const download = async (doc) => {
    try {
      const res = await api.get(`/documents/${doc.id}/signed-url`);
      window.open(res.data.url, '_blank');
    } catch (e) {
      toast.error('Could not generate download link');
    }
  };

  const remove = async (doc) => {
    if (!window.confirm(`Delete ${doc.original_filename}?`)) return;
    try {
      await api.delete(`/documents/${doc.id}`);
      toast.success('Deleted');
      onDeleted(doc.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const Icon = section.icon;
  return (
    <Card ref={cardRef} className={`border-l-4 ${section.tone} ${highlight ? 'ring-2 ring-amber-400 dark:ring-amber-500 shadow-md' : ''}`} data-testid={`invoice-section-${section.key.split(':')[1]}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <CardTitle className={`text-base flex items-center gap-2 ${section.accent}`}>
              <Icon className="w-4 h-4" />
              {section.title}
              <Badge variant="outline" className="ml-1 text-[10px]">{docs.length}</Badge>
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">{section.description}</CardDescription>
          </div>
          {canEdit && (
            <div className="flex items-center gap-2">
              {revenueEvents.length > 0 && (
                <Select value={revenueEventId || 'none'} onValueChange={(v) => setRevenueEventId(v === 'none' ? '' : v)}>
                  <SelectTrigger className="h-9 text-xs w-[260px]" data-testid={`re-link-${section.key.split(':')[1]}`}>
                    <SelectValue placeholder="Link to revenue event (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No link (commercial-level)</SelectItem>
                    {revenueEvents.map((re) => (
                      <SelectItem key={re.id} value={re.id}>
                        {re.name} · {re.revenue_type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <input ref={inputRef} type="file" className="hidden" onChange={handleSelect} accept=".pdf,.jpg,.jpeg,.png,.webp" data-testid={`upload-input-${section.key.split(':')[1]}`} />
              <Button size="sm" disabled={uploading} onClick={() => inputRef.current?.click()} data-testid={`upload-btn-${section.key.split(':')[1]}`}>
                {uploading ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Uploading…</> : <><Upload className="w-3 h-3 mr-1" /> Upload</>}
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {docs.length === 0 ? (
          <div className="text-xs text-muted-foreground py-4 text-center border-2 border-dashed rounded-md">
            No invoices uploaded yet. {canEdit && 'Click Upload to add one.'}
          </div>
        ) : (
          <div className="space-y-1.5">
            {docs.map((doc) => {
              const re = revenueEvents.find((r) => r.id === doc.revenue_event_id);
              return (
                <div key={doc.id} className="flex items-center gap-3 p-2.5 rounded-md hover:bg-muted/40 border" data-testid={`invoice-row-${doc.id}`}>
                  <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{doc.original_filename}</div>
                    <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 flex-wrap">
                      <span>{fmtSize(doc.file_size)}</span>
                      <span>·</span>
                      <span>{doc.uploaded_by_name || 'Unknown'}</span>
                      <span>·</span>
                      <span>{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                      {re && (
                        <>
                          <span>·</span>
                          <span className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-300">
                            <Link2 className="w-3 h-3" />
                            {re.name}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <Button size="icon" variant="ghost" onClick={() => download(doc)} title="Download" data-testid={`download-invoice-${doc.id}`}>
                    <Download className="w-3.5 h-3.5" />
                  </Button>
                  {canEdit && (
                    <Button size="icon" variant="ghost" onClick={() => remove(doc)} title="Delete" data-testid={`delete-invoice-${doc.id}`}>
                      <Trash2 className="w-3.5 h-3.5 text-rose-500" />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const CommercialInvoiceUploads = ({ commercialId, currentUser, initialRevenueEventId }) => {
  const [docs, setDocs] = useState([]);
  const [revenueEvents, setRevenueEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const canEdit = useMemo(() => {
    if (!currentUser) return true;  // fall back to true; backend will 403 if not allowed
    return (
      currentUser.role === 'super_admin'
      || currentUser.is_finance
      || currentUser.is_vyapaar_ops
    );
  }, [currentUser]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [docsRes, reRes] = await Promise.all([
        api.get(`/documents/entity/commercial:any/${commercialId}`),
        api.get(`/commercials/${commercialId}/revenue-events`).catch(() => ({ data: [] })),
      ]);
      setDocs(docsRes.data || []);
      setRevenueEvents(reRes.data || []);
    } catch (e) {
      toast.error('Failed to load invoice files');
    } finally { setLoading(false); }
  }, [commercialId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const grouped = useMemo(() => {
    const m = { 'commercial:selling_partner': [], 'commercial:vyapaar_commission': [], 'commercial:referral_partner': [] };
    docs.forEach((d) => { if (m[d.entity_type]) m[d.entity_type].push(d); });
    return m;
  }, [docs]);

  if (loading) {
    return <div className="text-sm text-muted-foreground py-10 text-center">Loading invoice files…</div>;
  }

  return (
    <div className="space-y-4" data-testid="commercial-invoice-uploads">
      {SECTIONS.map((s) => {
        const isVyapaarSection = s.key === 'commercial:vyapaar_commission';
        return (
          <InvoiceSection
            key={s.key}
            section={s}
            commercialId={commercialId}
            docs={grouped[s.key] || []}
            revenueEvents={revenueEvents}
            canEdit={canEdit}
            defaultRevenueEventId={isVyapaarSection ? initialRevenueEventId : ''}
            highlight={isVyapaarSection && !!initialRevenueEventId}
            onUploaded={(doc) => setDocs((d) => [doc, ...d])}
            onDeleted={(id) => setDocs((d) => d.filter((x) => x.id !== id))}
          />
        );
      })}
    </div>
  );
};

export default CommercialInvoiceUploads;
