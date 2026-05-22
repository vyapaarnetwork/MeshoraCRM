import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Activity, AlertTriangle, AlertCircle, Info, CheckCircle2, ArrowRight, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';

const severityStyles = {
  critical: {
    icon: AlertCircle,
    badgeClass: 'bg-red-100 text-red-700 border-red-200',
    barClass: 'bg-red-500',
    iconClass: 'text-red-600',
  },
  warning: {
    icon: AlertTriangle,
    badgeClass: 'bg-amber-100 text-amber-700 border-amber-200',
    barClass: 'bg-amber-500',
    iconClass: 'text-amber-600',
  },
  info: {
    icon: Info,
    badgeClass: 'bg-blue-100 text-blue-700 border-blue-200',
    barClass: 'bg-blue-500',
    iconClass: 'text-blue-600',
  },
};

const HealthCheckWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const navigate = useNavigate();

  const fetchHealth = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const res = await api.get('/dashboard/health-check');
      setData(res.data);
    } catch (e) {
      setData({ items: [], total_issues: 0, error: true });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <Card data-testid="health-check-widget">
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="space-y-2">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  const items = data?.items || [];
  const total = data?.total_issues || 0;
  const allClear = items.length === 0;

  return (
    <Card className="animate-fade-in" data-testid="health-check-widget">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Health Check
            {!allClear && (
              <Badge variant="secondary" data-testid="health-total-badge">
                {total} issue{total === 1 ? '' : 's'}
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            {allClear
              ? 'No configuration gaps detected. Everything looks good.'
              : 'Configuration and workflow gaps that need attention.'}
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => fetchHealth(true)}
          disabled={refreshing}
          data-testid="health-refresh-btn"
          className="gap-1"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {allClear ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <CheckCircle2 className="w-12 h-12 text-green-500 mb-2" />
            <p className="font-medium text-green-700">All systems healthy</p>
            <p className="text-sm text-muted-foreground mt-1">
              No partner gaps, stale drafts, or orphaned sub-categories.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map(item => {
              const style = severityStyles[item.severity] || severityStyles.info;
              const Icon = style.icon;
              return (
                <div
                  key={item.key}
                  className="flex items-stretch gap-0 border rounded-lg overflow-hidden hover:shadow-sm transition-shadow"
                  data-testid={`health-item-${item.key}`}
                >
                  <div className={`w-1 flex-shrink-0 ${style.barClass}`} />
                  <div className="flex-1 p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${style.iconClass}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-medium">{item.title}</p>
                          <Badge className={`${style.badgeClass} font-mono`} data-testid={`health-count-${item.key}`}>
                            {item.count}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {item.description}
                        </p>
                        {item.details && item.details.length > 0 && (
                          <p className="text-xs text-muted-foreground mt-1 truncate">
                            e.g. {item.details.slice(0, 3).map(d => d.name).join(', ')}
                            {item.count > 3 && ` and ${item.count - 3} more`}
                          </p>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(item.action_path)}
                      className="gap-1 flex-shrink-0"
                      data-testid={`health-action-${item.key}`}
                    >
                      {item.action_label}
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default HealthCheckWidget;
