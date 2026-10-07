import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  color?: 'blue' | 'red';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = 'blue',
}) => {
  const isRed = color === 'red';

  const iconClasses = isRed
    ? 'text-red-600 dark:text-red-400 bg-red-600/10 border-red-500/30'
    : 'text-blue-600 dark:text-blue-400 bg-blue-600/10 border-blue-500/30';

  return (
    <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 hover:border-black/20 dark:hover:border-white/20 transition-all rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider">
          {title}
        </span>
        <div className={`p-2.5 rounded-lg border ${iconClasses}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-3">
        <div className="text-2xl lg:text-3xl font-bold text-black dark:text-white tracking-tight">
          {value}
        </div>
        {(subtitle || trend) && (
          <div className="mt-1 flex items-center gap-2 text-xs text-black/60 dark:text-white/60">
            {trend && (
              <span
                className={`font-medium ${
                  trend.isPositive ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'
                }`}
              >
                {trend.value}
              </span>
            )}
            {subtitle && <span>{subtitle}</span>}
          </div>
        )}
      </div>
    </div>
  );
};
