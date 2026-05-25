import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Loader2, Eye, EyeOff, Mail, Lock, User, Phone, Building2,
  ArrowRight, ShieldCheck, Info, Sparkles, Handshake, Rocket
} from 'lucide-react';
import { toast } from 'sonner';
import { MeshoraMark, MeshoraLogoOnDark } from '../components/MeshoraLogo';

const Register = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
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

    setLoading(true);
    try {
      await register({
        name: formData.name,
        email: formData.email,
        password: formData.password,
        role: 'customer',
        company_name: formData.company_name || null,
        phone: formData.phone || null,
      });
      toast.success('Account created successfully!');
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* ============ Left Panel ============ */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse at top left, #312E81 0%, #1E1B4B 35%, #0F172A 100%)',
          }}
        />
        {/* Constellation overlay */}
        <svg className="absolute inset-0 w-full h-full opacity-30" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <radialGradient id="reg-dot" cx="50%" cy="50%" r="50%">
              <stop offset="0" stopColor="#A78BFA" />
              <stop offset="1" stopColor="#A78BFA" stopOpacity="0" />
            </radialGradient>
            <pattern id="reg-constellation" x="0" y="0" width="80" height="80" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="1.5" fill="url(#reg-dot)" />
              <circle cx="50" cy="40" r="1" fill="url(#reg-dot)" />
              <circle cx="20" cy="60" r="1.3" fill="url(#reg-dot)" />
              <line x1="10" y1="10" x2="50" y2="40" stroke="#A78BFA" strokeWidth="0.3" opacity="0.4" />
              <line x1="50" y1="40" x2="20" y2="60" stroke="#A78BFA" strokeWidth="0.3" opacity="0.4" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#reg-constellation)" />
        </svg>
        <div className="absolute -bottom-32 -right-32 w-[600px] h-[600px] rounded-full blur-3xl opacity-30" style={{ background: 'radial-gradient(circle, #A855F7 0%, transparent 70%)' }} />
        <div className="absolute top-1/3 -left-32 w-[400px] h-[400px] rounded-full blur-3xl opacity-25" style={{ background: 'radial-gradient(circle, #6366F1 0%, transparent 70%)' }} />

        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16 text-white w-full">
          <div>
            <MeshoraLogoOnDark size={48} />
          </div>

          <div className="space-y-6 max-w-xl">
            <h1 className="text-5xl xl:text-6xl font-bold leading-[1.05] tracking-tight">
              <span className="block">Join the</span>
              <span className="block" style={{
                background: 'linear-gradient(90deg, #C4B5FD 0%, #A78BFA 50%, #818CF8 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                Meshora Network.
              </span>
            </h1>
            <p className="text-base xl:text-lg text-white/70 max-w-md leading-relaxed">
              Discover trusted vendors, manage business relationships, and grow with confidence — all in one place.
            </p>
          </div>

          <div className="space-y-8">
            <div className="grid grid-cols-3 gap-3 max-w-xl">
              <FeatureChip icon={Sparkles} title="Quick Setup" body="Get started in under a minute." />
              <FeatureChip icon={Handshake} title="Verified Partners" body="Work with trusted vendors." />
              <FeatureChip icon={Rocket} title="Scale Faster" body="Convert leads into revenue." />
            </div>
            <div className="text-xs text-white/40">
              © {new Date().getFullYear()} Meshora. All rights reserved.
            </div>
          </div>
        </div>
      </div>

      {/* ============ Right Panel — Form ============ */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 lg:p-12 overflow-y-auto">
        <div className="w-full max-w-md space-y-5 animate-fade-in py-4">
          {/* Mobile logo */}
          <div className="lg:hidden flex justify-center mb-4">
            <div className="flex items-center gap-2">
              <MeshoraMark size={36} />
              <span
                className="font-bold text-2xl"
                style={{
                  background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                Meshora
              </span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200/60 dark:border-slate-800 p-8">
            <div className="text-center space-y-1 mb-6">
              <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Create your account</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">Start exploring vendors for your business</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" data-testid="register-form">
              {error && (
                <Alert variant="destructive" className="animate-scale-in">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <IconField icon={User} id="name" name="name" type="text" placeholder="Full name"
                value={formData.name} onChange={handleChange} required disabled={loading}
                testId="register-name-input" autoComplete="name" />

              <IconField icon={Mail} id="email" name="email" type="email" placeholder="you@company.com"
                value={formData.email} onChange={handleChange} required disabled={loading}
                testId="register-email-input" autoComplete="email" />

              <div className="grid grid-cols-2 gap-3">
                <IconField icon={Phone} id="phone" name="phone" type="tel" placeholder="Phone (optional)"
                  value={formData.phone} onChange={handleChange} disabled={loading}
                  testId="register-phone-input" autoComplete="tel" />
                <IconField icon={Building2} id="company_name" name="company_name" type="text" placeholder="Company (optional)"
                  value={formData.company_name} onChange={handleChange} disabled={loading}
                  testId="register-company-input" autoComplete="organization" />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Password (min 6 chars)"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    autoComplete="new-password"
                    data-testid="register-password-input"
                    className="h-11 pl-10 pr-10 bg-slate-50/60 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 focus-visible:ring-violet-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                    data-testid="register-toggle-password-btn"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <IconField icon={Lock} id="confirmPassword" name="confirmPassword" type="password"
                placeholder="Confirm password" value={formData.confirmPassword} onChange={handleChange}
                required disabled={loading} testId="register-confirm-password-input" autoComplete="new-password" />

              <Button
                type="submit"
                disabled={loading}
                data-testid="register-submit-btn"
                className="w-full h-12 text-base font-semibold shadow-lg group mt-2"
                style={{
                  background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%)',
                  color: 'white',
                }}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account…
                  </>
                ) : (
                  <span className="flex items-center justify-center w-full">
                    Create account
                    <ArrowRight className="ml-2 w-5 h-5 transition-transform group-hover:translate-x-1" />
                  </span>
                )}
              </Button>
            </form>

            {/* Info about other roles */}
            <div className="mt-5 p-3 bg-violet-50 dark:bg-violet-950/40 border border-violet-100 dark:border-violet-900 rounded-lg text-xs flex gap-2">
              <Info className="w-4 h-4 text-violet-600 dark:text-violet-400 mt-0.5 flex-shrink-0" />
              <p className="text-violet-800 dark:text-violet-200 leading-relaxed">
                <strong>Selling Partners</strong> and <strong>Sales Associates</strong> are onboarded by your Super Admin.
                Contact your administrator if you need a different account type.
              </p>
            </div>

            {/* Sign in link */}
            <div className="mt-6 text-center text-sm">
              <span className="text-slate-500 dark:text-slate-400">Already have an account? </span>
              <Link to="/login" className="font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400" data-testid="login-link">
                Sign in
              </Link>
            </div>
          </div>

          {/* Security card */}
          <div className="bg-white/60 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-800 rounded-xl p-4 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-violet-50 dark:bg-violet-950/40">
              <ShieldCheck className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Your data is safe with us.</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Enterprise-grade encryption protects everything you share.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const IconField = ({ icon: Icon, testId, ...rest }) => (
  <div className="relative">
    <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
    <Input
      data-testid={testId}
      className="h-11 pl-10 bg-slate-50/60 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 focus-visible:ring-violet-500"
      {...rest}
    />
  </div>
);

const FeatureChip = ({ icon: Icon, title, body }) => (
  <div className="rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 p-4 hover:bg-white/[0.07] transition-colors">
    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-500/30 to-indigo-500/30 flex items-center justify-center mb-3">
      <Icon className="w-4 h-4 text-violet-200" />
    </div>
    <div className="text-sm font-semibold text-white mb-1">{title}</div>
    <div className="text-xs text-white/60 leading-relaxed">{body}</div>
  </div>
);

export default Register;
