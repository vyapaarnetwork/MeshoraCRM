import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
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
import { Plus, Edit, Trash2, Tag, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const Categories = () => {
  const { isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [primaryCategories, setPrimaryCategories] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [leadStatuses, setLeadStatuses] = useState([]);
  
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [primaryRes, secondaryRes, statusesRes] = await Promise.all([
        api.get('/master/primary-categories'),
        api.get('/master/secondary-categories'),
        api.get('/master/lead-status')
      ]);
      setPrimaryCategories(primaryRes.data);
      setSecondaryCategories(secondaryRes.data);
      setLeadStatuses(statusesRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (type, item = null) => {
    setDialogType(type);
    setEditingItem(item);
    
    if (type === 'primary') {
      setFormData(item ? { name: item.name, description: item.description || '' } : { name: '', description: '' });
    } else if (type === 'secondary') {
      setFormData(item ? { 
        name: item.name, 
        primary_category_id: item.primary_category_id,
        description: item.description || '' 
      } : { name: '', primary_category_id: '', description: '' });
    } else if (type === 'status') {
      setFormData(item ? { 
        name: item.name, 
        color: item.color,
        order: item.order 
      } : { name: '', color: '#4169E1', order: leadStatuses.length + 1 });
    }
    
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      let endpoint, payload;
      
      if (dialogType === 'primary') {
        endpoint = editingItem 
          ? `/master/primary-categories/${editingItem.id}`
          : '/master/primary-categories';
        payload = formData;
      } else if (dialogType === 'secondary') {
        endpoint = editingItem 
          ? `/master/secondary-categories/${editingItem.id}`
          : '/master/secondary-categories';
        payload = formData;
      } else if (dialogType === 'status') {
        endpoint = editingItem 
          ? `/master/lead-status/${editingItem.id}`
          : '/master/lead-status';
        payload = formData;
      }
      
      if (editingItem) {
        await api.put(endpoint, payload);
        toast.success('Updated successfully');
      } else {
        await api.post(endpoint, payload);
        toast.success('Created successfully');
      }
      
      fetchData();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (type, id) => {
    if (!window.confirm('Are you sure you want to delete this item?')) return;
    
    try {
      let endpoint;
      if (type === 'primary') endpoint = `/master/primary-categories/${id}`;
      else if (type === 'secondary') endpoint = `/master/secondary-categories/${id}`;
      else if (type === 'status') endpoint = `/master/lead-status/${id}`;
      
      await api.delete(endpoint);
      toast.success('Deleted successfully');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  if (loading) return <CategoriesSkeleton />;

  return (
    <div className="space-y-6" data-testid="categories-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Master Data</h1>
        <p className="text-muted-foreground mt-1">
          Manage categories, statuses, and other system configuration
        </p>
      </div>

      <Tabs defaultValue="primary" className="space-y-4">
        <TabsList>
          <TabsTrigger value="primary" data-testid="primary-tab">Primary Categories</TabsTrigger>
          <TabsTrigger value="secondary" data-testid="secondary-tab">Secondary Categories</TabsTrigger>
          <TabsTrigger value="statuses" data-testid="statuses-tab">Lead Statuses</TabsTrigger>
        </TabsList>

        {/* Primary Categories */}
        <TabsContent value="primary">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Primary Categories</CardTitle>
                <CardDescription>Main business categories (HR, IT, Marketing, etc.)</CardDescription>
              </div>
              <Button onClick={() => openDialog('primary')} data-testid="add-primary-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Category
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Sub-categories</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {primaryCategories.map((cat) => (
                    <TableRow key={cat.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Tag className="w-4 h-4 text-primary" />
                          {cat.name}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {cat.description || '-'}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {secondaryCategories.filter(s => s.primary_category_id === cat.id).length}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => openDialog('primary', cat)}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => handleDelete('primary', cat.id)}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Secondary Categories */}
        <TabsContent value="secondary">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Secondary Categories</CardTitle>
                <CardDescription>Sub-categories mapped to primary categories</CardDescription>
              </div>
              <Button onClick={() => openDialog('secondary')} data-testid="add-secondary-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Sub-category
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Parent Category</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {secondaryCategories.map((cat) => (
                    <TableRow key={cat.id}>
                      <TableCell className="font-medium">{cat.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{cat.primary_category_name}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {cat.description || '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => openDialog('secondary', cat)}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => handleDelete('secondary', cat.id)}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Lead Statuses */}
        <TabsContent value="statuses">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Lead Statuses</CardTitle>
                <CardDescription>Pipeline stages for leads</CardDescription>
              </div>
              <Button onClick={() => openDialog('status')} data-testid="add-status-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Status
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Color</TableHead>
                    <TableHead>Order</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leadStatuses.map((status) => (
                    <TableRow key={status.id}>
                      <TableCell>
                        <Badge 
                          style={{ 
                            backgroundColor: `${status.color}20`,
                            color: status.color,
                            borderColor: status.color
                          }}
                        >
                          {status.name}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-6 h-6 rounded border"
                            style={{ backgroundColor: status.color }}
                          />
                          <span className="text-sm font-mono">{status.color}</span>
                        </div>
                      </TableCell>
                      <TableCell>{status.order}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => openDialog('status', status)}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button 
                            size="icon" 
                            variant="ghost"
                            onClick={() => handleDelete('status', status.id)}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingItem ? 'Edit' : 'Add'} {
                dialogType === 'primary' ? 'Primary Category' :
                dialogType === 'secondary' ? 'Secondary Category' :
                'Lead Status'
              }
            </DialogTitle>
            <DialogDescription>
              Fill in the details below
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Enter name"
                data-testid="dialog-name-input"
              />
            </div>
            
            {dialogType === 'secondary' && (
              <div className="space-y-2">
                <Label>Parent Category</Label>
                <Select 
                  value={formData.primary_category_id || ''} 
                  onValueChange={(v) => setFormData({ ...formData, primary_category_id: v })}
                >
                  <SelectTrigger data-testid="dialog-parent-select">
                    <SelectValue placeholder="Select parent category" />
                  </SelectTrigger>
                  <SelectContent>
                    {primaryCategories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            
            {dialogType === 'status' && (
              <>
                <div className="space-y-2">
                  <Label>Color</Label>
                  <div className="flex gap-2">
                    <Input
                      type="color"
                      value={formData.color || '#4169E1'}
                      onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                      className="w-16 h-10 p-1"
                    />
                    <Input
                      value={formData.color || '#4169E1'}
                      onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                      className="flex-1 font-mono"
                      data-testid="dialog-color-input"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Order</Label>
                  <Input
                    type="number"
                    value={formData.order || 0}
                    onChange={(e) => setFormData({ ...formData, order: parseInt(e.target.value) })}
                    min="1"
                    data-testid="dialog-order-input"
                  />
                </div>
              </>
            )}
            
            {(dialogType === 'primary' || dialogType === 'secondary') && (
              <div className="space-y-2">
                <Label>Description (Optional)</Label>
                <Input
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Enter description"
                  data-testid="dialog-description-input"
                />
              </div>
            )}
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="dialog-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const CategoriesSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-48 mb-2" />
      <Skeleton className="h-4 w-64" />
    </div>
    <Skeleton className="h-10 w-[400px]" />
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32 mb-2" />
        <Skeleton className="h-4 w-48" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default Categories;
