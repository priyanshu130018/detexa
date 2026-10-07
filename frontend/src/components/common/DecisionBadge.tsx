import React from 'react';
import { DecisionAction } from '../../types';
import { CheckCircle2, AlertTriangle, Eye, ShieldAlert, ShieldCheck } from 'lucide-react';

interface DecisionBadgeProps {
  decision?: DecisionAction | string;
  className?: string;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const DecisionBadge: React.FC<DecisionBadgeProps> = ({
  decision = 'ALLOW',
  className = '',
  showIcon = true,
  size = 'md',
}) => {
  const norm = (decision || 'ALLOW').toUpperCase();

  let colors = 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-500/30';
  let Icon = ShieldCheck;
  let label = 'ALLOW';

  if (norm === 'BLOCK') {
    colors = 'bg-red-600/20 text-red-600 dark:text-red-400 border-red-500/50 font-extrabold';
    Icon = ShieldAlert;
    label = 'BLOCK';
  } else if (norm === 'REVIEW') {
    colors = 'bg-red-600/10 text-red-600 dark:text-red-400 border-red-500/40';
    Icon = Eye;
    label = 'REVIEW';
  } else if (norm === 'CHALLENGE') {
    colors = 'bg-blue-600/20 text-blue-700 dark:text-blue-300 border-blue-500/40';
    Icon = AlertTriangle;
    label = 'CHALLENGE';
  } else if (norm === 'ALLOW') {
    colors = 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-500/30';
    Icon = CheckCircle2;
    label = 'ALLOW';
  }

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[10px] gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3.5 py-1.5 text-sm gap-2 font-bold',
  }[size];

  return (
    <span
      className={`inline-flex items-center font-bold tracking-wide uppercase rounded-lg border shadow-sm ${sizeClasses} ${colors} ${className}`}
    >
      {showIcon && <Icon className={size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
      <span>{label}</span>
    </span>
  );
};
