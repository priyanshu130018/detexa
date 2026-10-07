import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock, Mail, User, Phone, ArrowRight, AlertCircle } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password || !confirmPassword) {
      setError('Please fill in all required fields.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    try {
      setError(null);
      setLoading(true);
      await register(name, email, mobile || undefined, password);
      navigate('/dashboard');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Registration failed. Email might already exist.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-2xl bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 mb-2">
            <Shield className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-black dark:text-white tracking-tight">
            Create Detexa Account
          </h2>
          <p className="text-sm text-black/60 dark:text-white/60">
            Join the enterprise fraud intelligence network
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
                Full Name *
              </label>
              <div className="relative">
                <User className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Security Analyst"
                  className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-10 pr-4 py-2.5 text-sm text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Email Address *
              </label>
              <div className="relative">
                <Mail className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@company.com"
                  className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-10 pr-4 py-2.5 text-sm text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Mobile Number (Optional)
              </label>
              <div className="relative">
                <Phone className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="tel"
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value)}
                  placeholder="+1 555 019 2834"
                  className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-10 pr-4 py-2.5 text-sm text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Password * (min 8 chars)
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

            <div>
              <label className="block text-xs font-semibold text-black/80 dark:text-white/80 uppercase tracking-wider mb-2">
                Confirm Password *
              </label>
              <div className="relative">
                <Lock className="w-5 h-5 absolute left-3 top-3 text-black/40 dark:text-white/40" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
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
                  <span>Create Account</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        <div className="text-center text-xs text-black/60 dark:text-white/60">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-600 dark:text-blue-400 hover:underline font-semibold">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
};
