import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  CreditCard,
  Bell,
  SearchCode,
  Network,
  Cpu,
  UserCheck,
  X,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user } = useAuth();

  const primaryNavItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/transactions', label: 'Live Transactions', icon: CreditCard },
    { to: '/alerts', label: 'Security Alerts', icon: Bell },
    { to: '/investigation', label: 'Fraud Investigation', icon: SearchCode },
    { to: '/graph', label: 'Graph Investigation', icon: Network },
    { to: '/statistics', label: 'Model & Statistics', icon: Cpu },
  ];

  const secondaryNavItems = [
    { to: '/predict', label: 'Instant Inference', icon: Sparkles },
    { to: '/behavior', label: 'Behavior Analytics', icon: UserCheck },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white dark:bg-black border-r border-black/10 dark:border-white/10 flex flex-col transition-all duration-200 ease-in-out lg:translate-x-0 lg:static ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10 lg:hidden">
          <span className="text-lg font-bold text-black dark:text-white">Menu</span>
          <button
            onClick={onClose}
            className="p-1 rounded text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white"
            aria-label="Close sidebar menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Card */}
        <div className="p-4 m-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
          <div className="text-xs text-black/60 dark:text-white/60 font-medium">Logged in as</div>
          <div className="text-sm font-bold text-black dark:text-white truncate mt-0.5">
            {user?.name || 'Fraud Analyst'}
          </div>
          <div className="text-[11px] text-blue-600 dark:text-blue-400 font-mono truncate">
            {user?.email || 'analyst@detexa.internal'}
          </div>
          {user?.isAdmin && (
            <span className="inline-block mt-1 text-[10px] uppercase font-bold text-blue-600 dark:text-blue-400 bg-blue-600/10 dark:bg-blue-600/20 border border-blue-500/30 px-2 py-0.5 rounded">
              Administrator
            </span>
          )}
        </div>

        {/* Primary Nav links */}
        <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[11px] font-bold text-black/40 dark:text-white/40 uppercase tracking-wider">
            Core Fraud Defense
          </div>
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                      : 'text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          <div className="pt-4 px-3 pb-2 text-[11px] font-bold text-black/40 dark:text-white/40 uppercase tracking-wider">
            Advanced Tooling
          </div>
          {secondaryNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-blue-600/10 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/30'
                      : 'text-black/70 dark:text-white/70 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10'
                  }`
                }
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-black/10 dark:border-white/10 text-center">
          <div className="text-[11px] font-semibold text-black/70 dark:text-white/70">Detexa AI Defense Platform</div>
          <div className="text-[10px] text-black/40 dark:text-white/40 mt-0.5">
            XGBoost v3.0 & Decision Rules Engine
          </div>
        </div>
      </aside>
    </>
  );
};
