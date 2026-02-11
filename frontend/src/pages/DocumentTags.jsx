import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import { Plus, Edit, Trash2, FileText, Building2, Loader2, Tag } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Predefined colors for tags
const TAG_COLORS = [
  { value: '#3b82f6', label: 'Blue' },
  { value: '#22c55e', label: 'Green' },
  { value: '#f59e0b', label: 'Amber' },
  { value: '#a855f7', label: 'Purple' },
  { value: '#ec4899', label: 'Pink' },
  { value: '#06b6d4', label: 'Cyan' },
  { value: '#10b981', label: 'Emerald' },
  { value: '#6366f1', label: 'Indigo' },
  { value: '#ef4444', label: 'Red' },
  { value: '#6b7280', label: 'Gray' },
];

const DocumentTags = () => {
  const { isAdmin } = useAuth();
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTag, setEditingTag] = useState(null);
  const [activeTab, setActiveTab] = useState('lead');
  const [formData, setFormData] = useState({
    name: '',
    tag_key: '',
    entity_type: 'lead',
    color: '#3b82f6'
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchTags();
  }, []);

  const fetchTags = async () => {
    try {
      const response = await api.get('/master/document-tags');
      setTags(response.data);
    } catch (error) {
      toast.error('Failed to load document tags');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (tag = null) => {
    setEditingTag(tag);
    setFormData(tag ? {
      name: tag.name,
      tag_key: tag.tag_key,
      entity_type: tag.entity_type,
      color: tag.color
    } : {
      name: '',
      tag_key: '',
      entity_type: activeTab,
      color: '#3b82f6'
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.tag_key) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      if (editingTag) {
        await api.put(`/master/document-tags/${editingTag.id}`, formData);
        toast.success('Document tag updated successfully');
      } else {
        await api.post('/master/document-tags', formData);
        toast.success('Document tag created successfully');
      }
      fetchTags();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (tagId) => {
    if (!confirm('Are you sure you want to delete this document tag?')) return;

    try {
      await api.delete(`/master/document-tags/${tagId}`);
      toast.success('Document tag deleted');
      fetchTags();
    } catch (error) {
      toast.error('Failed to delete document tag');
    }
  };

  const leadTags = tags.filter(t => t.entity_type === 'lead');
  const companyTags = tags.filter(t => t.entity_type === 'company');

  // Auto-generate tag_key from name
  const handleNameChange = (name) => {
    setFormData({
      ...formData,
      name,
      tag_key: name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
    });
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Access denied. Admin only.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="document-tags-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Document Tags</h1>
          <p className="text-muted-foreground mt-1">
            Manage document types for leads and companies
          </p>
        </div>
        <Button onClick={() => openDialog()} data-testid="add-tag-btn">
          <Plus className="w-4 h-4 mr-2" />
          Add Tag
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="lead" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Lead Documents ({leadTags.length})
          </TabsTrigger>
          <TabsTrigger value="company" className="flex items-center gap-2">
            <Building2 className="w-4 h-4" />
            Company Documents ({companyTags.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="lead" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                Lead Document Tags
              </CardTitle>
              <CardDescription>
                These tags categorize documents uploaded to leads (e.g., Proposal, Contract, Invoice)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : leadTags.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tag Name</TableHead>
                      <TableHead>Key</TableHead>
                      <TableHead>Color</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {leadTags.map((tag) => (
                      <TableRow key={tag.id} data-testid={`tag-row-${tag.id}`}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Tag className="w-4 h-4" style={{ color: tag.color }} />
                            <span className="font-medium">{tag.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-sm bg-muted px-2 py-1 rounded">{tag.tag_key}</code>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-6 h-6 rounded" 
                              style={{ backgroundColor: tag.color }}
                            />
                            <span className="text-sm text-muted-foreground">{tag.color}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button 
                              size="icon" 
                              variant="ghost"
                              onClick={() => openDialog(tag)}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button 
                              size="icon" 
                              variant="ghost"
                              className="text-destructive hover:text-destructive"
                              onClick={() => handleDelete(tag.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
                  <h3 className="font-semibold mb-1">No lead document tags</h3>
                  <p className="text-muted-foreground text-sm mb-4">
                    Default tags (Proposal, Contract, Invoice) are available. Add custom tags here.
                  </p>
                  <Button onClick={() => { setFormData({ ...formData, entity_type: 'lead' }); openDialog(); }}>
                    <Plus className="w-4 h-4 mr-2" />
                    Add Lead Tag
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="company" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-primary" />
                Company Document Tags
              </CardTitle>
              <CardDescription>
                These tags categorize documents uploaded to companies (e.g., Corporate Profile, Brochure)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : companyTags.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tag Name</TableHead>
                      <TableHead>Key</TableHead>
                      <TableHead>Color</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {companyTags.map((tag) => (
                      <TableRow key={tag.id} data-testid={`tag-row-${tag.id}`}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Tag className="w-4 h-4" style={{ color: tag.color }} />
                            <span className="font-medium">{tag.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-sm bg-muted px-2 py-1 rounded">{tag.tag_key}</code>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-6 h-6 rounded" 
                              style={{ backgroundColor: tag.color }}
                            />
                            <span className="text-sm text-muted-foreground">{tag.color}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button 
                              size="icon" 
                              variant="ghost"
                              onClick={() => openDialog(tag)}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button 
                              size="icon" 
                              variant="ghost"
                              className="text-destructive hover:text-destructive"
                              onClick={() => handleDelete(tag.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-12">
                  <Building2 className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
                  <h3 className="font-semibold mb-1">No company document tags</h3>
                  <p className="text-muted-foreground text-sm mb-4">
                    Default tags (Corporate Profile, Brochure) are available. Add custom tags here.
                  </p>
                  <Button onClick={() => { setFormData({ ...formData, entity_type: 'company' }); openDialog(); }}>
                    <Plus className="w-4 h-4 mr-2" />
                    Add Company Tag
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingTag ? 'Edit Document Tag' : 'Add Document Tag'}
            </DialogTitle>
            <DialogDescription>
              {editingTag ? 'Update the document tag details' : 'Create a new document tag for categorizing uploads'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Tag Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="e.g., Proposal, Contract, Invoice"
                data-testid="tag-name-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Tag Key *</Label>
              <Input
                value={formData.tag_key}
                onChange={(e) => setFormData({ ...formData, tag_key: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                placeholder="e.g., proposal, contract"
                data-testid="tag-key-input"
              />
              <p className="text-xs text-muted-foreground">
                Auto-generated from name. Used internally for categorization.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Entity Type *</Label>
              <Select 
                value={formData.entity_type} 
                onValueChange={(v) => setFormData({ ...formData, entity_type: v })}
                disabled={!!editingTag}
              >
                <SelectTrigger data-testid="entity-type-select">
                  <SelectValue placeholder="Select entity type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lead">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Lead Documents
                    </div>
                  </SelectItem>
                  <SelectItem value="company">
                    <div className="flex items-center gap-2">
                      <Building2 className="w-4 h-4" />
                      Company Documents
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Color</Label>
              <Select 
                value={formData.color} 
                onValueChange={(v) => setFormData({ ...formData, color: v })}
              >
                <SelectTrigger data-testid="color-select">
                  <SelectValue>
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-4 h-4 rounded" 
                        style={{ backgroundColor: formData.color }}
                      />
                      {TAG_COLORS.find(c => c.value === formData.color)?.label || 'Custom'}
                    </div>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {TAG_COLORS.map((color) => (
                    <SelectItem key={color.value} value={color.value}>
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-4 h-4 rounded" 
                          style={{ backgroundColor: color.value }}
                        />
                        {color.label}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Preview */}
            {formData.name && (
              <div className="pt-2">
                <Label className="text-xs text-muted-foreground">Preview</Label>
                <div className="mt-1">
                  <Badge 
                    style={{ 
                      backgroundColor: `${formData.color}20`,
                      color: formData.color,
                      borderColor: formData.color
                    }}
                    variant="outline"
                  >
                    {formData.name}
                  </Badge>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="tag-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Tag'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DocumentTags;
