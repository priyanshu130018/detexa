import React from 'react';
import { RiskLevel } from '../../types';

interface RiskBadgeProps {
  level?: RiskLevel | string;
  className?: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level = 'Low', className = '' }) => {
  const normalized = (level || 'Low').toLowerCase();

  let colors = 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-500/30';
  let dotColor = 'bg-blue-600 dark:bg-blue-400';

  if (normalized === 'critical' || normalized === 'high') {
    colors = 'bg-red-600/15 text-red-600 dark:text-red-400 border-red-500/40';
    dotColor = 'bg-red-600 dark:bg-red-400';
  } else if (normalized === 'medium') {
    colors = 'bg-blue-600/20 text-blue-700 dark:text-blue-300 border-blue-500/40';
    dotColor = 'bg-blue-600 dark:bg-blue-400';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colors} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} animate-pulse`} />
      {level}
    </span>
  );
};
