import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
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
import { Calendar } from '../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { 
  BarChart3, 
  Download, 
  CalendarIcon, 
  TrendingUp,
  DollarSign,
  Users,
  FileText
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';
import { format, subMonths, startOfMonth, endOfMonth } from 'date-fns';

const COLORS = ['#4169E1', '#DC143C', '#10B981', '#F59E0B', '#8B5CF6'];

const Reports = () => {
  const { user, isAdmin, isSellingPartner, isSalesAssociate } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [partnerReport, setPartnerReport] = useState(null);
  const [associateReport, setAssociateReport] = useState(null);
  
  const [dateRange, setDateRange] = useState({
    start: subMonths(new Date(), 6),
    end: new Date()
  });
  const [selectedPeriod, setSelectedPeriod] = useState('6months');

  useEffect(() => {
    fetchReports();
  }, [dateRange]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = {
        start_date: format(dateRange.start, 'yyyy-MM-dd'),
        end_date: format(dateRange.end, 'yyyy-MM-dd')
      };

      const [statsRes] = await Promise.all([
        api.get('/dashboard/stats', { params })
      ]);
      
      setStats(statsRes.data);

      // Fetch role-specific reports
      if (isSellingPartner) {
        const reportRes = await api.get(`/reports/selling-partner/${user.id}`, { params });
        setPartnerReport(reportRes.data);
      } else if (isSalesAssociate) {
        const reportRes = await api.get(`/reports/sales-associate/${user.id}`, { params });
        setAssociateReport(reportRes.data);
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (period) => {
    setSelectedPeriod(period);
    const now = new Date();
    let start;
    
    switch (period) {
      case '1month':
        start = subMonths(now, 1);
        break;
      case '3months':
        start = subMonths(now, 3);
        break;
      case '6months':
        start = subMonths(now, 6);
        break;
      case '1year':
        start = subMonths(now, 12);
        break;
      default:
        start = subMonths(now, 6);
    }
    
    setDateRange({ start, end: now });
  };

  const handleExport = async () => {
    try {
      const params = {
        start_date: format(dateRange.start, 'yyyy-MM-dd'),
        end_date: format(dateRange.end, 'yyyy-MM-dd'),
        format: 'csv'
      };
      
      const response = await api.get('/reports/export', { params });
      const data = response.data.data;
      
      if (data.length === 0) {
        toast.info('No data to export');
        return;
      }
      
      // Convert to CSV
      const headers = Object.keys(data[0]);
      const csvContent = [
        headers.join(','),
        ...data.map(row => headers.map(h => `"${row[h] || ''}"`).join(','))
      ].join('\n');
      
      // Download
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `leads_report_${format(new Date(), 'yyyy-MM-dd')}.csv`;
      a.click();
      
      toast.success('Report exported successfully');
    } catch (error) {
      toast.error('Failed to export report');
    }
  };

  if (loading) return <ReportsSkeleton />;

  return (
    <div className="space-y-6" data-testid="reports-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Reports & Analytics</h1>
          <p className="text-muted-foreground mt-1">
            View performance metrics and business insights
          </p>
        </div>
        <Button onClick={handleExport} variant="outline" data-testid="export-btn">
          <Download className="w-4 h-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <Select value={selectedPeriod} onValueChange={handlePeriodChange}>
              <SelectTrigger className="w-full sm:w-[180px]" data-testid="period-filter">
                <CalendarIcon className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Select period" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1month">Last Month</SelectItem>
                <SelectItem value="3months">Last 3 Months</SelectItem>
                <SelectItem value="6months">Last 6 Months</SelectItem>
                <SelectItem value="1year">Last Year</SelectItem>
              </SelectContent>
            </Select>
            
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>Showing data from</span>
              <Badge variant="outline">{formatDate(dateRange.start)}</Badge>
              <span>to</span>
              <Badge variant="outline">{formatDate(dateRange.end)}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Total Leads"
          value={stats?.total_leads || 0}
          icon={FileText}
          testId="report-total-leads"
        />
        <SummaryCard
          title="Conversion Rate"
          value={`${stats?.conversion_rate || 0}%`}
          icon={TrendingUp}
          testId="report-conversion"
        />
        <SummaryCard
          title="Total Revenue"
          value={formatCurrency(stats?.total_revenue || 0)}
          icon={DollarSign}
          testId="report-revenue"
        />
        <SummaryCard
          title="Won Deals"
          value={stats?.won_deals || 0}
          icon={Users}
          testId="report-won-deals"
        />
      </div>

      {/* Role-specific Reports */}
      {isSellingPartner && partnerReport && (
        <Card data-testid="partner-report">
          <CardHeader>
            <CardTitle>Your Performance Summary</CardTitle>
            <CardDescription>Overview of your deals and earnings</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Deals</p>
                <p className="text-2xl font-bold">{partnerReport.total_deals}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Won Deals</p>
                <p className="text-2xl font-bold text-green-600">{partnerReport.won_deals}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Revenue</p>
                <p className="text-2xl font-bold">{formatCurrency(partnerReport.total_revenue)}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Your Earnings</p>
                <p className="text-2xl font-bold text-primary">
                  {formatCurrency(partnerReport.total_commission_earned)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {isSalesAssociate && associateReport && (
        <Card data-testid="associate-report">
          <CardHeader>
            <CardTitle>Your Referral Summary</CardTitle>
            <CardDescription>Overview of your referrals and earnings</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Referrals</p>
                <p className="text-2xl font-bold">{associateReport.total_referrals}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Converted</p>
                <p className="text-2xl font-bold text-green-600">{associateReport.converted_deals}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Conversion Rate</p>
                <p className="text-2xl font-bold">{associateReport.conversion_rate}%</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Earnings</p>
                <p className="text-2xl font-bold text-primary">
                  {formatCurrency(associateReport.total_earnings)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Pipeline by Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              Pipeline Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.leads_by_status?.length > 0 ? (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={stats.leads_by_status}
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="count"
                      nameKey="name"
                      label={({ name, count }) => `${name}: ${count}`}
                    >
                      {stats.leads_by_status.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart message="No pipeline data" />
            )}
          </CardContent>
        </Card>

        {/* Category Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              Leads by Category
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.leads_by_category?.length > 0 ? (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.leads_by_category}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#4169E1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart message="No category data" />
            )}
          </CardContent>
        </Card>

        {/* Revenue Trend */}
        {stats?.revenue_trend?.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                Revenue Trend
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stats.revenue_trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v) => [formatCurrency(v), 'Revenue']} />
                    <Line 
                      type="monotone" 
                      dataKey="revenue" 
                      stroke="#4169E1" 
                      strokeWidth={2}
                      dot={{ fill: '#4169E1' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

const SummaryCard = ({ title, value, icon: Icon, testId }) => (
  <Card data-testid={testId}>
    <CardContent className="pt-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className="p-3 bg-primary/10 rounded-lg">
          <Icon className="w-5 h-5 text-primary" />
        </div>
      </div>
    </CardContent>
  </Card>
);

const EmptyChart = ({ message }) => (
  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
    <div className="text-center">
      <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
      <p>{message}</p>
    </div>
  </div>
);

const ReportsSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-48 mb-2" />
      <Skeleton className="h-4 w-64" />
    </div>
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="h-10 w-[180px]" />
      </CardContent>
    </Card>
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardContent className="pt-6">
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

export default Reports;
