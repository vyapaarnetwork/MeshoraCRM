import { useState, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { 
  Upload, 
  File, 
  FileText, 
  Image, 
  X, 
  Download, 
  Eye, 
  Trash2,
  Loader2,
  Paperclip
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Document tags for leads
export const LEAD_DOCUMENT_TAGS = [
  { value: 'proposal', label: 'Proposal' },
  { value: 'contract', label: 'Contract' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'quotation', label: 'Quotation' },
  { value: 'other', label: 'Other' }
];

// Document tags for companies
export const COMPANY_DOCUMENT_TAGS = [
  { value: 'corporate_profile', label: 'Corporate Profile' },
  { value: 'product_catalog', label: 'Product Catalog' },
  { value: 'brochure', label: 'Brochure' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'other', label: 'Other' }
];

// Get file icon based on content type
const getFileIcon = (contentType) => {
  if (contentType?.startsWith('image/')) return Image;
  if (contentType?.includes('pdf')) return FileText;
  return File;
};

// Format file size
const formatFileSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// Get tag color
const getTagColor = (tag) => {
  const colors = {
    proposal: 'bg-blue-100 text-blue-700',
    contract: 'bg-green-100 text-green-700',
    invoice: 'bg-amber-100 text-amber-700',
    quotation: 'bg-purple-100 text-purple-700',
    corporate_profile: 'bg-indigo-100 text-indigo-700',
    product_catalog: 'bg-pink-100 text-pink-700',
    brochure: 'bg-cyan-100 text-cyan-700',
    certificate: 'bg-emerald-100 text-emerald-700',
    other: 'bg-gray-100 text-gray-700'
  };
  return colors[tag] || colors.other;
};

// Document Upload Dialog Component
export const DocumentUploadDialog = ({ 
  open, 
  onOpenChange, 
  entityType, 
  entityId, 
  onUploadComplete,
  tags = LEAD_DOCUMENT_TAGS
}) => {
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [tag, setTag] = useState('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.size > 10 * 1024 * 1024) {
        toast.error('File too large. Maximum size is 10MB.');
        return;
      }
      setFile(selectedFile);
    }
  };

  const handleUpload = async () => {
    if (!file || !tag) {
      toast.error('Please select a file and tag');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('entity_type', entityType);
      formData.append('entity_id', entityId);
      formData.append('tag', tag);
      if (description) {
        formData.append('description', description);
      }

      await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      toast.success('Document uploaded successfully');
      setFile(null);
      setTag('');
      setDescription('');
      onOpenChange(false);
      if (onUploadComplete) onUploadComplete();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setTag('');
    setDescription('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
          <DialogDescription>
            Upload a document (max 10MB). Supported formats: PDF, Word, Excel, Images.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* File Input */}
          <div className="space-y-2">
            <Label>Select File *</Label>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.gif"
            />
            {file ? (
              <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                <File className="w-8 h-8 text-primary" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => setFile(null)}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <Button 
                variant="outline" 
                className="w-full h-24 border-dashed"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="flex flex-col items-center gap-2">
                  <Upload className="w-6 h-6 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Click to select a file</span>
                </div>
              </Button>
            )}
          </div>

          {/* Tag Selection */}
          <div className="space-y-2">
            <Label>Document Type *</Label>
            <Select value={tag} onValueChange={setTag}>
              <SelectTrigger data-testid="document-tag-select">
                <SelectValue placeholder="Select document type" />
              </SelectTrigger>
              <SelectContent>
                {tags.map(t => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label>Description (Optional)</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the document"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={uploading}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={uploading || !file || !tag}>
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4 mr-2" />
                Upload
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Document List Component
export const DocumentList = ({ 
  documents, 
  onDelete, 
  canDelete = false,
  emptyMessage = 'No documents uploaded yet'
}) => {
  // Phase 36 — production-friendly download: ask the backend for a signed URL
  // (no Authorization header needed), then open it directly. This bypasses the
  // axios+blob path that was failing on cross-domain deployments (app.vyapaar.net).
  const handleDownload = async (doc) => {
    try {
      const { data } = await api.get(`/documents/${doc.id}/signed-url`);
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const link = document.createElement('a');
      link.href = `${BACKEND_URL}${data.url}`;
      link.setAttribute('download', doc.original_filename);
      link.rel = 'noopener noreferrer';
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || 'Unknown error';
      toast.error(`Failed to download document: ${detail}`);
    }
  };

  const handleView = async (doc) => {
    try {
      const { data } = await api.get(`/documents/${doc.id}/signed-url`);
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      // Open the inline-flavoured URL in a new tab so PDFs / images render in-browser
      window.open(`${BACKEND_URL}${data.preview_url}`, '_blank', 'noopener,noreferrer');
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || 'Unknown error';
      toast.error(`Failed to open document: ${detail}`);
    }
  };

  if (!documents || documents.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Paperclip className="w-10 h-10 mx-auto mb-2 opacity-50" />
        <p className="text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map(doc => {
        const FileIcon = getFileIcon(doc.content_type);
        return (
          <Card key={doc.id} className="overflow-hidden">
            <CardContent className="p-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-muted rounded-lg">
                  <FileIcon className="w-6 h-6 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium truncate">{doc.original_filename}</p>
                    <Badge className={getTagColor(doc.tag)} variant="secondary">
                      {doc.tag.replace('_', ' ')}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                    <span>{formatFileSize(doc.file_size)}</span>
                    {doc.uploaded_by_name && (
                      <span>Uploaded by {doc.uploaded_by_name}</span>
                    )}
                  </div>
                  {doc.description && (
                    <p className="text-xs text-muted-foreground mt-1">{doc.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={() => handleView(doc)}
                    title="View"
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={() => handleDownload(doc)}
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                  {canDelete && onDelete && (
                    <Button 
                      variant="ghost" 
                      size="icon"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDelete(doc.id)}
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

export default DocumentUploadDialog;
