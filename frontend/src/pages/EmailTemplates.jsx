import { useState, useEffect } from 'react';
import DOMPurify from 'dompurify';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import { 
  Mail, 
  Edit, 
  Eye, 
  RotateCcw, 
  Save, 
  Loader2, 
  Copy, 
  Check,
  FileText,
  UserPlus,
  RefreshCw,
  Trophy,
  XCircle,
  Clock,
  Info
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Event icons mapping
const EVENT_ICONS = {
  new_lead: FileText,
  lead_assigned: UserPlus,
  lead_status_changed: RefreshCw,
  lead_won: Trophy,
  lead_lost: XCircle,
  follow_up_reminder: Clock,
};

// Event colors
const EVENT_COLORS = {
  new_lead: 'bg-blue-100 text-blue-700',
  lead_assigned: 'bg-green-100 text-green-700',
  lead_status_changed: 'bg-purple-100 text-purple-700',
  lead_won: 'bg-emerald-100 text-emerald-700',
  lead_lost: 'bg-red-100 text-red-700',
  follow_up_reminder: 'bg-amber-100 text-amber-700',
};

const EmailTemplates = () => {
  const { isAdmin } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewContent, setPreviewContent] = useState({ subject: '', body: '' });
  const [formData, setFormData] = useState({
    subject: '',
    body: '',
    is_enabled: true
  });
  const [saving, setSaving] = useState(false);
  const [copiedVar, setCopiedVar] = useState(null);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await api.get('/email-templates');
      setTemplates(response.data);
    } catch (error) {
      toast.error('Failed to load email templates');
    } finally {
      setLoading(false);
    }
  };

  const openEditDialog = (template) => {
    setSelectedTemplate(template);
    setFormData({
      subject: template.subject,
      body: template.body,
      is_enabled: template.is_enabled
    });
    setEditDialogOpen(true);
  };

  const handleSave = async () => {
    if (!selectedTemplate) return;
    
    setSaving(true);
    try {
      await api.put(`/email-templates/${selectedTemplate.event_type}`, formData);
      toast.success('Template saved successfully');
      fetchTemplates();
      setEditDialogOpen(false);
    } catch (error) {
      toast.error('Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (eventType) => {
    if (!confirm('Are you sure you want to reset this template to default?')) return;
    
    try {
      await api.post(`/email-templates/${eventType}/reset`);
      toast.success('Template reset to default');
      fetchTemplates();
      setEditDialogOpen(false);
    } catch (error) {
      toast.error('Failed to reset template');
    }
  };

  const handlePreview = async () => {
    if (!selectedTemplate) return;
    
    try {
      const response = await api.post(`/email-templates/${selectedTemplate.event_type}/preview`, formData);
      setPreviewContent(response.data);
      setPreviewDialogOpen(true);
    } catch (error) {
      toast.error('Failed to generate preview');
    }
  };

  const handleToggleEnabled = async (template) => {
    try {
      await api.put(`/email-templates/${template.event_type}`, {
        is_enabled: !template.is_enabled
      });
      toast.success(`Template ${template.is_enabled ? 'disabled' : 'enabled'}`);
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to update template');
    }
  };

  const copyVariable = (variable) => {
    navigator.clipboard.writeText(variable);
    setCopiedVar(variable);
    setTimeout(() => setCopiedVar(null), 2000);
  };

  const insertVariable = (variable) => {
    setFormData(prev => ({
      ...prev,
      body: prev.body + variable
    }));
    toast.success('Variable inserted into body');
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Access denied. Admin only.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="email-templates-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Email Templates</h1>
          <p className="text-muted-foreground mt-1">
            Configure automated email notifications for different events
          </p>
        </div>
      </div>

      {/* Templates List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {templates.map((template) => {
            const Icon = EVENT_ICONS[template.event_type] || Mail;
            return (
              <Card key={template.event_type} data-testid={`template-card-${template.event_type}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${EVENT_COLORS[template.event_type] || 'bg-gray-100'}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <CardTitle className="text-base">{template.event_label}</CardTitle>
                        <CardDescription className="text-xs mt-0.5">
                          {template.variables?.length || 0} variables available
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={template.is_enabled}
                        onCheckedChange={() => handleToggleEnabled(template)}
                        data-testid={`toggle-${template.event_type}`}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Subject</p>
                      <p className="text-sm font-medium truncate">{template.subject}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => openEditDialog(template)}
                        data-testid={`edit-${template.event_type}`}
                      >
                        <Edit className="w-4 h-4 mr-1" />
                        Edit
                      </Button>
                      <Badge variant={template.is_enabled ? 'default' : 'secondary'}>
                        {template.is_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                      {template.updated_at && (
                        <span className="text-xs text-muted-foreground">
                          Modified
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5" />
              Edit Email Template
            </DialogTitle>
            <DialogDescription>
              {selectedTemplate?.event_label} - Customize the email content and subject line
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto">
            <Tabs defaultValue="editor" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="editor">Editor</TabsTrigger>
                <TabsTrigger value="variables">Available Variables</TabsTrigger>
              </TabsList>

              <TabsContent value="editor" className="space-y-4 mt-4">
                {/* Enable/Disable Toggle */}
                <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div>
                    <p className="font-medium text-sm">Enable this email</p>
                    <p className="text-xs text-muted-foreground">When disabled, this email won't be sent</p>
                  </div>
                  <Switch
                    checked={formData.is_enabled}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_enabled: checked })}
                  />
                </div>

                {/* Subject */}
                <div className="space-y-2">
                  <Label>Email Subject</Label>
                  <Input
                    value={formData.subject}
                    onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                    placeholder="Enter email subject..."
                    data-testid="template-subject-input"
                  />
                  <p className="text-xs text-muted-foreground">
                    You can use variables like {"{{lead_title}}"} in the subject
                  </p>
                </div>

                {/* Body */}
                <div className="space-y-2">
                  <Label>Email Body (HTML)</Label>
                  <Textarea
                    value={formData.body}
                    onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                    placeholder="Enter email body (HTML supported)..."
                    className="min-h-[300px] font-mono text-sm"
                    data-testid="template-body-input"
                  />
                  <p className="text-xs text-muted-foreground">
                    HTML formatting is supported. Use variables tab to see available placeholders.
                  </p>
                </div>
              </TabsContent>

              <TabsContent value="variables" className="mt-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Info className="w-4 h-4" />
                      Template Variables
                    </CardTitle>
                    <CardDescription>
                      Click on a variable to copy it, or use the insert button to add it to the body
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {selectedTemplate?.variables?.map((variable, index) => (
                          <div 
                            key={index}
                            className="flex items-center justify-between p-3 bg-muted rounded-lg hover:bg-muted/80 transition-colors"
                          >
                            <div className="flex-1">
                              <code className="text-sm font-mono bg-background px-2 py-1 rounded">
                                {variable.key}
                              </code>
                              <p className="text-xs text-muted-foreground mt-1">
                                {variable.description}
                              </p>
                            </div>
                            <div className="flex items-center gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => copyVariable(variable.key)}
                                title="Copy to clipboard"
                              >
                                {copiedVar === variable.key ? (
                                  <Check className="w-4 h-4 text-green-600" />
                                ) : (
                                  <Copy className="w-4 h-4" />
                                )}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => insertVariable(variable.key)}
                              >
                                Insert
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 sm:gap-0">
            <Button 
              variant="outline" 
              onClick={() => handleReset(selectedTemplate?.event_type)}
              className="text-destructive hover:text-destructive"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to Default
            </Button>
            <div className="flex-1" />
            <Button variant="outline" onClick={handlePreview}>
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Button>
            <Button onClick={handleSave} disabled={saving} data-testid="save-template-btn">
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Save Template
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="w-5 h-5" />
              Email Preview
            </DialogTitle>
            <DialogDescription>
              Preview with sample data - actual emails will use real lead information
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4">
            {/* Subject Preview */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Subject</Label>
              <div className="p-3 bg-muted rounded-lg">
                <p className="font-medium">{previewContent.subject}</p>
              </div>
            </div>

            {/* Body Preview */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Body</Label>
              <div className="border rounded-lg overflow-hidden">
                <div 
                  className="p-4 bg-white"
                  dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(previewContent.body || '', {
                      USE_PROFILES: { html: true },
                      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
                      FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus']
                    })
                  }}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmailTemplates;
