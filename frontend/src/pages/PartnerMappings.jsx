import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Skeleton } from '../components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Network, Search, Building2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const PartnerMappings = () => {
  const [loading, setLoading] = useState(true);
  const [primaryCategories, setPrimaryCategories] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [selectedPrimaryId, setSelectedPrimaryId] = useState('');
  const [selectedSubId, setSelectedSubId] = useState('');
  const [search, setSearch] = useState('');
  const [pending, setPending] = useState(new Set());

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [primaryRes, secondaryRes, companiesRes] = await Promise.all([
        api.get('/master/primary-categories'),
        api.get('/master/secondary-categories'),
        api.get('/master/partner-mappings'),
      ]);
      setPrimaryCategories(primaryRes.data);
      setSecondaryCategories(secondaryRes.data);
      setCompanies(companiesRes.data);
    } catch (e) {
      toast.error('Failed to load partner mappings');
    } finally {
      setLoading(false);
    }
  };

  // Sub-categories filtered by selected primary
  const subOptions = useMemo(() => {
    if (!selectedPrimaryId) return secondaryCategories;
    return secondaryCategories.filter(s => s.primary_category_id === selectedPrimaryId);
  }, [selectedPrimaryId, secondaryCategories]);

  const filteredCompanies = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter(c => c.name.toLowerCase().includes(q));
  }, [companies, search]);

  const isMapped = (company) =>
    Array.isArray(company.subcategory_ids) && company.subcategory_ids.includes(selectedSubId);

  const mappedCount = useMemo(
    () => companies.filter(c => (c.subcategory_ids || []).includes(selectedSubId)).length,
    [companies, selectedSubId]
  );

  const handleToggle = async (company, nextMapped) => {
    if (!selectedSubId) return;
    const key = `${company.id}:${selectedSubId}`;
    setPending(prev => new Set(prev).add(key));

    // Optimistic update
    setCompanies(prev => prev.map(c => {
      if (c.id !== company.id) return c;
      const current = new Set(c.subcategory_ids || []);
      if (nextMapped) current.add(selectedSubId); else current.delete(selectedSubId);
      return { ...c, subcategory_ids: Array.from(current) };
    }));

    try {
      await api.post('/master/partner-subcategory-toggle', {
        company_id: company.id,
        subcategory_id: selectedSubId,
        mapped: nextMapped,
      });
      toast.success(`${company.name} ${nextMapped ? 'mapped to' : 'unmapped from'} sub-category`);
    } catch (e) {
      // Revert on failure
      setCompanies(prev => prev.map(c => {
        if (c.id !== company.id) return c;
        const current = new Set(c.subcategory_ids || []);
        if (nextMapped) current.delete(selectedSubId); else current.add(selectedSubId);
        return { ...c, subcategory_ids: Array.from(current) };
      }));
      toast.error(e.response?.data?.detail || 'Failed to update mapping');
    } finally {
      setPending(prev => {
        const n = new Set(prev);
        n.delete(key);
        return n;
      });
    }
  };

  if (loading) return <PartnerMappingsSkeleton />;

  const selectedSub = secondaryCategories.find(s => s.id === selectedSubId);

  return (
    <div className="space-y-6" data-testid="partner-mappings-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
          <Network className="w-7 h-7 text-primary" />
          Partner Mappings
        </h1>
        <p className="text-muted-foreground mt-1">
          Map selling-partner companies to the sub-categories they can serve. This drives the
          dependent Selling Partner dropdown on the Add Lead screen.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Select Sub-category</CardTitle>
          <CardDescription>
            Pick a sub-category to view and edit which partner companies are mapped to it.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Primary Category (filter)</Label>
            <Select
              value={selectedPrimaryId || 'all'}
              onValueChange={(v) => {
                setSelectedPrimaryId(v === 'all' ? '' : v);
                setSelectedSubId('');
              }}
            >
              <SelectTrigger data-testid="primary-filter-select">
                <SelectValue placeholder="All primary categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All primary categories</SelectItem>
                {primaryCategories.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Sub-category *</Label>
            <Select value={selectedSubId} onValueChange={setSelectedSubId}>
              <SelectTrigger data-testid="subcategory-select">
                <SelectValue placeholder="Select sub-category" />
              </SelectTrigger>
              <SelectContent>
                {subOptions.map(s => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name} {s.primary_category_name && <span className="text-muted-foreground">— {s.primary_category_name}</span>}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {selectedSubId ? (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-primary" />
                Partner Companies for "{selectedSub?.name}"
              </CardTitle>
              <CardDescription>
                <Badge variant="secondary" data-testid="mapped-count-badge">
                  {mappedCount} / {companies.length} mapped
                </Badge>
              </CardDescription>
            </div>
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search partner companies..."
                className="pl-9"
                data-testid="company-search-input"
              />
            </div>
          </CardHeader>
          <CardContent>
            {filteredCompanies.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                {companies.length === 0
                  ? 'No selling-partner companies exist yet. Create one in Companies first.'
                  : 'No companies match your search.'}
              </div>
            ) : (
              <div className="divide-y border rounded-md">
                {filteredCompanies.map(c => {
                  const mapped = isMapped(c);
                  const key = `${c.id}:${selectedSubId}`;
                  const isPending = pending.has(key);
                  return (
                    <div
                      key={c.id}
                      className="flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors"
                      data-testid={`mapping-row-${c.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <Building2 className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <p className="font-medium">{c.name}</p>
                          <p className="text-xs text-muted-foreground">
                            Mapped to {(c.subcategory_ids || []).length} sub-categories total
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {mapped && <Badge className="bg-green-100 text-green-700 border-green-200">Mapped</Badge>}
                        <Switch
                          checked={mapped}
                          disabled={isPending}
                          onCheckedChange={(checked) => handleToggle(c, checked)}
                          data-testid={`mapping-toggle-${c.id}`}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Select a sub-category above to manage partner mappings.
          </CardContent>
        </Card>
      )}
    </div>
  );
};

const PartnerMappingsSkeleton = () => (
  <div className="space-y-6">
    <Skeleton className="h-10 w-72" />
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-48" />
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
    <Card>
      <CardContent className="space-y-2 py-6">
        {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-14 w-full" />)}
      </CardContent>
    </Card>
  </div>
);

export default PartnerMappings;
