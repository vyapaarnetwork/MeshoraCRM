import { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { Plus, Building2, Search } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { DocumentUploadDialog, COMPANY_DOCUMENT_TAGS } from '../components/DocumentUpload';
import { CompanyTable } from './companies/CompanyTable';
import { CompanyFormDialog } from './companies/CompanyFormDialog';
import { CompanyDocumentsDialog } from './companies/CompanyDocumentsDialog';

const EMPTY_FORM = {
  name: '',
  type: '',
  vyapaar_commission_percentage: '15',
  address: '',
  contact_email: '',
  contact_phone: '',
  subcategory_ids: [],
  default_user_name: '',
  default_user_email: '',
  default_user_phone: '',
  default_user_password: '',
};

const Companies = () => {
  const [companies, setCompanies] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  // Form / dialogs
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  // Document dialogs
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [documentsDialogOpen, setDocumentsDialogOpen] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState(null);
  const [selectedCompanyName, setSelectedCompanyName] = useState('');
  const [documents, setDocuments] = useState([]);
  const [documentTags, setDocumentTags] = useState(COMPANY_DOCUMENT_TAGS);

  useEffect(() => {
    fetchData();
    fetchDocumentTags();
  }, []);

  const fetchData = async () => {
    try {
      const [companiesRes, categoriesRes] = await Promise.all([
        api.get('/companies'),
        api.get('/master/secondary-categories'),
      ]);
      setCompanies(companiesRes.data);
      setSecondaryCategories(categoriesRes.data);
    } catch (e) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocumentTags = async () => {
    try {
      const response = await api.get('/master/document-tags?entity_type=company');
      if (response.data && response.data.length > 0) {
        setDocumentTags(response.data.map(t => ({ value: t.tag_key, label: t.name })));
      }
    } catch (e) { /* fall back to defaults */ }
  };

  const fetchCompanyDocuments = async (companyId) => {
    try {
      const response = await api.get(`/documents/entity/company/${companyId}`);
      setDocuments(response.data);
    } catch (e) {
      console.error('Failed to fetch documents:', e);
    }
  };

  const openDocumentsDialog = (company) => {
    setSelectedCompanyId(company.id);
    setSelectedCompanyName(company.name);
    fetchCompanyDocuments(company.id);
    setDocumentsDialogOpen(true);
  };

  const handleDocumentUploaded = () => {
    if (selectedCompanyId) fetchCompanyDocuments(selectedCompanyId);
  };

  const handleDeleteDocument = async (docId) => {
    try {
      await api.delete(`/documents/${docId}`);
      toast.success('Document deleted');
      if (selectedCompanyId) fetchCompanyDocuments(selectedCompanyId);
    } catch (e) {
      toast.error('Failed to delete document');
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
      subcategory_ids: company.subcategory_ids || [],
      default_user_name: '',
      default_user_email: '',
      default_user_phone: '',
      default_user_password: '',
    } : EMPTY_FORM);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.type) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (!editingCompany && (formData.type === 'customer' || formData.type === 'selling_partner')) {
      if (!formData.default_user_name || !formData.default_user_email) {
        toast.error(`Please provide default user details for ${formData.type === 'customer' ? 'customer' : 'selling partner'} company`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const includeUser = formData.type === 'customer' || formData.type === 'selling_partner';
      const defaultPwd = formData.type === 'selling_partner' ? 'partner123' : 'customer123';
      const payload = {
        ...formData,
        vyapaar_commission_percentage: parseFloat(formData.vyapaar_commission_percentage),
        subcategory_ids: formData.type === 'selling_partner' ? formData.subcategory_ids : [],
        default_user_name: includeUser ? formData.default_user_name : null,
        default_user_email: includeUser ? formData.default_user_email : null,
        default_user_phone: includeUser ? formData.default_user_phone : null,
        default_user_password: includeUser ? (formData.default_user_password || defaultPwd) : null,
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

  const toggleSubcategory = (id) => {
    setFormData(prev => ({
      ...prev,
      subcategory_ids: prev.subcategory_ids.includes(id)
        ? prev.subcategory_ids.filter(x => x !== id)
        : [...prev.subcategory_ids, id],
    }));
  };

  const filteredCompanies = companies.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || c.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const stats = {
    total: companies.length,
    selling_partners: companies.filter(c => c.type === 'selling_partner').length,
    customers: companies.filter(c => c.type === 'customer').length,
  };

  const categoriesByPrimary = secondaryCategories.reduce((acc, cat) => {
    const primaryName = cat.primary_category_name || 'Other';
    if (!acc[primaryName]) acc[primaryName] = [];
    acc[primaryName].push(cat);
    return acc;
  }, {});

  if (loading) return <CompaniesSkeleton />;

  return (
    <div className="space-y-6" data-testid="companies-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Companies</h1>
          <p className="text-muted-foreground mt-1">Manage partner and customer companies</p>
        </div>
        <Button onClick={() => openDialog()} data-testid="add-company-btn">
          <Plus className="w-4 h-4 mr-2" />
          Add Company
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total Companies" value={stats.total} color="text-primary" />
        <StatCard label="Selling Partners" value={stats.selling_partners} color="text-blue-600" iconColor="text-blue-200" />
        <StatCard label="Customers" value={stats.customers} color="text-orange-600" iconColor="text-orange-200" />
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

      <CompanyTable
        companies={filteredCompanies}
        searchTerm={searchTerm}
        typeFilter={typeFilter}
        onEdit={openDialog}
        onOpenDocuments={openDocumentsDialog}
        onAdd={() => openDialog()}
      />

      <CompanyFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editingCompany={editingCompany}
        formData={formData}
        setFormData={setFormData}
        categoriesByPrimary={categoriesByPrimary}
        secondaryCategories={secondaryCategories}
        submitting={submitting}
        onSubmit={handleSubmit}
        onToggleSubcategory={toggleSubcategory}
      />

      <CompanyDocumentsDialog
        open={documentsDialogOpen}
        onOpenChange={setDocumentsDialogOpen}
        companyName={selectedCompanyName}
        documents={documents}
        onUploadClick={() => {
          setDocumentsDialogOpen(false);
          setUploadDialogOpen(true);
        }}
        onDelete={handleDeleteDocument}
      />

      <DocumentUploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        entityType="company"
        entityId={selectedCompanyId}
        tags={documentTags}
        onUploadComplete={handleDocumentUploaded}
      />
    </div>
  );
};

const StatCard = ({ label, value, color = 'text-foreground', iconColor = 'text-primary/20' }) => (
  <Card>
    <CardContent className="pt-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
        </div>
        <Building2 className={`w-8 h-8 ${iconColor}`} />
      </div>
    </CardContent>
  </Card>
);

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
