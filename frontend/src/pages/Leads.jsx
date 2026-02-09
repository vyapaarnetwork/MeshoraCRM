import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { 
  Plus, 
  Search, 
  Filter, 
  MoreHorizontal, 
  Eye, 
  Edit, 
  Trash2,
  FileText,
  Building2,
  Calendar
} from 'lucide-react';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';

const Leads = () => {
  const { user, isAdmin, isCustomer, isSalesAssociate } = useAuth();
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [statuses, setStatuses] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [leadsRes, statusesRes] = await Promise.all([
        api.get('/leads'),
        api.get('/master/lead-status')
      ]);
      setLeads(leadsRes.data);
      setStatuses(statusesRes.data);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error('Failed to load leads');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (leadId) => {
    if (!window.confirm('Are you sure you want to delete this lead?')) return;
    
    try {
      await api.delete(`/leads/${leadId}`);
      setLeads(leads.filter(l => l.id !== leadId));
      toast.success('Lead deleted successfully');
    } catch (error) {
      toast.error('Failed to delete lead');
    }
  };

  const filteredLeads = leads.filter(lead => {
    const matchesSearch = 
      lead.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      lead.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      lead.customer_email.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || lead.status_id === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return <LeadsSkeleton />;
  }

  return (
    <div className="space-y-6" data-testid="leads-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Leads</h1>
          <p className="text-muted-foreground mt-1">
            Manage and track your leads pipeline
          </p>
        </div>
        {!isSalesAssociate && (
          <Button 
            onClick={() => navigate('/leads/new')} 
            className="bg-primary"
            data-testid="create-lead-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Lead
          </Button>
        )}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search leads..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="lead-search-input"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[180px]" data-testid="status-filter">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {statuses.map((status) => (
                  <SelectItem key={status.id} value={status.id}>
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-2 h-2 rounded-full" 
                        style={{ backgroundColor: status.color }}
                      />
                      {status.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Leads Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            All Leads ({filteredLeads.length})
          </CardTitle>
          <CardDescription>
            Click on a lead to view details and manage follow-ups
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredLeads.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Lead</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Deal Value</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[60px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLeads.map((lead) => (
                    <TableRow 
                      key={lead.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/leads/${lead.id}`)}
                      data-testid={`lead-row-${lead.id}`}
                    >
                      <TableCell>
                        <div className="font-medium">{lead.title}</div>
                        {lead.selling_partner_name && (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            <Building2 className="w-3 h-3" />
                            {lead.selling_partner_name}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <div>{lead.customer_name}</div>
                        <div className="text-xs text-muted-foreground">{lead.customer_email}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{lead.primary_category_name || 'Uncategorized'}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge 
                          style={{ 
                            backgroundColor: `${lead.status_color}20`,
                            color: lead.status_color,
                            borderColor: lead.status_color
                          }}
                        >
                          {lead.status_name || 'New'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatCurrency(lead.deal_value)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-muted-foreground text-sm">
                          <Calendar className="w-3 h-3" />
                          {formatDate(lead.created_at)}
                        </div>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" data-testid={`lead-menu-${lead.id}`}>
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => navigate(`/leads/${lead.id}`)}>
                              <Eye className="w-4 h-4 mr-2" />
                              View Details
                            </DropdownMenuItem>
                            {!isSalesAssociate && (
                              <DropdownMenuItem onClick={() => navigate(`/leads/${lead.id}/edit`)}>
                                <Edit className="w-4 h-4 mr-2" />
                                Edit Lead
                              </DropdownMenuItem>
                            )}
                            {isAdmin && (
                              <DropdownMenuItem 
                                onClick={() => handleDelete(lead.id)}
                                className="text-destructive"
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                Delete
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="font-semibold mb-1">No leads found</h3>
              <p className="text-muted-foreground text-sm mb-4">
                {searchTerm || statusFilter !== 'all' 
                  ? 'Try adjusting your filters'
                  : 'Get started by creating your first lead'
                }
              </p>
              {!isSalesAssociate && !searchTerm && statusFilter === 'all' && (
                <Button onClick={() => navigate('/leads/new')} data-testid="empty-create-lead-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Lead
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Loading Skeleton
const LeadsSkeleton = () => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <div>
        <Skeleton className="h-8 w-32 mb-2" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Skeleton className="h-10 w-32" />
    </div>
    <Card>
      <CardContent className="pt-6">
        <div className="flex gap-4">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-[180px]" />
        </div>
      </CardContent>
    </Card>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default Leads;
