import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
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
  BarChart3, 
  Download, 
  CalendarIcon, 
  TrendingUp,
  DollarSign,
  Users,
  FileText,
  Building2,
  Percent,
  PieChart
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
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Legend,
  AreaChart,
  Area
} from 'recharts';
import api, { formatCurrency, formatDate } from '../utils/api';
import { toast } from 'sonner';
import { format, subMonths } from 'date-fns';

const COLORS = ['#4169E1', '#DC143C', '#10B981', '#F59E0B', '#8B5CF6', '#64748B'];

const Reports = () => {
  const { user, isAdmin, isSellingPartner, isSalesAssociate } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [vyapaarReport, setVyapaarReport] = useState(null);
  const [partnerReport, setPartnerReport] = useState(null);
  const [associateReport, setAssociateReport] = useState(null);
  
  const [dateRange, setDateRange] = useState({
    start: subMonths(new Date(), 6),
    end: new Date()
  });
  const [selectedPeriod, setSelectedPeriod] = useState('6months');
  const [reportPeriod, setReportPeriod] = useState('monthly');

  useEffect(() => {
    fetchReports();
  }, [dateRange, reportPeriod]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = {
        start_date: format(dateRange.start, 'yyyy-MM-dd'),
        end_date: format(dateRange.end, 'yyyy-MM-dd'),
        period: reportPeriod
      };

      const [statsRes] = await Promise.all([
        api.get('/dashboard/stats', { params })
      ]);
      
      setStats(statsRes.data);

      // Fetch role-specific reports
      if (isAdmin) {
        const vyapaarRes = await api.get('/reports/vyapaar-revenue', { params });
        setVyapaarReport(vyapaarRes.data);
      }
      
      if (isSellingPartner) {
        const reportRes = await api.get(`/reports/selling-partner/${user.id}/detailed`, { params });
        setPartnerReport(reportRes.data);
      } else if (isSalesAssociate) {
        const reportRes = await api.get(`/reports/sales-associate/${user.id}/detailed`, { params });
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
            Comprehensive business intelligence and commission tracking
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
            
            <Select value={reportPeriod} onValueChange={setReportPeriod}>
              <SelectTrigger className="w-full sm:w-[180px]" data-testid="report-period-filter">
                <SelectValue placeholder="Group by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">Monthly</SelectItem>
                <SelectItem value="quarterly">Quarterly</SelectItem>
                <SelectItem value="yearly">Yearly</SelectItem>
              </SelectContent>
            </Select>
            
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>Showing:</span>
              <Badge variant="outline">{formatDate(dateRange.start)}</Badge>
              <span>to</span>
              <Badge variant="outline">{formatDate(dateRange.end)}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Admin Tabs */}
      {isAdmin && (
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview" data-testid="overview-tab">Overview</TabsTrigger>
            <TabsTrigger value="vyapaar" data-testid="vyapaar-tab">Vyapaar Revenue</TabsTrigger>
            <TabsTrigger value="partners" data-testid="partners-tab">Partner Performance</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
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
                color="text-green-600"
                testId="report-conversion"
              />
              <SummaryCard
                title="Total Revenue"
                value={formatCurrency(stats?.total_revenue || 0)}
                icon={DollarSign}
                testId="report-revenue"
              />
              <SummaryCard
                title="Net Commission"
                value={formatCurrency(vyapaarReport?.summary?.net_revenue || 0)}
                icon={Percent}
                color="text-purple-600"
                testId="report-commission"
              />
            </div>

            {/* Charts */}
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <PieChart className="w-5 h-5 text-primary" />
                    Pipeline Distribution
                  </CardTitle>
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
                        </RechartsPieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChart message="No pipeline data" />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-primary" />
                    Category Distribution
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
            </div>
          </TabsContent>

          {/* Vyapaar Revenue Tab */}
          <TabsContent value="vyapaar" className="space-y-6">
            {vyapaarReport && (
              <>
                {/* Revenue Summary */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
                  <SummaryCard
                    title="Won Deals"
                    value={vyapaarReport.summary.total_won_deals}
                    icon={FileText}
                    testId="vyapaar-won-deals"
                  />
                  <SummaryCard
                    title="Total Deal Value"
                    value={formatCurrency(vyapaarReport.summary.total_deal_value)}
                    icon={DollarSign}
                    testId="vyapaar-deal-value"
                  />
                  <SummaryCard
                    title="Gross Commission"
                    value={formatCurrency(vyapaarReport.summary.gross_commission)}
                    icon={Percent}
                    color="text-blue-600"
                    testId="vyapaar-gross"
                  />
                  <SummaryCard
                    title="SA Payouts"
                    value={formatCurrency(vyapaarReport.summary.sa_payouts)}
                    icon={Users}
                    color="text-purple-600"
                    testId="vyapaar-payouts"
                  />
                  <SummaryCard
                    title="Net Revenue"
                    value={formatCurrency(vyapaarReport.summary.net_revenue)}
                    icon={TrendingUp}
                    color="text-green-600"
                    testId="vyapaar-net"
                  />
                </div>

                {/* Period Breakdown Chart */}
                {vyapaarReport.period_breakdown?.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Revenue & Commission Trend</CardTitle>
                      <CardDescription>Gross vs Net revenue over time</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="h-[350px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={vyapaarReport.period_breakdown}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                            <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
                            <Tooltip formatter={(v) => formatCurrency(v)} />
                            <Legend />
                            <Area 
                              type="monotone" 
                              dataKey="gross_commission" 
                              stackId="1"
                              stroke="#4169E1" 
                              fill="#4169E1" 
                              fillOpacity={0.3}
                              name="Gross Commission"
                            />
                            <Area 
                              type="monotone" 
                              dataKey="net_revenue" 
                              stackId="2"
                              stroke="#10B981" 
                              fill="#10B981" 
                              fillOpacity={0.3}
                              name="Net Revenue"
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Partner Profitability */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Building2 className="w-5 h-5 text-primary" />
                        Partner Profitability
                      </CardTitle>
                      <CardDescription>Commission earned by partner</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[300px]">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Partner</TableHead>
                              <TableHead className="text-right">Deals</TableHead>
                              <TableHead className="text-right">Revenue</TableHead>
                              <TableHead className="text-right">Commission</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {vyapaarReport.partner_profitability?.map((partner, index) => (
                              <TableRow key={index}>
                                <TableCell className="font-medium">{partner.name}</TableCell>
                                <TableCell className="text-right">{partner.deals}</TableCell>
                                <TableCell className="text-right">{formatCurrency(partner.revenue)}</TableCell>
                                <TableCell className="text-right text-primary font-medium">
                                  {formatCurrency(partner.vyapaar_commission)}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </ScrollArea>
                    </CardContent>
                  </Card>

                  {/* Category Contribution */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-primary" />
                        Category Contribution
                      </CardTitle>
                      <CardDescription>Revenue by business category</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {vyapaarReport.category_contribution?.length > 0 ? (
                        <div className="h-[300px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={vyapaarReport.category_contribution} layout="vertical">
                              <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                              <XAxis type="number" tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
                              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 12 }} />
                              <Tooltip formatter={(v) => formatCurrency(v)} />
                              <Bar dataKey="commission" fill="#4169E1" radius={[0, 4, 4, 0]} name="Commission" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <EmptyChart message="No category data" />
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Deals Table */}
                <Card>
                  <CardHeader>
                    <CardTitle>Won Deals Detail</CardTitle>
                    <CardDescription>Complete list of won deals with commission breakdown</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[400px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Deal</TableHead>
                            <TableHead>Partner</TableHead>
                            <TableHead>Category</TableHead>
                            <TableHead className="text-right">Deal Value</TableHead>
                            <TableHead className="text-right">Vyapaar</TableHead>
                            <TableHead className="text-right">SA Payout</TableHead>
                            <TableHead className="text-right">Net</TableHead>
                            <TableHead>Date</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {vyapaarReport.deals?.map((deal) => (
                            <TableRow key={deal.id}>
                              <TableCell className="font-medium">{deal.title}</TableCell>
                              <TableCell>{deal.partner}</TableCell>
                              <TableCell>
                                <Badge variant="outline">{deal.category}</Badge>
                              </TableCell>
                              <TableCell className="text-right">{formatCurrency(deal.deal_value)}</TableCell>
                              <TableCell className="text-right text-blue-600">{formatCurrency(deal.vyapaar_commission)}</TableCell>
                              <TableCell className="text-right text-purple-600">{formatCurrency(deal.sa_payout)}</TableCell>
                              <TableCell className="text-right text-green-600 font-medium">{formatCurrency(deal.net_revenue)}</TableCell>
                              <TableCell className="text-muted-foreground">{deal.date}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* Partners Tab */}
          <TabsContent value="partners" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Partner Performance Overview</CardTitle>
                <CardDescription>View individual partner reports from the Users page</CardDescription>
              </CardHeader>
              <CardContent>
                {vyapaarReport?.partner_profitability?.length > 0 ? (
                  <div className="h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={vyapaarReport.partner_profitability}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-45} textAnchor="end" height={80} />
                        <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
                        <Tooltip formatter={(v) => formatCurrency(v)} />
                        <Legend />
                        <Bar dataKey="revenue" fill="#4169E1" name="Total Revenue" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="vyapaar_commission" fill="#10B981" name="Vyapaar Commission" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyChart message="No partner data available" />
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {/* Selling Partner Report */}
      {isSellingPartner && partnerReport && (
        <div className="space-y-6">
          <Card className="bg-gradient-to-br from-primary/5 to-secondary/5">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-center gap-6">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <Building2 className="w-8 h-8 text-primary" />
                </div>
                <div className="text-center sm:text-left flex-1">
                  <h2 className="text-xl font-bold">{partnerReport.partner_info.name}</h2>
                  <p className="text-muted-foreground">{partnerReport.partner_info.company}</p>
                  <Badge variant="outline" className="mt-2">
                    Base Rate: {partnerReport.partner_info.base_commission_rate}% to Vyapaar
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <SummaryCard
              title="Total Deals"
              value={partnerReport.summary.total_deals}
              icon={FileText}
              testId="partner-total-deals"
            />
            <SummaryCard
              title="Won Deals"
              value={partnerReport.summary.won_deals}
              icon={TrendingUp}
              color="text-green-600"
              testId="partner-won-deals"
            />
            <SummaryCard
              title="Your Revenue"
              value={formatCurrency(partnerReport.summary.total_revenue_generated)}
              icon={DollarSign}
              testId="partner-revenue"
            />
            <SummaryCard
              title="Conversion Rate"
              value={`${partnerReport.summary.conversion_rate}%`}
              icon={Percent}
              color="text-purple-600"
              testId="partner-conversion"
            />
          </div>

          {/* Period Breakdown */}
          {partnerReport.period_breakdown?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Revenue Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={partnerReport.period_breakdown}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="period" />
                      <YAxis tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
                      <Tooltip formatter={(v) => formatCurrency(v)} />
                      <Legend />
                      <Line type="monotone" dataKey="revenue" stroke="#4169E1" strokeWidth={2} name="Your Revenue" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Sales Associate Report */}
      {isSalesAssociate && associateReport && (
        <div className="space-y-6">
          <Card className="bg-gradient-to-br from-purple-50 to-blue-50">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-center gap-6">
                <div className="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center">
                  <Users className="w-8 h-8 text-purple-600" />
                </div>
                <div className="text-center sm:text-left flex-1">
                  <h2 className="text-xl font-bold">{associateReport.associate_info.name}</h2>
                  <p className="text-muted-foreground">{associateReport.associate_info.email}</p>
                </div>
                <div className="text-center sm:text-right">
                  <p className="text-sm text-muted-foreground">Lifetime Earnings</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {formatCurrency(associateReport.lifetime_earnings)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            <SummaryCard
              title="Total Referrals"
              value={associateReport.summary.total_referrals}
              icon={FileText}
              testId="associate-referrals"
            />
            <SummaryCard
              title="Converted"
              value={associateReport.summary.converted_deals}
              icon={TrendingUp}
              color="text-green-600"
              testId="associate-converted"
            />
            <SummaryCard
              title="Pending"
              value={associateReport.summary.pending_deals}
              icon={Users}
              color="text-yellow-600"
              testId="associate-pending"
            />
            <SummaryCard
              title="Total Earnings"
              value={formatCurrency(associateReport.summary.total_earnings)}
              icon={DollarSign}
              color="text-purple-600"
              testId="associate-earnings"
            />
            <SummaryCard
              title="Forecasted"
              value={formatCurrency(associateReport.summary.forecasted_earnings)}
              icon={Percent}
              color="text-blue-600"
              testId="associate-forecast"
            />
          </div>

          {/* Deals Table */}
          <Card>
            <CardHeader>
              <CardTitle>Your Referrals</CardTitle>
              <CardDescription>Deals you referred and their earnings</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Deal</TableHead>
                      <TableHead>Partner</TableHead>
                      <TableHead className="text-right">Deal Value</TableHead>
                      <TableHead className="text-right">Your %</TableHead>
                      <TableHead className="text-right">Earnings</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {associateReport.deals?.map((deal) => (
                      <TableRow key={deal.id}>
                        <TableCell className="font-medium">{deal.title}</TableCell>
                        <TableCell>{deal.partner}</TableCell>
                        <TableCell className="text-right">{formatCurrency(deal.deal_value)}</TableCell>
                        <TableCell className="text-right">{deal.commission_percentage}%</TableCell>
                        <TableCell className="text-right text-purple-600 font-medium">
                          {formatCurrency(deal.earnings)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={deal.status === 'Won' ? 'default' : 'secondary'}>
                            {deal.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{deal.date}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

const SummaryCard = ({ title, value, icon: Icon, color = 'text-primary', testId }) => (
  <Card data-testid={testId}>
    <CardContent className="pt-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className="p-3 bg-muted rounded-lg">
          <Icon className={`w-5 h-5 ${color}`} />
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
