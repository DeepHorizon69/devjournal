import React from 'react';
import { clsx } from 'clsx';
import { ArrowUpRight } from 'lucide-react';
import { Card } from './Card';
import { Skeleton } from './Skeleton';

export interface StatCardProps {
  label: string;
  count: number;
  icon?: React.ReactNode;
  indicatorColor?: 'accent' | 'success' | 'warning' | 'neutral';
  loading?: boolean;
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  count,
  icon,
  indicatorColor = 'neutral',
  loading = false,
  onClick,
}) => {
  const dotColors = {
    neutral: 'bg-text-secondary',
    accent: 'bg-accent',
    success: 'bg-status-success',
    warning: 'bg-status-warning',
  };

  return (
    <Card
      interactive={Boolean(onClick)}
      padding="sm"
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
      className="group flex flex-col justify-between gap-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dotColors[indicatorColor])} />
          <span className="text-xs font-medium text-text-secondary truncate">{label}</span>
        </div>
        {icon ? (
          <span className="text-text-muted group-hover:text-text-secondary transition-colors">
            {icon}
          </span>
        ) : (
          onClick && (
            <ArrowUpRight
              size={14}
              className="text-text-muted opacity-0 group-hover:opacity-100 group-hover:text-accent transition-all shrink-0"
            />
          )
        )}
      </div>

      <div className="flex items-baseline justify-between pt-0.5">
        {loading ? (
          <Skeleton className="h-6 w-12" />
        ) : (
          <span className="text-xl font-semibold font-mono text-text-primary tracking-tight">
            {count}
          </span>
        )}
      </div>
    </Card>
  );
};
