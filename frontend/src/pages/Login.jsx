import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Loader2, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

const LOGO_URL = "https://customer-assets.emergentagent.com/job_209b3ec1-0b0e-469f-a49b-80bce3fa5de7/artifacts/8t9iukb4_Vyapaar-Logo.png";
const BG_IMAGE = "https://images.unsplash.com/photo-1765954296215-6c3aadec42aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBvZmZpY2UlMjBhYnN0cmFjdCUyMGJ1c2luZXNzJTIwbmV0d29ya3xlbnwwfHx8fDE3NzA2NTkxMTZ8MA&ixlib=rb-4.1.0&q=85";

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      toast.success('Welcome back!');
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

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
              Connect. Collaborate.<br />Grow Together.
            </h1>
            <p className="text-lg text-white/80 max-w-md">
              The trusted CRM platform for managing your business partnerships, leads, and commissions.
            </p>
          </div>
          <div className="text-sm text-white/60">
            © 2025 Vyapaar Network. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12 bg-background">
        <div className="w-full max-w-md space-y-8 animate-fade-in">
          {/* Mobile Logo */}
          <div className="lg:hidden flex justify-center">
            <img src={LOGO_URL} alt="Vyapaar Network" className="h-10 w-auto" />
          </div>

          <Card className="border-0 shadow-xl">
            <CardHeader className="space-y-1 text-center">
              <CardTitle className="text-2xl font-bold">Welcome back</CardTitle>
              <CardDescription>Enter your credentials to access your account</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <Alert variant="destructive" className="animate-scale-in">
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                    data-testid="login-email-input"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      disabled={loading}
                      data-testid="login-password-input"
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

                <Button 
                  type="submit" 
                  className="w-full h-11 bg-primary hover:bg-primary/90"
                  disabled={loading}
                  data-testid="login-submit-btn"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    'Sign in'
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center text-sm">
                <span className="text-muted-foreground">Don't have an account? </span>
                <Link 
                  to="/register" 
                  className="text-primary font-medium hover:underline"
                  data-testid="register-link"
                >
                  Create account
                </Link>
              </div>

              {/* Demo credentials hint */}
              <div className="mt-6 p-3 bg-muted rounded-lg text-sm">
                <p className="font-medium text-muted-foreground mb-1">Demo Admin Account:</p>
                <p className="text-xs text-muted-foreground">
                  Email: admin@vyapaarnetwork.com<br />
                  Password: admin123
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Login;
