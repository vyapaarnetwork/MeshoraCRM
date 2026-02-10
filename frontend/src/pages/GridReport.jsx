import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import SortableTable from '../components/SortableTable';
import { 
  TrendingUp, 
  DollarSign, 
  Users, 
  Target,
  BarChart3,
  Download,
  Filter,
  Calendar,
  Building2,
  CheckCircle2,
  XCircle,
  Clock
} from 'lucide-react';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';

const GridReport = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [reportData, setReportData] = useState(null);
  const [partners, setPartners] = useState([]);
  const [categories, setCategories] = useState([]);
  const [statuses, setStatuses] = useState([]);
  
  // Filters
  const [filters, setFilters] = useState({
    start_date: '',
    end_date: '',
    partner_id: '',
    category_id: '',
    status_id: ''
  });

  useEffect(() => {
    fetchReferenceData();
    fetchReport();
  }, []);

  const fetchReferenceData = async () => {
    try {
      const [usersRes, catRes, statusRes] = await Promise.all([
        api.get('/users'),
        api.get('/master/primary-categories'),
        api.get('/master/lead-status')
      ]);
      setPartners(usersRes.data.filter(u => u.role === 'selling_partner'));
      setCategories(catRes.data);
      setStatuses(statusRes.data);
    } catch (error) {
      console.error('Failed to load reference data:', error);
    }
  };

  const fetchReport = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.partner_id) params.append('partner_id', filters.partner_id);
      if (filters.category_id) params.append('category_id', filters.category_id);
      if (filters.status_id) params.append('status_id', filters.status_id);
      
      const response = await api.get(`/reports/grid-performance?${params.toString()}`);
      setReportData(response.data);
    } catch (error) {
      toast.error('Failed to load report');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    fetchReport();
  };

  const clearFilters = () => {
    setFilters({
      start_date: '',
      end_date: '',
      partner_id: '',
      category_id: '',
      status_id: ''
    });
    setTimeout(fetchReport, 0);
  };

  const exportToCSV = () => {
    if (!reportData?.grid_data) return;
    
    const headers = ['Title', 'Customer', 'Partner', 'Category', 'Status', 'Deal Value', 'Vyapaar Commission', 'Partner Revenue', 'Date'];
    const rows = reportData.grid_data.map(row => [
      row.title,
      row.customer_name,
      row.partner_name,
      row.category,
      row.status,
      row.deal_value,
      row.vyapaar_commission,
      row.partner_revenue,
      row.created_at
    ]);
    
    const csvContent = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `vyapaar-performance-${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success('Report exported successfully');
  };

  // Table columns for main grid
  const gridColumns = [
    {
      key: 'title',
      label: 'Lead',
      render: (value, row) => (
        <div>
          <p className="font-medium">{value}</p>
          <p className="text-xs text-muted-foreground">{row.customer_name}</p>
        </div>
      )
    },
    {
      key: 'partner_name',
      label: 'Partner',
      render: (value, row) => (
        <div>
          <p className="font-medium">{value}</p>
          {row.company_name !== '-' && (
            <p className="text-xs text-muted-foreground">{row.company_name}</p>
          )}
        </div>
      )
    },
    {
      key: 'category',
      label: 'Category',
      render: (value) => <Badge variant="outline">{value}</Badge>
    },
    {
      key: 'status',
      label: 'Status',
      render: (value, row) => (
        <Badge style={{ backgroundColor: row.status_color + '20', color: row.status_color, borderColor: row.status_color }}>
          {value}
        </Badge>
      )
    },
    {
      key: 'deal_value',
      label: 'Deal Value',
      render: (value) => <span className="font-medium">{formatCurrency(value)}</span>
    },
    {
      key: 'vyapaar_commission',
      label: 'Vyapaar Commission',
      render: (value, row) => (
        <div>
          <span className="font-medium text-green-600">{formatCurrency(value)}</span>
          <p className="text-xs text-muted-foreground">{row.vyapaar_commission_pct}%</p>
        </div>
      )
    },
    {
      key: 'partner_revenue',
      label: 'Partner Revenue',
      render: (value) => <span className="font-medium text-blue-600">{formatCurrency(value)}</span>
    },
    {
      key: 'created_at',
      label: 'Date',
      render: (value) => <span className="text-sm text-muted-foreground">{formatDate(value)}</span>
    }
  ];

  // Partner summary columns
  const partnerColumns = [
    {
      key: 'partner_name',
      label: 'Partner',
      render: (value, row) => (
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="text-xs font-medium text-primary">
              {value.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <p className="font-medium">{value}</p>
            <p className="text-xs text-muted-foreground">{row.company_name}</p>
          </div>
        </div>
      )
    },
    {
      key: 'total_leads',
      label: 'Total Leads'
    },
    {
      key: 'won_deals',
      label: 'Won Deals',
      render: (value) => <span className="font-medium text-green-600">{value}</span>
    },
    {
      key: 'conversion_rate',
      label: 'Conversion',
      render: (value) => (
        <Badge variant={value >= 50 ? 'default' : value >= 25 ? 'secondary' : 'outline'}>
          {value}%
        </Badge>
      )
    },
    {
      key: 'total_deal_value',
      label: 'Total Value',
      render: (value) => formatCurrency(value)
    },
    {
      key: 'vyapaar_commission',
      label: 'Vyapaar Commission',
      render: (value) => <span className="font-medium text-green-600">{formatCurrency(value)}</span>
    },
    {
      key: 'partner_revenue',
      label: 'Partner Revenue',
      render: (value) => <span className="font-medium text-blue-600">{formatCurrency(value)}</span>
    }
  ];

  if (loading && !reportData) return <GridReportSkeleton />;

  const summary = reportData?.summary || {};
  const partnerSummary = reportData?.partner_summary || [];
  const gridData = reportData?.grid_data || [];

  return (
    <div className="space-y-6" data-testid="grid-report-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Grid Performance Report</h1>
          <p className="text-muted-foreground mt-1">
            Vyapaar Network's performance across all selling partners
          </p>
        </div>
        <Button onClick={exportToCSV} variant="outline" data-testid="export-btn">
          <Download className="w-4 h-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                data-testid="filter-start-date"
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                data-testid="filter-end-date"
              />
            </div>
            <div className="space-y-2">
              <Label>Partner</Label>
              <Select value={filters.partner_id || 'all'} onValueChange={(v) => handleFilterChange('partner_id', v === 'all' ? '' : v)}>
                <SelectTrigger data-testid="filter-partner">
                  <SelectValue placeholder="All Partners" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Partners</SelectItem>
                  {partners.map(p => (
                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select value={filters.category_id || 'all'} onValueChange={(v) => handleFilterChange('category_id', v === 'all' ? '' : v)}>
                <SelectTrigger data-testid="filter-category">
                  <SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map(c => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={filters.status_id || 'all'} onValueChange={(v) => handleFilterChange('status_id', v === 'all' ? '' : v)}>
                <SelectTrigger data-testid="filter-status">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  {statuses.map(s => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={applyFilters} className="flex-1" data-testid="apply-filters-btn">
                Apply
              </Button>
              <Button onClick={clearFilters} variant="outline" data-testid="clear-filters-btn">
                Clear
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Leads</p>
                <p className="text-2xl font-bold">{summary.total_leads}</p>
              </div>
              <div className="p-3 rounded-lg bg-primary/10 text-primary">
                <Target className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Won Deals</p>
                <p className="text-2xl font-bold text-green-600">{summary.won_deals}</p>
              </div>
              <div className="p-3 rounded-lg bg-green-100 text-green-600">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Lost Deals</p>
                <p className="text-2xl font-bold text-red-600">{summary.lost_deals}</p>
              </div>
              <div className="p-3 rounded-lg bg-red-100 text-red-600">
                <XCircle className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Deal Value</p>
                <p className="text-2xl font-bold">{formatCurrency(summary.total_deal_value)}</p>
              </div>
              <div className="p-3 rounded-lg bg-blue-100 text-blue-600">
                <DollarSign className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-green-50 border-green-200">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-700">Vyapaar Commission</p>
                <p className="text-2xl font-bold text-green-600">{formatCurrency(summary.total_vyapaar_commission)}</p>
              </div>
              <div className="p-3 rounded-lg bg-green-200 text-green-700">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-blue-700">Partner Revenue</p>
                <p className="text-2xl font-bold text-blue-600">{formatCurrency(summary.total_partner_revenue)}</p>
              </div>
              <div className="p-3 rounded-lg bg-blue-200 text-blue-700">
                <Building2 className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Partner Performance Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Partner Performance Summary
          </CardTitle>
          <CardDescription>
            Performance breakdown by selling partner (sorted by won deals)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SortableTable
            columns={partnerColumns}
            data={partnerSummary}
            rowKey="partner_id"
            pageSize={10}
            emptyMessage="No partner data available"
          />
        </CardContent>
      </Card>

      {/* Detailed Grid */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            Detailed Lead Grid
          </CardTitle>
          <CardDescription>
            All leads with sortable columns and filters
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SortableTable
            columns={gridColumns}
            data={gridData}
            rowKey="id"
            pageSize={15}
            onRowClick={(row) => navigate(`/leads/${row.id}`)}
            emptyMessage="No leads found with current filters"
          />
        </CardContent>
      </Card>
    </div>
  );
};

const GridReportSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-64 mb-2" />
      <Skeleton className="h-4 w-96" />
    </div>
    <Card>
      <CardContent className="pt-6">
        <div className="grid grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
      {[1, 2, 3, 4, 5, 6].map(i => (
        <Card key={i}>
          <CardContent className="pt-6">
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map(i => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export default GridReport;
