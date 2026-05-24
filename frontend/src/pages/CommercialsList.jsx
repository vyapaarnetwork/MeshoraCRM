import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { formatCurrency, formatDate } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Briefcase, Repeat, FileText, Search, Filter } from 'lucide-react';

const CommercialsList = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  useEffect(() => {
    const params = {};
    if (typeFilter !== 'all') params.type = typeFilter;
    api.get('/commercials', { params }).then((r) => setItems(r.data || [])).finally(() => setLoading(false));
  }, [typeFilter]);

  const filtered = items.filter((i) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (i.lead_title || '').toLowerCase().includes(q) ||
      (i.customer_name || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6" data-testid="commercials-list-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Commercials</h1>
          <p className="text-sm text-muted-foreground">All post-sales project & contract setups across won deals.</p>
        </div>
      </div>

      <Card>
        <CardContent className="py-4 flex flex-col md:flex-row md:items-end gap-3">
          <div className="flex-1">
            <label className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Search className="w-3 h-3" /> Search</label>
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Lead title or customer…" data-testid="commercials-search" />
          </div>
          <div className="w-full md:w-48">
            <label className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Filter className="w-3 h-3" /> Type</label>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger data-testid="commercials-type-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="one_time">One-Time Project</SelectItem>
                <SelectItem value="recurring">Recurring Contract</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="text-muted-foreground text-sm">Loading…</div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <FileText className="w-10 h-10 mx-auto mb-2 opacity-40" />
            <p>No commercials yet.</p>
            <p className="text-xs mt-1">When you mark a lead as Won, set up its commercials from the lead detail page.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <Link key={c.id} to={`/commercials/${c.id}`} className="block group" data-testid={`commercial-card-${c.id}`}>
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="flex items-center gap-1">
                      {c.type === 'one_time' ? <Briefcase className="w-3 h-3" /> : <Repeat className="w-3 h-3" />}
                      {c.type === 'one_time' ? 'One-Time' : 'Recurring'}
                    </Badge>
                    {c.type === 'recurring' && c.contract_status && (
                      <Badge className="capitalize bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200">
                        {c.contract_status.replace('_', ' ')}
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-base mt-2">{c.lead_title}</CardTitle>
                  <p className="text-xs text-muted-foreground">{c.customer_name}</p>
                </CardHeader>
                <CardContent className="text-sm space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">{c.type === 'one_time' ? 'Project value' : 'Contract value'}</span>
                    <span className="font-semibold">{formatCurrency(c.type === 'one_time' ? c.total_value : c.contract_value)}</span>
                  </div>
                  {c.type === 'one_time' && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Milestones</span>
                      <span>{(c.milestones || []).length}</span>
                    </div>
                  )}
                  {c.type === 'recurring' && (
                    <>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Billing</span>
                        <span className="capitalize">{(c.billing_frequency || '—').replace('_', ' ')}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Ends</span>
                        <span>{formatDate(c.contract_end_date) || '—'}</span>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default CommercialsList;
