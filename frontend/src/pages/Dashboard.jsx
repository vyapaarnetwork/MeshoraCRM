import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  TrendingUp, 
  TrendingDown, 
  Users, 
  FileText, 
  DollarSign, 
  Percent,
  BarChart3,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  CalendarRange,
  X as XIcon
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend
} from 'recharts';
import api, { formatCurrency, getRoleLabel } from '../utils/api';
import HealthCheckWidget from '../components/HealthCheckWidget';
import CommercialsWidget from '../components/CommercialsWidget';
import DashboardDigest from '../components/DashboardDigest';

const COLORS = ['#4169E1', '#DC143C', '#10B981', '#F59E0B', '#8B5CF6', '#64748B'];

const Dashboard = () => {
  const { user, isAdmin, isSellingPartner, isSalesAssociate, isCustomer } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [activePreset, setActivePreset] = useState('all');

  const fetchDashboardData = useCallback(async (sd, ed) => {
    setLoading(true);
    try {
      const params = {};
      if (sd) params.start_date = sd;
      if (ed) {
        // Make end_date inclusive of the entire day
        params.end_date = ed.length === 10 ? `${ed}T23:59:59` : ed;
      }
      const response = await api.get('/dashboard/stats', { params });
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData(startDate, endDate);
  }, [fetchDashboardData, startDate, endDate]);

  const toIsoDate = (date) => date.toISOString().slice(0, 10);

  const applyPreset = (preset) => {
    setActivePreset(preset);
    const today = new Date();
    const todayStr = toIsoDate(today);
    if (preset === 'all') {
      setStartDate('');
      setEndDate('');
    } else if (preset === 'today') {
      setStartDate(todayStr);
      setEndDate(todayStr);
    } else if (preset === '7d') {
      const past = new Date();
      past.setDate(past.getDate() - 6);
      setStartDate(toIsoDate(past));
      setEndDate(todayStr);
    } else if (preset === '30d') {
      const past = new Date();
      past.setDate(past.getDate() - 29);
      setStartDate(toIsoDate(past));
      setEndDate(todayStr);
    } else if (preset === 'month') {
      const first = new Date(today.getFullYear(), today.getMonth(), 1);
      setStartDate(toIsoDate(first));
      setEndDate(todayStr);
    }
  };

  const handleManualChange = (field, value) => {
    setActivePreset('custom');
    if (field === 'start') setStartDate(value);
    else setEndDate(value);
  };

  const clearFilters = () => applyPreset('all');

  const hasActiveFilter = startDate || endDate;

  if (loading && !stats) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Welcome back, {user?.name?.split(' ')[0]}!
          </h1>
          <p className="text-muted-foreground mt-1">
            Here's what's happening with your {isAdmin ? 'platform' : 'account'} today.
          </p>
        </div>
        <Badge variant="outline" className="w-fit">
          {getRoleLabel(user?.role)}
        </Badge>
      </div>

      {/* Phase 1.5: Daily collaboration digest */}
      <DashboardDigest />

      {/* Date Filter */}
      <Card data-testid="dashboard-date-filter">
        <CardContent className="py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <CalendarRange className="w-4 h-4 text-primary" />
              <span>Filter by date range</span>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              {[
                { key: 'all', label: 'All time' },
                { key: 'today', label: 'Today' },
                { key: '7d', label: 'Last 7d' },
                { key: '30d', label: 'Last 30d' },
                { key: 'month', label: 'This month' },
              ].map((preset) => (
                <Button
                  key={preset.key}
                  type="button"
                  size="sm"
                  variant={activePreset === preset.key ? 'default' : 'outline'}
                  onClick={() => applyPreset(preset.key)}
                  data-testid={`date-preset-${preset.key}`}
                >
                  {preset.label}
                </Button>
              ))}
              <div className="flex items-center gap-2">
                <div className="flex flex-col">
                  <Label htmlFor="dash-start-date" className="text-[10px] uppercase tracking-wider text-muted-foreground">From</Label>
                  <Input
                    id="dash-start-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => handleManualChange('start', e.target.value)}
                    className="h-9 w-[150px]"
                    data-testid="date-start-input"
                    max={endDate || undefined}
                  />
                </div>
                <div className="flex flex-col">
                  <Label htmlFor="dash-end-date" className="text-[10px] uppercase tracking-wider text-muted-foreground">To</Label>
                  <Input
                    id="dash-end-date"
                    type="date"
                    value={endDate}
                    onChange={(e) => handleManualChange('end', e.target.value)}
                    className="h-9 w-[150px]"
                    data-testid="date-end-input"
                    min={startDate || undefined}
                  />
                </div>
                {hasActiveFilter && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={clearFilters}
                    className="h-9"
                    data-testid="date-clear-btn"
                  >
                    <XIcon className="w-4 h-4 mr-1" />
                    Clear
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 stagger-children">
        <StatsCard
          title="Total Leads"
          value={stats?.total_leads || 0}
          icon={FileText}
          trend={stats?.total_leads > 0 ? 'up' : 'neutral'}
          trendValue="Active pipeline"
          testId="stat-total-leads"
        />
        <StatsCard
          title="Won Deals"
          value={stats?.won_deals || 0}
          icon={TrendingUp}
          trend="up"
          trendValue={`${stats?.conversion_rate || 0}% conversion`}
          color="text-green-600"
          testId="stat-won-deals"
        />
        <StatsCard
          title="Total Revenue"
          value={formatCurrency(stats?.total_revenue || 0)}
          icon={DollarSign}
          trend={stats?.total_revenue > 0 ? 'up' : 'neutral'}
          trendValue="From won deals"
          testId="stat-total-revenue"
        />
        {(isAdmin || isSellingPartner) && (
          <StatsCard
            title={isAdmin ? "Platform Commission" : "Your Share"}
            value={formatCurrency(stats?.total_commission || 0)}
            icon={Percent}
            trend="up"
            trendValue="Earned commission"
            color="text-purple-600"
            testId="stat-commission"
          />
        )}
        {isSalesAssociate && (
          <StatsCard
            title="Your Earnings"
            value={formatCurrency(stats?.total_commission || 0)}
            icon={Percent}
            trend="up"
            trendValue="From referrals"
            color="text-purple-600"
            testId="stat-earnings"
          />
        )}
        {isCustomer && (
          <StatsCard
            title="Lost Deals"
            value={stats?.lost_deals || 0}
            icon={TrendingDown}
            trend="down"
            trendValue="Not converted"
            color="text-red-600"
            testId="stat-lost-deals"
          />
        )}
      </div>

      {/* Health Check Widget (Admin only) */}
      {isAdmin && <HealthCheckWidget />}

      {/* Commercials snapshot (Admin only) */}
      {isAdmin && <CommercialsWidget />}

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Leads by Status */}
        <Card className="animate-fade-in" data-testid="leads-by-status-chart">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PieChart className="w-5 h-5 text-primary" />
              Leads by Status
            </CardTitle>
            <CardDescription>Distribution of leads across pipeline stages</CardDescription>
          </CardHeader>
          <CardContent>
            {stats?.leads_by_status?.length > 0 ? (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie
                      data={stats.leads_by_status}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, count }) => `${name}: ${count}`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="count"
                      nameKey="name"
                    >
                      {stats.leads_by_status.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart message="No leads data available" />
            )}
          </CardContent>
        </Card>

        {/* Leads by Category */}
        <Card className="animate-fade-in" data-testid="leads-by-category-chart">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              Leads by Category
            </CardTitle>
            <CardDescription>Business categories with most leads</CardDescription>
          </CardHeader>
          <CardContent>
            {stats?.leads_by_category?.length > 0 ? (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.leads_by_category} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#4169E1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart message="No category data available" />
            )}
          </CardContent>
        </Card>

        {/* Revenue Trend */}
        {(isAdmin || isSellingPartner) && stats?.revenue_trend?.length > 0 && (
          <Card className="lg:col-span-2 animate-fade-in" data-testid="revenue-trend-chart">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                Revenue Trend
              </CardTitle>
              <CardDescription>Monthly revenue from won deals</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stats.revenue_trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                    <YAxis 
                      tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 12 }}
                    />
                    <Tooltip 
                      formatter={(value) => [formatCurrency(value), 'Revenue']}
                    />
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

      {/* Pipeline Progress */}
      {stats?.leads_by_status?.length > 0 && (
        <Card className="animate-fade-in" data-testid="pipeline-progress">
          <CardHeader>
            <CardTitle>Pipeline Progress</CardTitle>
            <CardDescription>Lead distribution across stages</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {stats.leads_by_status.map((status, index) => (
              <div key={status.id} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: status.color || COLORS[index % COLORS.length] }}
                    />
                    <span className="font-medium">{status.name}</span>
                  </div>
                  <span className="text-muted-foreground">
                    {status.count} leads ({((status.count / stats.total_leads) * 100).toFixed(0)}%)
                  </span>
                </div>
                <Progress 
                  value={(status.count / stats.total_leads) * 100} 
                  className="h-2"
                  style={{ '--progress-background': status.color || COLORS[index % COLORS.length] }}
                />
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

// Stats Card Component
const StatsCard = ({ title, value, icon: Icon, trend, trendValue, color = 'text-primary', testId }) => (
  <Card className="hover:shadow-md transition-shadow" data-testid={testId}>
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      <Icon className={`w-5 h-5 ${color}`} />
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
      <div className="flex items-center gap-1 mt-1">
        {trend === 'up' && <ArrowUpRight className="w-4 h-4 text-green-500" />}
        {trend === 'down' && <ArrowDownRight className="w-4 h-4 text-red-500" />}
        <span className="text-xs text-muted-foreground">{trendValue}</span>
      </div>
    </CardContent>
  </Card>
);

// Empty Chart Component
const EmptyChart = ({ message }) => (
  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
    <div className="text-center">
      <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
      <p>{message}</p>
    </div>
  </div>
);

// Loading Skeleton
const DashboardSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-64 mb-2" />
      <Skeleton className="h-4 w-48" />
    </div>
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-4 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-32 mb-2" />
            <Skeleton className="h-3 w-20" />
          </CardContent>
        </Card>
      ))}
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      {[1, 2].map((i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32 mb-2" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[300px] w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

export default Dashboard;
