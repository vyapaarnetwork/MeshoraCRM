import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import SortableTable from '../components/SortableTable';
import MultiSelect from '../components/MultiSelect';
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
  Upload,
  Save as SaveIcon,
  Star,
  StarOff,
  Bookmark,
} from 'lucide-react';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';
import { HealthScoreBadge } from '../components/HealthScore';

const HEALTH_BAND_ORDER = { at_risk: 0, cold: 1, warm: 2, hot: 3 };
const HEALTH_OPTIONS = [
  { value: 'hot',     label: '🔥 Hot',     color: '#dc2626' },
  { value: 'warm',    label: '☀️ Warm',    color: '#f59e0b' },
  { value: 'cold',    label: '❄️ Cold',    color: '#0ea5e9' },
  { value: 'at_risk', label: '🚨 At Risk', color: '#ef4444' },
];

const Leads = () => {
  const { user, isAdmin, isCustomer, isSalesAssociate } = useAuth();
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  // Phase 34.7.3 — multi-select filters
  const [statusFilters, setStatusFilters] = useState([]);
  const [healthFilters, setHealthFilters] = useState([]);
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [statuses, setStatuses] = useState([]);
  const [healthByLead, setHealthByLead] = useState({});

  // Phase 34.7.3 — Saved Views state
  const [views, setViews] = useState([]);
  const [activeViewId, setActiveViewId] = useState(null);
  const [viewsLoaded, setViewsLoaded] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [newViewName, setNewViewName] = useState('');
  const [newViewDefault, setNewViewDefault] = useState(false);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignedToMe]);

  // Phase 34.7.3 — Load saved views once and apply default if any
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/lead-views');
        setViews(res.data || []);
        const def = (res.data || []).find(v => v.is_default);
        if (def && !viewsLoaded) {
          applyView(def);
        }
      } catch (e) {
        // non-fatal
      } finally {
        setViewsLoaded(true);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyView = (v) => {
    if (!v || !v.filters) return;
    setStatusFilters(v.filters.statuses || []);
    setHealthFilters(v.filters.healths || []);
    setAssignedToMe(Boolean(v.filters.assigned_to_me));
    setActiveViewId(v.id);
  };

  const handleSaveView = async () => {
    const name = newViewName.trim();
    if (!name) { toast.error('View name is required'); return; }
    try {
      const payload = {
        name,
        is_default: newViewDefault,
        filters: {
          statuses: statusFilters,
          healths: healthFilters,
          assigned_to_me: assignedToMe,
        },
      };
      const res = await api.post('/lead-views', payload);
      // Refresh list (other defaults may have been unset server-side)
      const list = await api.get('/lead-views');
      setViews(list.data || []);
      setActiveViewId(res.data.id);
      setSaveDialogOpen(false);
      setNewViewName('');
      setNewViewDefault(false);
      toast.success(`View "${name}" saved`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save view');
    }
  };

  const handleDeleteView = async (id) => {
    if (!window.confirm('Delete this view?')) return;
    try {
      await api.delete(`/lead-views/${id}`);
      setViews(views.filter(v => v.id !== id));
      if (activeViewId === id) setActiveViewId(null);
      toast.success('View deleted');
    } catch (e) {
      toast.error('Failed to delete view');
    }
  };

  const handleSetDefault = async (id) => {
    try {
      await api.patch(`/lead-views/${id}`, { is_default: true });
      const list = await api.get('/lead-views');
      setViews(list.data || []);
      toast.success('Default view updated');
    } catch (e) {
      toast.error('Failed to update default');
    }
  };

  const handleClearFilters = () => {
    setStatusFilters([]);
    setHealthFilters([]);
    setAssignedToMe(false);
    setActiveViewId(null);
  };

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

  // Filter by status[] + health[] (multi-select; empty = no filter)
  const filteredLeads = leads
    .filter(lead => statusFilters.length === 0 || statusFilters.includes(lead.status_id))
    .filter(lead => healthFilters.length === 0 || healthFilters.includes(healthByLead[lead.id]?.health?.band));

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

      {/* Status + Health Filters (Phase 34.7.3 — multi-select + Saved Views) */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-[220px]">
              <MultiSelect
                options={statuses.map(s => ({ value: s.id, label: s.name, color: s.color }))}
                value={statusFilters}
                onChange={(v) => { setStatusFilters(v); setActiveViewId(null); }}
                placeholder="All Statuses"
                allLabel="All Statuses"
                testId="status-filter"
              />
            </div>
            <div className="w-[200px]">
              <MultiSelect
                options={HEALTH_OPTIONS}
                value={healthFilters}
                onChange={(v) => { setHealthFilters(v); setActiveViewId(null); }}
                placeholder="All Health"
                allLabel="All Health"
                testId="health-filter"
              />
            </div>
            <label
              className="flex items-center gap-2 text-sm cursor-pointer select-none px-3 py-1.5 rounded-md border bg-card hover:bg-accent"
              data-testid="assigned-to-me-toggle"
            >
              <input
                type="checkbox"
                checked={assignedToMe}
                onChange={(e) => { setAssignedToMe(e.target.checked); setActiveViewId(null); }}
                className="h-4 w-4 accent-violet-600"
                data-testid="assigned-to-me-checkbox"
              />
              <span className="font-medium">Assigned to Me</span>
            </label>

            {/* Saved Views dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" data-testid="views-dropdown-btn">
                  <Bookmark className="w-3.5 h-3.5 mr-1.5" />
                  {activeViewId
                    ? (views.find(v => v.id === activeViewId)?.name || 'View')
                    : 'Views'}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-72">
                <DropdownMenuLabel>Saved Views</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {views.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-muted-foreground">No saved views yet.</div>
                ) : (
                  views.map(v => (
                    <DropdownMenuItem
                      key={v.id}
                      className="flex items-center justify-between gap-2 cursor-pointer"
                      onClick={() => applyView(v)}
                      data-testid={`view-item-${v.id}`}
                    >
                      <span className="flex items-center gap-1.5 truncate">
                        {v.is_default ? <Star className="w-3 h-3 text-amber-500 fill-current" /> : null}
                        {v.name}
                      </span>
                      <span className="flex items-center gap-1">
                        {!v.is_default && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleSetDefault(v.id); }}
                            className="p-1 rounded hover:bg-muted text-muted-foreground"
                            title="Set as default"
                            data-testid={`view-set-default-${v.id}`}
                          >
                            <StarOff className="w-3 h-3" />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteView(v.id); }}
                          className="p-1 rounded hover:bg-rose-100 text-rose-600"
                          title="Delete view"
                          data-testid={`view-delete-${v.id}`}
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </span>
                    </DropdownMenuItem>
                  ))
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setSaveDialogOpen(true)} data-testid="save-current-view-btn">
                  <SaveIcon className="w-3.5 h-3.5 mr-1.5" />
                  Save current filters as view
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <span className="text-sm text-muted-foreground ml-auto">
              {filteredLeads.length} leads
            </span>
            {(statusFilters.length > 0 || healthFilters.length > 0 || assignedToMe) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearFilters}
                data-testid="clear-filters-btn"
              >
                Clear filters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Save View Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save view</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="view-name">Name</Label>
              <Input
                id="view-name"
                value={newViewName}
                onChange={(e) => setNewViewName(e.target.value)}
                placeholder="e.g. Hot leads I own"
                data-testid="view-name-input"
                autoFocus
              />
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={newViewDefault}
                onChange={(e) => setNewViewDefault(e.target.checked)}
                className="h-4 w-4 accent-violet-600"
                data-testid="view-default-checkbox"
              />
              Set as default view (auto-load on Leads page open)
            </label>
            <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
              <strong>Saves:</strong>{' '}
              {statusFilters.length} status filter{statusFilters.length !== 1 ? 's' : ''},{' '}
              {healthFilters.length} health filter{healthFilters.length !== 1 ? 's' : ''}
              {assignedToMe ? ', Assigned to Me' : ''}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveView} data-testid="confirm-save-view-btn">
              <SaveIcon className="w-4 h-4 mr-1.5" /> Save view
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
              statusFilters.length > 0 || healthFilters.length > 0 || assignedToMe
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
