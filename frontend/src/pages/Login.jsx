import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Loader2, Eye, EyeOff, Mail, Lock, ArrowRight, ShieldCheck,
  UsersRound, Target, TrendingUp
} from 'lucide-react';
import { toast } from 'sonner';
import { MeshoraMark, MeshoraLogoOnDark } from '../components/MeshoraLogo';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
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
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* ============ Left Panel ============ */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Layered gradient background */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse at top left, #312E81 0%, #1E1B4B 35%, #0F172A 100%)',
          }}
        />
        {/* Constellation / mesh dots overlay */}
        <svg className="absolute inset-0 w-full h-full opacity-30" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <radialGradient id="dot" cx="50%" cy="50%" r="50%">
              <stop offset="0" stopColor="#A78BFA" />
              <stop offset="1" stopColor="#A78BFA" stopOpacity="0" />
            </radialGradient>
            <pattern id="constellation" x="0" y="0" width="80" height="80" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="1.5" fill="url(#dot)" />
              <circle cx="50" cy="40" r="1" fill="url(#dot)" />
              <circle cx="20" cy="60" r="1.3" fill="url(#dot)" />
              <line x1="10" y1="10" x2="50" y2="40" stroke="#A78BFA" strokeWidth="0.3" opacity="0.4" />
              <line x1="50" y1="40" x2="20" y2="60" stroke="#A78BFA" strokeWidth="0.3" opacity="0.4" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#constellation)" />
        </svg>
        {/* Soft purple glow blobs */}
        <div className="absolute -bottom-32 -right-32 w-[600px] h-[600px] rounded-full blur-3xl opacity-30" style={{ background: 'radial-gradient(circle, #A855F7 0%, transparent 70%)' }} />
        <div className="absolute top-1/3 -left-32 w-[400px] h-[400px] rounded-full blur-3xl opacity-25" style={{ background: 'radial-gradient(circle, #6366F1 0%, transparent 70%)' }} />

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16 text-white w-full">
          {/* Top: Logo */}
          <div>
            <MeshoraLogoOnDark size={48} />
          </div>

          {/* Middle: Tagline */}
          <div className="space-y-6 max-w-xl">
            <h1 className="text-5xl xl:text-6xl font-bold leading-[1.05] tracking-tight">
              <span className="block">Connect.</span>
              <span className="block">Collaborate.</span>
              <span className="block" style={{
                background: 'linear-gradient(90deg, #C4B5FD 0%, #A78BFA 50%, #818CF8 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                Grow Together.
              </span>
            </h1>
            <p className="text-base xl:text-lg text-white/70 max-w-md leading-relaxed">
              The trusted CRM platform for managing your business relationships, leads, and commissions.
            </p>
          </div>

          {/* Bottom: Feature cards + copyright */}
          <div className="space-y-8">
            <div className="grid grid-cols-3 gap-3 max-w-xl">
              <FeatureChip icon={UsersRound} title="Stronger Connections" body="Build meaningful relationships." />
              <FeatureChip icon={Target} title="More Opportunities" body="Track leads and grow your pipeline." />
              <FeatureChip icon={TrendingUp} title="Better Results" body="Close deals and maximize commissions." />
            </div>
            <div className="text-xs text-white/40">
              © {new Date().getFullYear()} Meshora. All rights reserved.
            </div>
          </div>
        </div>
      </div>

      {/* ============ Right Panel — Form ============ */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 lg:p-12">
        <div className="w-full max-w-md space-y-5 animate-fade-in">
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
              <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Welcome back</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">Sign in to access your Meshora account</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
              {error && (
                <Alert variant="destructive" className="animate-scale-in">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Email */}
              <div className="space-y-1.5">
                <label htmlFor="email" className="text-sm font-medium text-slate-700 dark:text-slate-300">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                    autoComplete="email"
                    data-testid="login-email-input"
                    className="h-11 pl-10 bg-slate-50/60 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 focus-visible:ring-violet-500"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium text-slate-700 dark:text-slate-300">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading}
                    autoComplete="current-password"
                    data-testid="login-password-input"
                    className="h-11 pl-10 pr-10 bg-slate-50/60 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 focus-visible:ring-violet-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                    data-testid="toggle-password-btn"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Remember + Forgot */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="w-4 h-4 accent-violet-600 rounded"
                    data-testid="remember-me-checkbox"
                  />
                  <span className="text-sm text-slate-600 dark:text-slate-300">Remember me</span>
                </label>
                <Link to="/forgot-password" className="text-sm font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400">
                  Forgot password?
                </Link>
              </div>

              {/* Submit */}
              <Button
                type="submit"
                disabled={loading}
                data-testid="login-submit-btn"
                className="w-full h-12 text-base font-semibold shadow-lg group"
                style={{
                  background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%)',
                  color: 'white',
                }}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <span className="flex items-center justify-center w-full">
                    Sign in
                    <ArrowRight className="ml-2 w-5 h-5 transition-transform group-hover:translate-x-1" />
                  </span>
                )}
              </Button>
            </form>

            {/* Divider */}
            <div className="relative my-5">
              <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-slate-200 dark:border-slate-700" /></div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-slate-900 px-3 text-slate-400">or</span>
              </div>
            </div>

            {/* Google (placeholder — unimplemented) */}
            <Button
              type="button"
              variant="outline"
              disabled
              title="Google sign-in not yet enabled"
              className="w-full h-11 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
              data-testid="google-signin-btn"
            >
              <svg className="w-5 h-5 mr-2" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3l5.7-5.7C33.9 5.8 29.2 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.8 1.1 8 3l5.7-5.7C33.9 5.8 29.2 4 24 4 16.3 4 9.6 8.3 6.3 14.7z" />
                <path fill="#4CAF50" d="M24 44c5.1 0 9.8-1.9 13.3-5.1l-6.1-5c-2 1.4-4.5 2.1-7.2 2.1-5.2 0-9.7-3.4-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
                <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.1 5C40.6 35.8 44 30.4 44 24c0-1.3-.1-2.4-.4-3.5z" />
              </svg>
              Sign in with Google
            </Button>

            {/* Create account */}
            <div className="mt-6 text-center text-sm">
              <span className="text-slate-500 dark:text-slate-400">Don't have an account? </span>
              <Link to="/register" className="font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400" data-testid="register-link">
                Create account
              </Link>
            </div>
          </div>

          {/* Security card */}
          <div className="bg-white/60 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-800 rounded-xl p-4 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-violet-50 dark:bg-violet-950/40">
              <ShieldCheck className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">Secure. Reliable. Always.</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Your data is protected with enterprise-grade security and privacy.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const FeatureChip = ({ icon: Icon, title, body }) => (
  <div className="rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 p-4 hover:bg-white/[0.07] transition-colors">
    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-500/30 to-indigo-500/30 flex items-center justify-center mb-3">
      <Icon className="w-4 h-4 text-violet-200" />
    </div>
    <div className="text-sm font-semibold text-white mb-1">{title}</div>
    <div className="text-xs text-white/60 leading-relaxed">{body}</div>
  </div>
);

export default Login;
