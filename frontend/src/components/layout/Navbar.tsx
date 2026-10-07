import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { useRealtime } from '../../context/RealtimeContext';
import { Shield, Moon, Sun, LogOut, Menu, RefreshCw, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

interface NavbarProps {
  onToggleSidebar?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar }) => {
  const { user, logout, isAuthenticated } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const { connectionState, reconnectAttempts, reconnect } = useRealtime();

  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-black/95 border-b border-black/10 dark:border-white/10 backdrop-blur-md px-4 lg:px-8 py-3 transition-colors duration-150">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isAuthenticated && (
            <button
              onClick={onToggleSidebar}
              className="lg:hidden p-2 rounded-lg text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10 transition"
              aria-label="Toggle navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          <Link to="/" className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-600/10 dark:bg-blue-600/20 border border-blue-500/30 text-blue-600 dark:text-blue-400">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xl font-extrabold text-black dark:text-white tracking-tight">
                Detexa
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-widest bg-blue-600/10 dark:bg-blue-600/20 px-2 py-0.5 rounded border border-blue-500/30">
                AI Defense
              </span>
            </div>
          </Link>
        </div>

        {/* Center: Live Stream Connection Status (When Logged in) */}
        {isAuthenticated && (
          <div className="hidden md:flex items-center gap-2">
            {connectionState === 'connected' && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 animate-pulse" />
                <span>Live Stream: Connected</span>
              </span>
            )}
            {connectionState === 'connecting' && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30">
                <RefreshCw className="w-3 h-3 animate-spin text-blue-600 dark:text-blue-400" />
                <span>Connecting Stream...</span>
              </span>
            )}
            {connectionState === 'reconnecting' && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 animate-pulse">
                <RefreshCw className="w-3 h-3 animate-spin text-blue-600 dark:text-blue-400" />
                <span>Reconnecting (Attempt {reconnectAttempts})...</span>
              </span>
            )}
            {(connectionState === 'disconnected' || connectionState === 'unavailable') && (
              <button
                onClick={reconnect}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-600/10 text-red-600 dark:text-red-400 border border-red-500/30 hover:bg-red-600/20 transition cursor-pointer"
                title="Click to reconnect stream"
              >
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Stream Offline (Reconnect)</span>
              </button>
            )}
          </div>
        )}

        <div className="flex items-center gap-3">
          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10 transition"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            aria-label="Toggle theme mode"
          >
            {isDark ? (
              <Sun className="w-5 h-5 text-white transition-transform duration-200 rotate-0 hover:rotate-45" />
            ) : (
              <Moon className="w-5 h-5 text-black transition-transform duration-200 rotate-0 hover:-rotate-12" />
            )}
          </button>

          {isAuthenticated && user ? (
            <div className="flex items-center gap-3 pl-3 border-l border-black/10 dark:border-white/10">
              <div className="hidden sm:block text-right">
                <div className="text-sm font-semibold text-black dark:text-white">{user.name}</div>
                <div className="text-xs text-black/60 dark:text-white/60">{user.email}</div>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 bg-red-600/10 hover:bg-red-600/20 border border-red-500/30 transition"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden md:inline">Sign Out</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="px-4 py-1.5 text-sm font-medium text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white transition"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="px-4 py-1.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-md transition"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
