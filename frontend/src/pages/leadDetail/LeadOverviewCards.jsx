import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Separator } from '../../components/ui/separator';
import {
  Building2, Mail, Phone, User, Tag, DollarSign, Percent,
} from 'lucide-react';
import { formatCurrency, formatDateTime } from '../../utils/api';

const InfoItem = ({ icon: Icon, label, value }) => (
  <div className="flex items-start gap-3">
    <Icon className="w-4 h-4 text-muted-foreground mt-0.5" />
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value || '-'}</p>
    </div>
  </div>
);

export const LeadOverviewCard = ({ lead }) => (
  <Card>
    <CardHeader>
      <div className="flex items-start justify-between">
        <div>
          <CardTitle className="text-2xl">{lead.title}</CardTitle>
          <CardDescription className="mt-1">
            Created {formatDateTime(lead.created_at)} by {lead.created_by_name}
          </CardDescription>
        </div>
        <Badge
          className="text-sm"
          style={{
            backgroundColor: `${lead.status_color}20`,
            color: lead.status_color,
            borderColor: lead.status_color,
          }}
        >
          {lead.status_name || 'New'}
        </Badge>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      {lead.description && <p className="text-muted-foreground">{lead.description}</p>}
      <div className="grid sm:grid-cols-2 gap-4">
        <InfoItem icon={Tag} label="Category" value={lead.primary_category_name} />
        {lead.secondary_category_name && (
          <InfoItem icon={Tag} label="Sub-category" value={lead.secondary_category_name} />
        )}
        <InfoItem icon={DollarSign} label="Deal Value" value={formatCurrency(lead.deal_value)} />
        {lead.selling_partner_name && (
          <InfoItem icon={Building2} label="Selling Partner" value={lead.selling_partner_name} />
        )}
        {lead.sales_associate_name && (
          <InfoItem icon={User} label="Sales Associate" value={lead.sales_associate_name} />
        )}
      </div>
    </CardContent>
  </Card>
);

export const CustomerInfoCard = ({ lead }) => (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <User className="w-5 h-5 text-primary" />
        Customer Information
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="grid sm:grid-cols-2 gap-4">
        <InfoItem icon={User} label="Name" value={lead.customer_name} />
        <InfoItem icon={Mail} label="Email" value={lead.customer_email} />
        {lead.customer_phone && (
          <InfoItem icon={Phone} label="Phone" value={lead.customer_phone} />
        )}
        {lead.customer_company && (
          <InfoItem icon={Building2} label="Company" value={lead.customer_company} />
        )}
      </div>
    </CardContent>
  </Card>
);

export const CommissionBreakdownCard = ({ lead }) => {
  const c = lead.commission_breakdown;
  if (!c || !lead.deal_value) return null;
  return (
    <Card data-testid="commission-breakdown">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Percent className="w-5 h-5 text-primary" />
          Commission Breakdown
        </CardTitle>
        <CardDescription>Transparent view of how commission is distributed</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex justify-between items-center py-2">
            <span className="text-muted-foreground">Total Deal Value</span>
            <span className="font-semibold text-lg">{formatCurrency(c.total_deal_value)}</span>
          </div>
          <Separator />
          <div className="flex justify-between items-center py-2">
            <span className="text-muted-foreground">Vyapaar Network ({c.vyapaar_percentage}%)</span>
            <span className="font-medium text-primary">{formatCurrency(c.vyapaar_share)}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-muted-foreground">Selling Partner Share</span>
            <span className="font-medium text-green-600">{formatCurrency(c.selling_partner_share)}</span>
          </div>
          {c.sales_associate_share && (
            <div className="flex justify-between items-center py-2">
              <span className="text-muted-foreground">
                Sales Associate ({c.sales_associate_percentage}% of Vyapaar share)
              </span>
              <span className="font-medium text-purple-600">{formatCurrency(c.sales_associate_share)}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
