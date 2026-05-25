import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Paperclip, Upload } from 'lucide-react';
import { DocumentList } from '../../components/DocumentUpload';

export const DocumentsCard = ({ documents, canDelete, onDelete, onUploadClick }) => (
  <Card data-testid="documents-section">
    <CardHeader>
      <div className="flex items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Paperclip className="w-5 h-5 text-primary" />
          Documents ({documents.length})
        </CardTitle>
        <Button size="sm" onClick={onUploadClick} data-testid="upload-document-btn">
          <Upload className="w-4 h-4 mr-2" />
          Upload
        </Button>
      </div>
    </CardHeader>
    <CardContent>
      <DocumentList
        documents={documents}
        canDelete={canDelete}
        onDelete={onDelete}
        emptyMessage="No documents uploaded for this lead"
      />
    </CardContent>
  </Card>
);

export default DocumentsCard;
