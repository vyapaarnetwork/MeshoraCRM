import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
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
import { Plus, Edit, Trash2, Percent, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const Commission = () => {
  const { isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({ name: '', vyapaar_percentage: '', description: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await api.get('/master/commission-templates');
      setTemplates(response.data);
    } catch (error) {
      toast.error('Failed to load commission templates');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (item = null) => {
    setEditingItem(item);
    setFormData(item ? {
      name: item.name,
      vyapaar_percentage: item.vyapaar_percentage.toString(),
      description: item.description || ''
    } : { name: '', vyapaar_percentage: '', description: '' });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.vyapaar_percentage) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        vyapaar_percentage: parseFloat(formData.vyapaar_percentage),
        description: formData.description || null
      };

      if (editingItem) {
        await api.put(`/master/commission-templates/${editingItem.id}`, payload);
        toast.success('Template updated successfully');
      } else {
        await api.post('/master/commission-templates', payload);
        toast.success('Template created successfully');
      }

      fetchTemplates();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this template?')) return;

    try {
      await api.delete(`/master/commission-templates/${id}`);
      toast.success('Template deleted successfully');
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to delete template');
    }
  };

  if (loading) return <CommissionSkeleton />;

  return (
    <div className="space-y-6" data-testid="commission-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Commission Templates</h1>
        <p className="text-muted-foreground mt-1">
          Manage commission percentage templates for partners
        </p>
      </div>

      {/* Info Card */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Percent className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold mb-1">How Commission Works</h3>
              <p className="text-sm text-muted-foreground">
                Commission templates define the percentage Vyapaar Network earns from each deal. 
                These templates can be applied to selling partners, and can be overridden at the individual lead level.
                Sales Associates or Selling Partners can be set as the lead's referrer, and earn a percentage of Vyapaar's share when they refer a lead.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Percent className="w-5 h-5 text-primary" />
              Commission Templates
            </CardTitle>
            <CardDescription>
              Pre-defined commission rates for different partner tiers
            </CardDescription>
          </div>
          <Button onClick={() => openDialog()} data-testid="add-template-btn">
            <Plus className="w-4 h-4 mr-2" />
            Add Template
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Template Name</TableHead>
                <TableHead>Vyapaar Commission</TableHead>
                <TableHead>Partner Share</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.map((template) => (
                <TableRow key={template.id} data-testid={`template-row-${template.id}`}>
                  <TableCell className="font-medium">{template.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-primary/10 text-primary">
                      {template.vyapaar_percentage}%
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-green-100 text-green-700">
                      {100 - template.vyapaar_percentage}%
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {template.description || '-'}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => openDialog(template)}
                        data-testid={`edit-template-${template.id}`}
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => handleDelete(template.id)}
                        className="text-destructive"
                        data-testid={`delete-template-${template.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {templates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    No commission templates found. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Example Calculation */}
      <Card>
        <CardHeader>
          <CardTitle>Commission Calculation Example</CardTitle>
          <CardDescription>How commissions are distributed on a ₹1,00,000 deal</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Template</TableHead>
                  <TableHead className="text-right">Deal Value</TableHead>
                  <TableHead className="text-right">Vyapaar Gets</TableHead>
                  <TableHead className="text-right">Partner Gets</TableHead>
                  <TableHead className="text-right">SA Gets (10% of Vyapaar)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.map((template) => {
                  const dealValue = 100000;
                  const vyapaarShare = dealValue * (template.vyapaar_percentage / 100);
                  const partnerShare = dealValue - vyapaarShare;
                  const saShare = vyapaarShare * 0.1;
                  
                  return (
                    <TableRow key={template.id}>
                      <TableCell className="font-medium">{template.name}</TableCell>
                      <TableCell className="text-right">₹1,00,000</TableCell>
                      <TableCell className="text-right text-primary font-medium">
                        ₹{vyapaarShare.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right text-green-600 font-medium">
                        ₹{partnerShare.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right text-purple-600 font-medium">
                        ₹{saShare.toLocaleString('en-IN')}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingItem ? 'Edit' : 'Add'} Commission Template
            </DialogTitle>
            <DialogDescription>
              Define a commission percentage for partners
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Template Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Standard, Premium Partner"
                data-testid="template-name-input"
              />
            </div>
            <div className="space-y-2">
              <Label>Vyapaar Commission Percentage *</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.vyapaar_percentage}
                  onChange={(e) => setFormData({ ...formData, vyapaar_percentage: e.target.value })}
                  placeholder="15"
                  data-testid="template-percentage-input"
                />
                <span className="text-muted-foreground">%</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Partner will receive {100 - (parseFloat(formData.vyapaar_percentage) || 0)}% of deal value
              </p>
            </div>
            <div className="space-y-2">
              <Label>Description (Optional)</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of this template"
                data-testid="template-description-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="template-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Template'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const CommissionSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-64 mb-2" />
      <Skeleton className="h-4 w-48" />
    </div>
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="h-20 w-full" />
      </CardContent>
    </Card>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48 mb-2" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default Commission;
