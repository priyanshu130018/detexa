import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock, Mail, ArrowRight, AlertCircle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    const t0 = performance.now();
    try {
      setError(null);
      setLoading(true);
      await login(email, password);
      const apiDuration = performance.now() - t0;
      console.log(`[Performance] Login API response time: ${apiDuration.toFixed(2)}ms`);

      const tNav = performance.now();
      navigate('/dashboard');
      const navDuration = performance.now() - tNav;
      console.log(`[Performance] Frontend navigation time: ${navDuration.toFixed(2)}ms`);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        (err.code === 'ERR_NETWORK' || !err.response
          ? 'Cannot connect to backend server. Please verify the API is running at http://localhost:8000.'
          : 'Invalid credentials. Please verify your email and password.');
      setError(msg);
      setLoading(false);
    }
  };

  const handleDemoFill = () => {
    setEmail('priyanshu@gmail.com');
    setPassword('Admin@1234');
    setError(null);
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-2xl bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 mb-2">
            <Shield className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-black dark:text-white tracking-tight">
            Sign in to Detexa
          </h2>
          <p className="text-sm text-black/60 dark:text-white/60">
            Access real-time fraud monitoring and ML anomaly telemetry
          </p>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-red-600/15 border border-red-500/30 text-red-600 dark:text-red-400 text-sm flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600 dark:text-red-400" />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 sm:p-8 shadow-xl transition-colors">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="priyanshu@gmail.com"
                  className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-10 pr-4 py-2.5 text-sm text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Password
              </label>
              <div className="relative">
                <Lock className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-10 pr-4 py-2.5 text-sm text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none transition flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 disabled:opacity-50"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Demo Login Shortcut */}
          <div className="mt-6 pt-6 border-t border-black/10 dark:border-white/10 text-center">
            <button
              type="button"
              onClick={handleDemoFill}
              className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/30 rounded-lg px-3 py-1.5 transition"
            >
              Click here to fill Demo Admin credentials
            </button>
          </div>
        </div>

        <div className="text-center text-xs text-black/60 dark:text-white/60">
          Don't have an account?{' '}
          <Link to="/register" className="text-blue-600 dark:text-blue-400 hover:underline font-semibold">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
};
