import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import { Loader2, Tag, X, UserPlus } from 'lucide-react';

export const CompanyFormDialog = ({
  open,
  onOpenChange,
  editingCompany,
  formData,
  setFormData,
  categoriesByPrimary,
  secondaryCategories,
  submitting,
  onSubmit,
  onToggleSubcategory,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>{editingCompany ? 'Edit Company' : 'Add New Company'}</DialogTitle>
        <DialogDescription>
          {editingCompany ? 'Update company details' : 'Create a new company account'}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label>Company Name *</Label>
          <Input
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter company name"
            data-testid="company-name-input"
          />
        </div>

        <div className="space-y-2">
          <Label>Company Type *</Label>
          <Select
            value={formData.type}
            onValueChange={(v) => setFormData({ ...formData, type: v, subcategory_ids: [] })}
          >
            <SelectTrigger data-testid="company-type-select">
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="selling_partner">Selling Partner</SelectItem>
              <SelectItem value="customer">Customer</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Vyapaar Commission (%)</Label>
          <Input
            type="number" min="0" max="100" step="0.1"
            value={formData.vyapaar_commission_percentage}
            onChange={(e) => setFormData({ ...formData, vyapaar_commission_percentage: e.target.value })}
            placeholder="15"
            data-testid="company-commission-input"
          />
          <p className="text-xs text-muted-foreground">Default commission rate for this company's deals</p>
        </div>

        {formData.type === 'selling_partner' && (
          <SubcategoryPicker
            formData={formData}
            secondaryCategories={secondaryCategories}
            categoriesByPrimary={categoriesByPrimary}
            onToggle={onToggleSubcategory}
          />
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Contact Email</Label>
            <Input
              type="email"
              value={formData.contact_email}
              onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
              placeholder="contact@company.com"
            />
          </div>
          <div className="space-y-2">
            <Label>Contact Phone</Label>
            <Input
              value={formData.contact_phone}
              onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
              placeholder="+91 98765 43210"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Address</Label>
          <Input
            value={formData.address}
            onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            placeholder="Company address"
          />
        </div>

        {(formData.type === 'customer' || formData.type === 'selling_partner') && !editingCompany && (
          <DefaultUserSection formData={formData} setFormData={setFormData} />
        )}
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>Cancel</Button>
        <Button onClick={onSubmit} disabled={submitting} data-testid="company-submit-btn">
          {submitting ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>
          ) : 'Save Company'}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

const SubcategoryPicker = ({ formData, secondaryCategories, categoriesByPrimary, onToggle }) => (
  <div className="space-y-3">
    <Label className="flex items-center gap-2">
      <Tag className="w-4 h-4" />
      Service Sub-categories
    </Label>
    <p className="text-xs text-muted-foreground">
      Select the service categories this partner specializes in
    </p>
    {formData.subcategory_ids.length > 0 && (
      <div className="flex flex-wrap gap-2 p-2 bg-muted rounded-md">
        {formData.subcategory_ids.map(id => {
          const cat = secondaryCategories.find(c => c.id === id);
          return cat ? (
            <Badge key={id} variant="secondary" className="flex items-center gap-1">
              {cat.name}
              <X className="w-3 h-3 cursor-pointer" onClick={() => onToggle(id)} />
            </Badge>
          ) : null;
        })}
      </div>
    )}
    <div className="border rounded-md max-h-[200px] overflow-y-auto">
      {Object.entries(categoriesByPrimary).map(([primaryName, categories]) => (
        <div key={primaryName} className="border-b last:border-b-0">
          <div className="px-3 py-2 bg-muted/50 font-medium text-sm">{primaryName}</div>
          <div className="p-2 space-y-1">
            {categories.map(cat => (
              <div key={cat.id} className="flex items-center space-x-2">
                <Checkbox
                  id={cat.id}
                  checked={formData.subcategory_ids.includes(cat.id)}
                  onCheckedChange={() => onToggle(cat.id)}
                />
                <label htmlFor={cat.id} className="text-sm cursor-pointer">{cat.name}</label>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
);

const DefaultUserSection = ({ formData, setFormData }) => (
  <div className="border-t pt-4 mt-4">
    <p className="text-sm font-medium mb-3 flex items-center gap-2">
      <UserPlus className="w-4 h-4" />
      Default {formData.type === 'selling_partner' ? 'Selling Partner' : 'Customer'} User *
    </p>
    <p className="text-xs text-muted-foreground mb-3">
      {formData.type === 'selling_partner'
        ? 'This user will be created with Selling Partner role. Without it, the company will not appear in lead assignment dropdowns.'
        : 'This user will be created with Customer role and can add more team members'}
    </p>
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label>User Name *</Label>
        <Input
          value={formData.default_user_name}
          onChange={(e) => setFormData({ ...formData, default_user_name: e.target.value })}
          placeholder="Full name"
          data-testid="default-user-name"
        />
      </div>
      <div className="space-y-2">
        <Label>User Email *</Label>
        <Input
          type="email"
          value={formData.default_user_email}
          onChange={(e) => setFormData({ ...formData, default_user_email: e.target.value })}
          placeholder="user@company.com"
          data-testid="default-user-email"
        />
      </div>
      <div className="space-y-2">
        <Label>User Phone</Label>
        <Input
          value={formData.default_user_phone}
          onChange={(e) => setFormData({ ...formData, default_user_phone: e.target.value })}
          placeholder="+91 98765 43210"
        />
      </div>
      <div className="space-y-2">
        <Label>Password</Label>
        <Input
          type="password"
          value={formData.default_user_password}
          onChange={(e) => setFormData({ ...formData, default_user_password: e.target.value })}
          placeholder={`Default: ${formData.type === 'selling_partner' ? 'partner123' : 'customer123'}`}
        />
      </div>
    </div>
  </div>
);

export default CompanyFormDialog;
