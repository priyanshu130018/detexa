import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ElementType;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description = 'There are currently no items matching your criteria.',
  icon: Icon = Inbox,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-2xl border border-dashed border-black/20 dark:border-white/20 bg-black/5 dark:bg-white/5 transition-colors">
      <div className="p-4 rounded-2xl bg-white dark:bg-black border border-black/10 dark:border-white/10 text-black/50 dark:text-white/50 mb-4 shadow-sm">
        <Icon className="w-8 h-8 stroke-[1.5]" />
      </div>
      <h3 className="text-base font-bold text-black dark:text-white">{title}</h3>
      <p className="text-xs sm:text-sm text-black/60 dark:text-white/60 mt-1 max-w-sm">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition shadow-md shadow-blue-600/20"
        >
          {action.label}
        </button>
      )}
    </div>
  );
};
