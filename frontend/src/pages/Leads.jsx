import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
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
import SortableTable from '../components/SortableTable';
import { 
  Plus, 
  Filter, 
  MoreHorizontal, 
  Eye, 
  Edit, 
  Trash2,
  FileText,
  Building2,
  Calendar,
  Upload
} from 'lucide-react';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';
import { HealthScoreBadge } from '../components/HealthScore';

const HEALTH_BAND_ORDER = { at_risk: 0, cold: 1, warm: 2, hot: 3 };

const Leads = () => {
  const { user, isAdmin, isCustomer, isSalesAssociate } = useAuth();
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [healthFilter, setHealthFilter] = useState('all');
  const [assignedToMe, setAssignedToMe] = useState(false);  // Phase 34.7
  const [statuses, setStatuses] = useState([]);
  const [healthByLead, setHealthByLead] = useState({});

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignedToMe]);

  const fetchData = async () => {
    try {
      const [leadsRes, statusesRes, healthRes] = await Promise.all([
        api.get('/leads', { params: assignedToMe ? { assigned_to_me: true } : {} }),
        api.get('/master/lead-status'),
        api.get('/leads/health-summary').catch(() => ({ data: { results: [] } })),
      ]);
      setLeads(leadsRes.data);
      setStatuses(statusesRes.data);
      const map = {};
      for (const r of (healthRes.data?.results || [])) {
        map[r.id] = { health: r.health, next_action: r.next_action };
      }
      setHealthByLead(map);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error('Failed to load leads');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (leadId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this lead?')) return;
    
    try {
      await api.delete(`/leads/${leadId}`);
      setLeads(leads.filter(l => l.id !== leadId));
      toast.success('Lead deleted successfully');
    } catch (error) {
      toast.error('Failed to delete lead');
    }
  };

  // Filter by status + health band
  const filteredLeads = leads
    .filter(lead => statusFilter === 'all' || lead.status_id === statusFilter)
    .filter(lead => healthFilter === 'all' || healthByLead[lead.id]?.health?.band === healthFilter);

  // Inject health onto each row + helper for sortable health column
  const leadsWithHealth = filteredLeads.map((l) => ({
    ...l,
    _health: healthByLead[l.id]?.health || null,
    _health_score: healthByLead[l.id]?.health?.score ?? -1,
    _health_band_rank: HEALTH_BAND_ORDER[healthByLead[l.id]?.health?.band] ?? 99,
  }));

  // Table columns configuration
  const columns = [
    {
      key: 'title',
      label: 'Lead',
      render: (value, row) => (
        <div>
          <div className="font-medium">{value}</div>
          {row.selling_partner_name && (
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Building2 className="w-3 h-3" />
              {row.selling_partner_name}
            </div>
          )}
        </div>
      )
    },
    {
      key: 'customer_name',
      label: 'Customer',
      render: (value, row) => (
        <div>
          <div>{value}</div>
          <div className="text-xs text-muted-foreground">{row.customer_email}</div>
        </div>
      )
    },
    {
      key: 'customer_company',
      label: 'Company',
      render: (value) => (
        <div className="text-sm">
          {value ? (
            <span className="inline-flex items-center gap-1">
              <Building2 className="w-3 h-3 text-muted-foreground" />
              {value}
            </span>
          ) : (
            <span className="text-muted-foreground text-xs">—</span>
          )}
        </div>
      )
    },
    {
      key: 'primary_category_name',
      label: 'Category',
      render: (value) => (
        <Badge variant="outline">{value || 'Uncategorized'}</Badge>
      )
    },
    {
      key: 'status_name',
      label: 'Status',
      render: (value, row) => (
        <Badge 
          style={{ 
            backgroundColor: `${row.status_color}20`,
            color: row.status_color,
            borderColor: row.status_color
          }}
        >
          {value || 'New'}
        </Badge>
      )
    },
    {
      key: 'deal_value',
      label: 'Deal Value',
      render: (value) => (
        <span className="font-medium">{formatCurrency(value)}</span>
      )
    },
    {
      key: '_health_score',
      label: 'Health',
      render: (_, row) => row._health ? <HealthScoreBadge health={row._health} size="sm" /> : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      key: 'created_at',
      label: 'Created',
      render: (value) => (
        <div className="flex items-center gap-1 text-muted-foreground text-sm">
          <Calendar className="w-3 h-3" />
          {formatDate(value)}
        </div>
      )
    },
    {
      key: 'actions',
      label: '',
      sortable: false,
      width: '60px',
      render: (_, row) => (
        <div onClick={(e) => e.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" data-testid={`lead-menu-${row.id}`}>
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/leads/${row.id}`)}>
                <Eye className="w-4 h-4 mr-2" />
                View Details
              </DropdownMenuItem>
              {!isSalesAssociate && (
                <DropdownMenuItem onClick={() => navigate(`/leads/${row.id}/edit`)}>
                  <Edit className="w-4 h-4 mr-2" />
                  Edit Lead
                </DropdownMenuItem>
              )}
              {isAdmin && (
                <DropdownMenuItem 
                  onClick={(e) => handleDelete(row.id, e)}
                  className="text-destructive"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )
    }
  ];

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
          <div className="flex gap-2">
            <Button 
              variant="outline"
              onClick={() => navigate('/leads/import')}
              data-testid="import-leads-btn"
            >
              <Upload className="w-4 h-4 mr-2" />
              Import
            </Button>
            <Button 
              onClick={() => navigate('/leads/new')} 
              className="bg-primary"
              data-testid="create-lead-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Lead
            </Button>
          </div>
        )}
      </div>

      {/* Status + Health Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[200px]" data-testid="status-filter">
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
            <Select value={healthFilter} onValueChange={setHealthFilter}>
              <SelectTrigger className="w-[180px]" data-testid="health-filter">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Filter by health" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Health</SelectItem>
                <SelectItem value="at_risk">🚨 At Risk</SelectItem>
                <SelectItem value="cold">❄️ Cold</SelectItem>
                <SelectItem value="warm">☀️ Warm</SelectItem>
                <SelectItem value="hot">🔥 Hot</SelectItem>
              </SelectContent>
            </Select>
            <label
              className="flex items-center gap-2 text-sm cursor-pointer select-none px-3 py-1.5 rounded-md border bg-card hover:bg-accent"
              data-testid="assigned-to-me-toggle"
            >
              <input
                type="checkbox"
                checked={assignedToMe}
                onChange={(e) => setAssignedToMe(e.target.checked)}
                className="h-4 w-4 accent-violet-600"
                data-testid="assigned-to-me-checkbox"
              />
              <span className="font-medium">Assigned to Me</span>
            </label>
            <span className="text-sm text-muted-foreground">
              {filteredLeads.length} leads
            </span>
            {(statusFilter !== 'all' || healthFilter !== 'all' || assignedToMe) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setStatusFilter('all'); setHealthFilter('all'); setAssignedToMe(false); }}
                data-testid="clear-filters-btn"
              >
                Clear filters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Leads Table with Sorting */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            All Leads
          </CardTitle>
          <CardDescription>
            Click column headers to sort. Click on a lead to view details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SortableTable
            columns={columns}
            data={leadsWithHealth}
            rowKey="id"
            pageSize={15}
            onRowClick={(row) => navigate(`/leads/${row.id}`)}
            emptyMessage={
              statusFilter !== 'all' || healthFilter !== 'all'
                ? 'No leads match the current filters. Try clearing them.'
                : 'No leads found. Create your first lead to get started.'
            }
          />
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
        <Skeleton className="h-10 w-[200px]" />
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
