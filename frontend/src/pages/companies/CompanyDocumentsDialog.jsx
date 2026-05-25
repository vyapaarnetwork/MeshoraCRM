import { Button } from '../../components/ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import { Paperclip, Upload } from 'lucide-react';
import { DocumentList } from '../../components/DocumentUpload';

export const CompanyDocumentsDialog = ({
  open,
  onOpenChange,
  companyName,
  documents,
  onUploadClick,
  onDelete,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Paperclip className="w-5 h-5" />
          Documents - {companyName}
        </DialogTitle>
        <DialogDescription>
          Corporate profiles, brochures, and other company documents
        </DialogDescription>
      </DialogHeader>
      <div className="py-4">
        <div className="flex justify-end mb-4">
          <Button size="sm" onClick={onUploadClick} data-testid="upload-company-doc-btn">
            <Upload className="w-4 h-4 mr-2" />
            Upload Document
          </Button>
        </div>
        <DocumentList
          documents={documents}
          canDelete={true}
          onDelete={onDelete}
          emptyMessage="No documents uploaded for this company"
        />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export default CompanyDocumentsDialog;
