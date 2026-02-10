import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Progress } from '../components/ui/progress';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { 
  Upload, 
  Download, 
  FileSpreadsheet, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  FileText,
  Loader2,
  ArrowLeft,
  Info
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { toast } from 'sonner';

const LeadImport = () => {
  const { isAdmin, isSellingPartner, isCustomer } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  
  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchTemplate();
  }, []);

  const fetchTemplate = async () => {
    try {
      const response = await api.get('/leads/import/template');
      setTemplate(response.data);
    } catch (error) {
      toast.error('Failed to load import template');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadSample = async () => {
    try {
      const response = await api.get('/leads/import/download-sample', {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'lead_import_template.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success('Sample file downloaded');
    } catch (error) {
      toast.error('Failed to download sample file');
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        toast.error('Please select a CSV file');
        return;
      }
      setFile(selectedFile);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    setResult(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post('/leads/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setResult(response.data);
      
      if (response.data.successful > 0) {
        toast.success(`Successfully imported ${response.data.successful} leads`);
      }
      if (response.data.failed > 0) {
        toast.warning(`${response.data.failed} rows had errors`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Import failed');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="lead-import-page">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/leads')} data-testid="back-btn">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Leads
        </Button>
      </div>

      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Import Leads</h1>
        <p className="text-muted-foreground mt-1">
          Bulk import leads from a CSV file
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Instructions Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="w-5 h-5 text-primary" />
              Import Instructions
            </CardTitle>
            <CardDescription>
              Follow these steps to import leads successfully
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center text-sm font-medium text-primary">
                  1
                </div>
                <div>
                  <p className="font-medium">Download the sample template</p>
                  <p className="text-sm text-muted-foreground">
                    Get the CSV template with correct column headers
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center text-sm font-medium text-primary">
                  2
                </div>
                <div>
                  <p className="font-medium">Fill in your lead data</p>
                  <p className="text-sm text-muted-foreground">
                    Add your leads following the template format
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center text-sm font-medium text-primary">
                  3
                </div>
                <div>
                  <p className="font-medium">Upload and import</p>
                  <p className="text-sm text-muted-foreground">
                    Select your file and click import
                  </p>
                </div>
              </div>
            </div>

            <Separator />

            <Button 
              onClick={handleDownloadSample} 
              variant="outline" 
              className="w-full"
              data-testid="download-template-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              Download Sample CSV Template
            </Button>
          </CardContent>
        </Card>

        {/* Upload Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-5 h-5 text-primary" />
              Upload File
            </CardTitle>
            <CardDescription>
              Select a CSV file to import leads
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* File Input Zone */}
            <div 
              className={`
                border-2 border-dashed rounded-lg p-8 text-center transition-colors
                ${file ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}
              `}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
                data-testid="file-input"
              />
              
              {file ? (
                <div className="space-y-2">
                  <FileSpreadsheet className="w-12 h-12 mx-auto text-primary" />
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={(e) => { e.stopPropagation(); handleReset(); }}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <FileText className="w-12 h-12 mx-auto text-muted-foreground" />
                  <p className="font-medium">Click to select a CSV file</p>
                  <p className="text-sm text-muted-foreground">
                    or drag and drop here
                  </p>
                </div>
              )}
            </div>

            <Button 
              onClick={handleUpload}
              disabled={!file || uploading}
              className="w-full"
              data-testid="import-btn"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Import Leads
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Import Result */}
      {result && (
        <Card className="animate-fade-in" data-testid="import-result">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {result.failed === 0 ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : result.successful === 0 ? (
                <XCircle className="w-5 h-5 text-red-600" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-yellow-600" />
              )}
              Import Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-4 bg-muted rounded-lg">
                <p className="text-2xl font-bold">{result.total_rows}</p>
                <p className="text-sm text-muted-foreground">Total Rows</p>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">{result.successful}</p>
                <p className="text-sm text-green-700">Successful</p>
              </div>
              <div className="text-center p-4 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-600">{result.failed}</p>
                <p className="text-sm text-red-700">Failed</p>
              </div>
            </div>

            {/* Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Import Progress</span>
                <span>{Math.round((result.successful / result.total_rows) * 100)}%</span>
              </div>
              <Progress 
                value={(result.successful / result.total_rows) * 100} 
                className="h-2"
              />
            </div>

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-red-600">Errors ({result.errors.length})</h4>
                <ScrollArea className="h-[200px] border rounded-lg">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[60px]">Row</TableHead>
                        <TableHead>Errors</TableHead>
                        <TableHead>Data</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.errors.map((error, index) => (
                        <TableRow key={index}>
                          <TableCell className="font-mono">{error.row}</TableCell>
                          <TableCell>
                            <ul className="list-disc list-inside text-sm text-red-600">
                              {error.errors.map((e, i) => (
                                <li key={i}>{e}</li>
                              ))}
                            </ul>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                            {error.data?.title || error.data?.customer_name || 'N/A'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <Button onClick={() => navigate('/leads')} data-testid="view-leads-btn">
                View Imported Leads
              </Button>
              <Button variant="outline" onClick={handleReset}>
                Import More
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template Reference */}
      {template && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-primary" />
              Column Reference
            </CardTitle>
            <CardDescription>
              Required and optional columns for the import file
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Column Name</TableHead>
                    <TableHead>Required</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Example</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {template.columns.map((col) => (
                    <TableRow key={col.name}>
                      <TableCell className="font-mono text-sm">{col.name}</TableCell>
                      <TableCell>
                        <Badge variant={col.required ? "default" : "secondary"}>
                          {col.required ? "Required" : "Optional"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {col.description}
                      </TableCell>
                      <TableCell className="text-sm font-mono">{col.example}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <Separator className="my-4" />

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium mb-2">Available Categories</h4>
                <div className="flex flex-wrap gap-1">
                  {template.available_categories?.map((cat) => (
                    <Badge key={cat} variant="outline">{cat}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="font-medium mb-2">Available Statuses</h4>
                <div className="flex flex-wrap gap-1">
                  {template.available_statuses?.map((status) => (
                    <Badge key={status} variant="outline">{status}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default LeadImport;
