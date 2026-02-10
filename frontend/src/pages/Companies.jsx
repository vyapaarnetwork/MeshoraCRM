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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Plus, Edit, Building2, Percent, Search, Loader2, Tag, X } from 'lucide-react';
import api, { formatDate } from '../utils/api';
import { toast } from 'sonner';

const Companies = () => {
  const { isAdmin } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    type: '',
    vyapaar_commission_percentage: '15',
    address: '',
    contact_email: '',
    contact_phone: '',
    subcategory_ids: []
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [companiesRes, categoriesRes] = await Promise.all([
        api.get('/companies'),
        api.get('/master/secondary-categories')
      ]);
      setCompanies(companiesRes.data);
      setSecondaryCategories(categoriesRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = (company = null) => {
    setEditingCompany(company);
    setFormData(company ? {
      name: company.name,
      type: company.type,
      vyapaar_commission_percentage: company.vyapaar_commission_percentage.toString(),
      address: company.address || '',
      contact_email: company.contact_email || '',
      contact_phone: company.contact_phone || '',
      subcategory_ids: company.subcategory_ids || []
    } : {
      name: '',
      type: '',
      vyapaar_commission_percentage: '15',
      address: '',
      contact_email: '',
      contact_phone: '',
      subcategory_ids: []
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.type) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        ...formData,
        vyapaar_commission_percentage: parseFloat(formData.vyapaar_commission_percentage),
        subcategory_ids: formData.type === 'selling_partner' ? formData.subcategory_ids : []
      };

      if (editingCompany) {
        await api.put(`/companies/${editingCompany.id}`, payload);
        toast.success('Company updated successfully');
      } else {
        await api.post('/companies', payload);
        toast.success('Company created successfully');
      }

      fetchData();
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Operation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSubcategory = (categoryId) => {
    setFormData(prev => ({
      ...prev,
      subcategory_ids: prev.subcategory_ids.includes(categoryId)
        ? prev.subcategory_ids.filter(id => id !== categoryId)
        : [...prev.subcategory_ids, categoryId]
    }));
  };

  const filteredCompanies = companies.filter(company => {
    const matchesSearch = company.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || company.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const stats = {
    total: companies.length,
    selling_partners: companies.filter(c => c.type === 'selling_partner').length,
    customers: companies.filter(c => c.type === 'customer').length
  };

  // Group secondary categories by primary category
  const categoriesByPrimary = secondaryCategories.reduce((acc, cat) => {
    const primaryName = cat.primary_category_name || 'Other';
    if (!acc[primaryName]) {
      acc[primaryName] = [];
    }
    acc[primaryName].push(cat);
    return acc;
  }, {});

  if (loading) return <CompaniesSkeleton />;

  return (
    <div className="space-y-6" data-testid="companies-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Companies</h1>
          <p className="text-muted-foreground mt-1">
            Manage partner and customer companies
          </p>
        </div>
        <Button onClick={() => openDialog()} data-testid="add-company-btn">
          <Plus className="w-4 h-4 mr-2" />
          Add Company
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Companies</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
              <Building2 className="w-8 h-8 text-primary/20" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Selling Partners</p>
                <p className="text-2xl font-bold text-blue-600">{stats.selling_partners}</p>
              </div>
              <Building2 className="w-8 h-8 text-blue-200" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Customers</p>
                <p className="text-2xl font-bold text-orange-600">{stats.customers}</p>
              </div>
              <Building2 className="w-8 h-8 text-orange-200" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search companies..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="company-search-input"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full sm:w-[180px]" data-testid="type-filter">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="selling_partner">Selling Partners</SelectItem>
                <SelectItem value="customer">Customers</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Companies Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-primary" />
            All Companies ({filteredCompanies.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredCompanies.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Company</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Commission Rate</TableHead>
                    <TableHead>Sub-categories</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[80px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCompanies.map((company) => (
                    <TableRow key={company.id} data-testid={`company-row-${company.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                            <Building2 className="w-4 h-4 text-primary" />
                          </div>
                          <div>
                            <p className="font-medium">{company.name}</p>
                            {company.address && (
                              <p className="text-xs text-muted-foreground">{company.address}</p>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={company.type === 'selling_partner' ? 'default' : 'secondary'}>
                          {company.type === 'selling_partner' ? 'Selling Partner' : 'Customer'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Percent className="w-3 h-3 text-muted-foreground" />
                          <span className="font-medium">{company.vyapaar_commission_percentage}%</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {company.subcategories && company.subcategories.length > 0 ? (
                          <div className="flex flex-wrap gap-1 max-w-[200px]">
                            {company.subcategories.slice(0, 3).map((sub) => (
                              <Badge key={sub.id} variant="outline" className="text-xs">
                                {sub.name}
                              </Badge>
                            ))}
                            {company.subcategories.length > 3 && (
                              <Badge variant="outline" className="text-xs">
                                +{company.subcategories.length - 3} more
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {company.contact_email && (
                          <p className="text-sm">{company.contact_email}</p>
                        )}
                        {company.contact_phone && (
                          <p className="text-xs text-muted-foreground">{company.contact_phone}</p>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(company.created_at)}
                      </TableCell>
                      <TableCell>
                        <Button 
                          size="icon" 
                          variant="ghost"
                          onClick={() => openDialog(company)}
                          data-testid={`edit-company-${company.id}`}
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <Building2 className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="font-semibold mb-1">No companies found</h3>
              <p className="text-muted-foreground text-sm mb-4">
                {searchTerm || typeFilter !== 'all' 
                  ? 'Try adjusting your filters'
                  : 'Get started by adding your first company'
                }
              </p>
              {!searchTerm && typeFilter === 'all' && (
                <Button onClick={() => openDialog()}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Company
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingCompany ? 'Edit Company' : 'Add New Company'}
            </DialogTitle>
            <DialogDescription>
              {editingCompany ? 'Update company details' : 'Create a new company account'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Company Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Enter company name"
                data-testid="company-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Company Type *</Label>
              <Select 
                value={formData.type} 
                onValueChange={(v) => setFormData({ ...formData, type: v, subcategory_ids: [] })}
              >
                <SelectTrigger data-testid="company-type-select">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="selling_partner">Selling Partner</SelectItem>
                  <SelectItem value="customer">Customer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Vyapaar Commission (%)</Label>
              <Input
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={formData.vyapaar_commission_percentage}
                onChange={(e) => setFormData({ ...formData, vyapaar_commission_percentage: e.target.value })}
                placeholder="15"
                data-testid="company-commission-input"
              />
              <p className="text-xs text-muted-foreground">
                Default commission rate for this company's deals
              </p>
            </div>

            {/* Sub-categories section for selling partners */}
            {formData.type === 'selling_partner' && (
              <div className="space-y-3">
                <Label className="flex items-center gap-2">
                  <Tag className="w-4 h-4" />
                  Service Sub-categories
                </Label>
                <p className="text-xs text-muted-foreground">
                  Select the service categories this partner specializes in
                </p>
                
                {/* Selected subcategories */}
                {formData.subcategory_ids.length > 0 && (
                  <div className="flex flex-wrap gap-2 p-2 bg-muted rounded-md">
                    {formData.subcategory_ids.map(id => {
                      const cat = secondaryCategories.find(c => c.id === id);
                      return cat ? (
                        <Badge key={id} variant="secondary" className="flex items-center gap-1">
                          {cat.name}
                          <X 
                            className="w-3 h-3 cursor-pointer" 
                            onClick={() => toggleSubcategory(id)}
                          />
                        </Badge>
                      ) : null;
                    })}
                  </div>
                )}

                {/* Category selection */}
                <div className="border rounded-md max-h-[200px] overflow-y-auto">
                  {Object.entries(categoriesByPrimary).map(([primaryName, categories]) => (
                    <div key={primaryName} className="border-b last:border-b-0">
                      <div className="px-3 py-2 bg-muted/50 font-medium text-sm">
                        {primaryName}
                      </div>
                      <div className="p-2 space-y-1">
                        {categories.map(cat => (
                          <div key={cat.id} className="flex items-center space-x-2">
                            <Checkbox
                              id={cat.id}
                              checked={formData.subcategory_ids.includes(cat.id)}
                              onCheckedChange={() => toggleSubcategory(cat.id)}
                            />
                            <label
                              htmlFor={cat.id}
                              className="text-sm cursor-pointer"
                            >
                              {cat.name}
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Contact Email</Label>
                <Input
                  type="email"
                  value={formData.contact_email}
                  onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                  placeholder="contact@company.com"
                />
              </div>
              <div className="space-y-2">
                <Label>Contact Phone</Label>
                <Input
                  value={formData.contact_phone}
                  onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                  placeholder="+91 98765 43210"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Address</Label>
              <Input
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Company address"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} data-testid="company-submit-btn">
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Company'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const CompaniesSkeleton = () => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <div>
        <Skeleton className="h-8 w-32 mb-2" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Skeleton className="h-10 w-32" />
    </div>
    <div className="grid gap-4 sm:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="pt-6">
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default Companies;
