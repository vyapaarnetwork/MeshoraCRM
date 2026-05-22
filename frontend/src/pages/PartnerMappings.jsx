import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Checkbox } from '../components/ui/checkbox';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Network, Search, Building2, Grid3X3, List, UserPlus, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const PartnerMappings = () => {
  const [loading, setLoading] = useState(true);
  const [primaryCategories, setPrimaryCategories] = useState([]);
  const [secondaryCategories, setSecondaryCategories] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [pending, setPending] = useState(new Set());
  const [userDialogCompany, setUserDialogCompany] = useState(null);

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

  const refreshCompanies = async () => {
    try {
      const res = await api.get('/master/partner-mappings');
      setCompanies(res.data);
    } catch (e) { /* ignore */ }
  };

  // Shared toggle handler used by both views
  const toggleMapping = async (companyId, subcategoryId, nextMapped) => {
    const key = `${companyId}:${subcategoryId}`;
    if (pending.has(key)) return;
    setPending(prev => new Set(prev).add(key));

    // Optimistic update
    setCompanies(prev => prev.map(c => {
      if (c.id !== companyId) return c;
      const current = new Set(c.subcategory_ids || []);
      if (nextMapped) current.add(subcategoryId); else current.delete(subcategoryId);
      return { ...c, subcategory_ids: Array.from(current) };
    }));

    try {
      await api.post('/master/partner-subcategory-toggle', {
        company_id: companyId,
        subcategory_id: subcategoryId,
        mapped: nextMapped,
      });
    } catch (e) {
      // Revert on failure
      setCompanies(prev => prev.map(c => {
        if (c.id !== companyId) return c;
        const current = new Set(c.subcategory_ids || []);
        if (nextMapped) current.delete(subcategoryId); else current.add(subcategoryId);
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

      <Tabs defaultValue="by-subcategory" className="space-y-4">
        <TabsList>
          <TabsTrigger value="by-subcategory" data-testid="tab-by-subcategory" className="gap-2">
            <List className="w-4 h-4" /> By Sub-category
          </TabsTrigger>
          <TabsTrigger value="matrix" data-testid="tab-matrix" className="gap-2">
            <Grid3X3 className="w-4 h-4" /> Matrix
          </TabsTrigger>
        </TabsList>

        <TabsContent value="by-subcategory">
          <BySubcategoryView
            primaryCategories={primaryCategories}
            secondaryCategories={secondaryCategories}
            companies={companies}
            pending={pending}
            onToggle={toggleMapping}
            onAddUser={(c) => setUserDialogCompany(c)}
          />
        </TabsContent>

        <TabsContent value="matrix">
          <MatrixView
            primaryCategories={primaryCategories}
            secondaryCategories={secondaryCategories}
            companies={companies}
            pending={pending}
            onToggle={toggleMapping}
            onAddUser={(c) => setUserDialogCompany(c)}
          />
        </TabsContent>
      </Tabs>

      <AddPartnerUserDialog
        company={userDialogCompany}
        open={!!userDialogCompany}
        onClose={() => setUserDialogCompany(null)}
        onSuccess={async () => {
          setUserDialogCompany(null);
          await refreshCompanies();
        }}
      />
    </div>
  );
};

/* -------------------- By Sub-category view -------------------- */
const BySubcategoryView = ({ primaryCategories, secondaryCategories, companies, pending, onToggle, onAddUser }) => {
  const [selectedPrimaryId, setSelectedPrimaryId] = useState('');
  const [selectedSubId, setSelectedSubId] = useState('');
  const [search, setSearch] = useState('');

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

  const selectedSub = secondaryCategories.find(s => s.id === selectedSubId);

  return (
    <>
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
        <Card className="mt-6">
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
                  const noUsers = !c.active_user_count || c.active_user_count === 0;
                  return (
                    <div
                      key={c.id}
                      className="flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors"
                      data-testid={`mapping-row-${c.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <Building2 className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <p className="font-medium flex items-center gap-2">
                            {c.name}
                            {noUsers && (
                              <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700 text-xs gap-1">
                                <AlertTriangle className="w-3 h-3" /> No users
                              </Badge>
                            )}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {c.active_user_count || 0} active user{c.active_user_count === 1 ? '' : 's'} · Mapped to {(c.subcategory_ids || []).length} sub-categories
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {noUsers && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            onClick={() => onAddUser(c)}
                            data-testid={`add-user-btn-${c.id}`}
                          >
                            <UserPlus className="w-3.5 h-3.5" /> Add User
                          </Button>
                        )}
                        {mapped && <Badge className="bg-green-100 text-green-700 border-green-200">Mapped</Badge>}
                        <Switch
                          checked={mapped}
                          disabled={isPending}
                          onCheckedChange={(checked) => onToggle(c.id, selectedSubId, checked)}
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
        <Card className="mt-6">
          <CardContent className="py-12 text-center text-muted-foreground">
            Select a sub-category above to manage partner mappings.
          </CardContent>
        </Card>
      )}
    </>
  );
};

/* -------------------- Matrix view -------------------- */
const MatrixView = ({ primaryCategories, secondaryCategories, companies, pending, onToggle, onAddUser }) => {
  const [primaryFilter, setPrimaryFilter] = useState('');
  const [companySearch, setCompanySearch] = useState('');

  const visibleSubs = useMemo(() => {
    if (!primaryFilter) return secondaryCategories;
    return secondaryCategories.filter(s => s.primary_category_id === primaryFilter);
  }, [primaryFilter, secondaryCategories]);

  const visibleCompanies = useMemo(() => {
    const q = companySearch.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter(c => c.name.toLowerCase().includes(q));
  }, [companies, companySearch]);

  // Group sub-categories by primary for visual headers
  const groupedSubs = useMemo(() => {
    const map = new Map();
    visibleSubs.forEach(s => {
      const pname = s.primary_category_name || 'Other';
      if (!map.has(pname)) map.set(pname, []);
      map.get(pname).push(s);
    });
    return Array.from(map.entries()); // [ [primaryName, subs[]], ... ]
  }, [visibleSubs]);

  const companyMapsCount = (c) => (c.subcategory_ids || []).length;
  const isMapped = (c, subId) => (c.subcategory_ids || []).includes(subId);

  // Column-level select-all / clear-all for a single sub-category
  const setAllForSub = (subId, mapped) => {
    visibleCompanies.forEach(c => {
      const current = isMapped(c, subId);
      if (current !== mapped) onToggle(c.id, subId, mapped);
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Grid3X3 className="w-5 h-5 text-primary" />
            Mapping Matrix
          </CardTitle>
          <CardDescription>
            Check or uncheck a cell to map a partner company to a sub-category. Rows = companies,
            columns = sub-categories. Use column header chips to map/unmap all visible companies at once.
          </CardDescription>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <Select
            value={primaryFilter || 'all'}
            onValueChange={(v) => setPrimaryFilter(v === 'all' ? '' : v)}
          >
            <SelectTrigger className="w-full sm:w-56" data-testid="matrix-primary-filter">
              <SelectValue placeholder="All primary categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All primary categories</SelectItem>
              {primaryCategories.map(p => (
                <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={companySearch}
              onChange={(e) => setCompanySearch(e.target.value)}
              placeholder="Search partner companies..."
              className="pl-9"
              data-testid="matrix-company-search"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {visibleSubs.length === 0 || visibleCompanies.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {visibleCompanies.length === 0 ? 'No partner companies match your search.' : 'No sub-categories under this primary category.'}
          </div>
        ) : (
          <div className="overflow-auto max-h-[70vh] border rounded-md" data-testid="matrix-table-wrap">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-20 bg-background">
                {/* Primary category group row */}
                <tr className="border-b">
                  <th className="sticky left-0 z-30 bg-background text-left px-3 py-2 align-bottom min-w-[220px] border-r">
                    <div className="font-semibold">Partner Company</div>
                    <div className="text-xs text-muted-foreground font-normal">
                      {visibleCompanies.length} shown
                    </div>
                  </th>
                  {groupedSubs.map(([pname, subs]) => (
                    <th
                      key={pname}
                      colSpan={subs.length}
                      className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide bg-muted/40 border-l"
                    >
                      {pname}
                    </th>
                  ))}
                </tr>
                {/* Sub-category header row */}
                <tr className="border-b">
                  <th className="sticky left-0 z-30 bg-background border-r" />
                  {visibleSubs.map(s => {
                    const totalMapped = visibleCompanies.filter(c => isMapped(c, s.id)).length;
                    const allMapped = totalMapped === visibleCompanies.length && visibleCompanies.length > 0;
                    return (
                      <th
                        key={s.id}
                        className="px-2 py-2 align-bottom border-l min-w-[110px] text-center"
                        data-testid={`matrix-col-${s.id}`}
                      >
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-xs font-medium leading-tight">{s.name}</span>
                          <button
                            type="button"
                            onClick={() => setAllForSub(s.id, !allMapped)}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-muted-foreground transition-colors"
                            data-testid={`matrix-col-toggle-${s.id}`}
                            title={allMapped ? 'Unmap all visible companies' : 'Map all visible companies'}
                          >
                            {totalMapped}/{visibleCompanies.length} {allMapped ? '(clear)' : '(all)'}
                          </button>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {visibleCompanies.map((c, idx) => (
                  <tr
                    key={c.id}
                    className={idx % 2 === 0 ? 'bg-background' : 'bg-muted/20'}
                    data-testid={`matrix-row-${c.id}`}
                  >
                    <td className="sticky left-0 z-10 px-3 py-2 border-r bg-inherit">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="font-medium truncate flex items-center gap-1.5">
                            {c.name}
                            {(!c.active_user_count) && (
                              <span title="No active users" className="text-amber-600 flex-shrink-0">
                                <AlertTriangle className="w-3.5 h-3.5" />
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground flex items-center gap-2">
                            <span>{c.active_user_count || 0} users · {companyMapsCount(c)} mapped</span>
                            {(!c.active_user_count) && (
                              <button
                                type="button"
                                onClick={() => onAddUser(c)}
                                className="text-amber-700 underline hover:no-underline"
                                data-testid={`matrix-add-user-${c.id}`}
                              >
                                Add user
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    {visibleSubs.map(s => {
                      const mapped = isMapped(c, s.id);
                      const key = `${c.id}:${s.id}`;
                      const isPending = pending.has(key);
                      return (
                        <td
                          key={s.id}
                          className="border-l text-center align-middle"
                        >
                          <div className="flex items-center justify-center py-2">
                            <Checkbox
                              checked={mapped}
                              disabled={isPending}
                              onCheckedChange={(checked) => onToggle(c.id, s.id, !!checked)}
                              data-testid={`matrix-cell-${c.id}-${s.id}`}
                              aria-label={`Map ${c.name} to ${s.name}`}
                            />
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
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

/* -------------------- Add Partner User Dialog -------------------- */
const AddPartnerUserDialog = ({ company, open, onClose, onSuccess }) => {
  const [form, setForm] = useState({ name: '', email: '', phone: '', password: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) setForm({ name: '', email: '', phone: '', password: '' });
  }, [open, company]);

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      toast.error('Name and email are required');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/users', {
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password || 'partner123',
        role: 'selling_partner',
        company_id: company.id,
        phone: form.phone || null,
      });
      toast.success(`User created for ${company.name}`);
      onSuccess();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  if (!company) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="add-user-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-primary" />
            Add Selling Partner User
          </DialogTitle>
          <DialogDescription>
            Create a selling-partner user under <strong>{company.name}</strong>. Once added, the
            company will appear in lead-assignment dropdowns for its mapped sub-categories.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1.5">
            <Label>Name *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Full name"
              data-testid="dialog-user-name"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Email *</Label>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="user@partner.com"
              data-testid="dialog-user-email"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Phone</Label>
            <Input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+91 98765 43210"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Password</Label>
            <Input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Default: partner123"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={submitting} data-testid="dialog-submit-user">
            {submitting ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating...</>) : 'Create User'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PartnerMappings;
