import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Loader2, Eye, EyeOff, Building2, User, Briefcase, Users } from 'lucide-react';
import { toast } from 'sonner';

const LOGO_URL = "https://customer-assets.emergentagent.com/job_209b3ec1-0b0e-469f-a49b-80bce3fa5de7/artifacts/8t9iukb4_Vyapaar-Logo.png";
const BG_IMAGE = "https://images.unsplash.com/photo-1765954296215-6c3aadec42aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBvZmZpY2UlMjBhYnN0cmFjdCUyMGJ1c2luZXNzJTIwbmV0d29ya3xlbnwwfHx8fDE3NzA2NTkxMTZ8MA&ixlib=rb-4.1.0&q=85";

const roles = [
  { value: 'selling_partner', label: 'Selling Partner', icon: Building2, description: 'Company that sells products/services' },
  { value: 'sales_associate', label: 'Sales Associate', icon: Briefcase, description: 'Independent individual who brings leads' },
  { value: 'customer', label: 'Customer', icon: Users, description: 'Company or individual looking for vendors' }
];

const Register = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: '',
    company_name: '',
    phone: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleRoleChange = (value) => {
    setFormData({ ...formData, role: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    if ((formData.role === 'selling_partner' || formData.role === 'customer') && !formData.company_name) {
      setError('Company name is required for this role');
      return;
    }

    setLoading(true);

    try {
      const userData = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        role: formData.role,
        company_name: formData.company_name || null,
        phone: formData.phone || null
      };
      
      await register(userData);
      toast.success('Account created successfully!');
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const needsCompany = formData.role === 'selling_partner' || formData.role === 'customer';

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Image */}
      <div 
        className="hidden lg:flex lg:w-1/2 relative bg-cover bg-center"
        style={{ backgroundImage: `url(${BG_IMAGE})` }}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-primary/90 to-secondary/80" />
        <div className="relative z-10 flex flex-col justify-between p-12 text-white">
          <div>
            <img src={LOGO_URL} alt="Vyapaar Network" className="h-12 w-auto brightness-0 invert" />
          </div>
          <div className="space-y-4">
            <h1 className="text-4xl font-bold tracking-tight">
              Join the Network
            </h1>
            <p className="text-lg text-white/80 max-w-md">
              Create your account and start managing your business relationships, leads, and commissions efficiently.
            </p>
          </div>
          <div className="text-sm text-white/60">
            © 2025 Vyapaar Network. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12 bg-background overflow-y-auto">
        <div className="w-full max-w-md space-y-6 animate-fade-in py-8">
          {/* Mobile Logo */}
          <div className="lg:hidden flex justify-center">
            <img src={LOGO_URL} alt="Vyapaar Network" className="h-10 w-auto" />
          </div>

          <Card className="border-0 shadow-xl">
            <CardHeader className="space-y-1 text-center">
              <CardTitle className="text-2xl font-bold">Create an account</CardTitle>
              <CardDescription>Enter your details to get started</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <Alert variant="destructive" className="animate-scale-in">
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="John Doe"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    data-testid="register-name-input"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="you@company.com"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    data-testid="register-email-input"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone">Phone (Optional)</Label>
                  <Input
                    id="phone"
                    name="phone"
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={formData.phone}
                    onChange={handleChange}
                    disabled={loading}
                    data-testid="register-phone-input"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <Select value={formData.role} onValueChange={handleRoleChange} required>
                    <SelectTrigger className="h-11" data-testid="register-role-select">
                      <SelectValue placeholder="Select your role" />
                    </SelectTrigger>
                    <SelectContent>
                      {roles.map((role) => (
                        <SelectItem key={role.value} value={role.value}>
                          <div className="flex items-center gap-2">
                            <role.icon className="w-4 h-4" />
                            <span>{role.label}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {formData.role && (
                    <p className="text-xs text-muted-foreground">
                      {roles.find(r => r.value === formData.role)?.description}
                    </p>
                  )}
                </div>

                {needsCompany && (
                  <div className="space-y-2 animate-fade-in">
                    <Label htmlFor="company_name">Company Name</Label>
                    <Input
                      id="company_name"
                      name="company_name"
                      type="text"
                      placeholder="Your Company Ltd."
                      value={formData.company_name}
                      onChange={handleChange}
                      required={needsCompany}
                      disabled={loading}
                      data-testid="register-company-input"
                      className="h-11"
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={formData.password}
                      onChange={handleChange}
                      required
                      disabled={loading}
                      data-testid="register-password-input"
                      className="h-11 pr-10"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-11 w-11 text-muted-foreground"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type="password"
                    placeholder="••••••••"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    data-testid="register-confirm-password-input"
                    className="h-11"
                  />
                </div>

                <Button 
                  type="submit" 
                  className="w-full h-11 bg-primary hover:bg-primary/90"
                  disabled={loading}
                  data-testid="register-submit-btn"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating account...
                    </>
                  ) : (
                    'Create account'
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center text-sm">
                <span className="text-muted-foreground">Already have an account? </span>
                <Link 
                  to="/login" 
                  className="text-primary font-medium hover:underline"
                  data-testid="login-link"
                >
                  Sign in
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Register;
