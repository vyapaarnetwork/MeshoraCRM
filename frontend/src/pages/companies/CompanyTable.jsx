import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../components/ui/table';
import { Building2, Percent, Edit, Paperclip, Plus } from 'lucide-react';
import { formatDate } from '../../utils/api';

export const CompanyTable = ({
  companies,
  searchTerm,
  typeFilter,
  onEdit,
  onOpenDocuments,
  onAdd,
}) => (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <Building2 className="w-5 h-5 text-primary" />
        All Companies ({companies.length})
      </CardTitle>
    </CardHeader>
    <CardContent>
      {companies.length > 0 ? (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Commission Rate</TableHead>
                <TableHead>Sub-categories</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-[120px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {companies.map((company) => (
                <TableRow key={company.id} data-testid={`company-row-${company.id}`}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Building2 className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium">{company.name}</p>
                        {company.address && (
                          <p className="text-xs text-muted-foreground">{company.address}</p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={company.type === 'selling_partner' ? 'default' : 'secondary'}>
                      {company.type === 'selling_partner' ? 'Selling Partner' : 'Customer'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Percent className="w-3 h-3 text-muted-foreground" />
                      <span className="font-medium">{company.vyapaar_commission_percentage}%</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {company.subcategories && company.subcategories.length > 0 ? (
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {company.subcategories.slice(0, 3).map((sub) => (
                          <Badge key={sub.id} variant="outline" className="text-xs">
                            {sub.name}
                          </Badge>
                        ))}
                        {company.subcategories.length > 3 && (
                          <Badge variant="outline" className="text-xs">
                            +{company.subcategories.length - 3} more
                          </Badge>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {company.contact_email && <p className="text-sm">{company.contact_email}</p>}
                    {company.contact_phone && (
                      <p className="text-xs text-muted-foreground">{company.contact_phone}</p>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(company.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => onOpenDocuments(company)}
                        data-testid={`docs-company-${company.id}`}
                        title="View Documents"
                      >
                        <Paperclip className="w-4 h-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => onEdit(company)}
                        data-testid={`edit-company-${company.id}`}
                        title="Edit Company"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="text-center py-12">
          <Building2 className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
          <h3 className="font-semibold mb-1">No companies found</h3>
          <p className="text-muted-foreground text-sm mb-4">
            {searchTerm || typeFilter !== 'all'
              ? 'Try adjusting your filters'
              : 'Get started by adding your first company'}
          </p>
          {!searchTerm && typeFilter === 'all' && (
            <Button onClick={onAdd}>
              <Plus className="w-4 h-4 mr-2" />
              Add Company
            </Button>
          )}
        </div>
      )}
    </CardContent>
  </Card>
);

export default CompanyTable;
