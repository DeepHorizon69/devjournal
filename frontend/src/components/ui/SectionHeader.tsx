import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  icon,
  action,
  className,
}) => {
  return (
    <div
      className={twMerge(
        clsx('flex items-center justify-between gap-4', className)
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {icon && <span className="text-text-muted shrink-0">{icon}</span>}
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary tracking-tight truncate">
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-text-secondary truncate mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0 flex items-center gap-2">{action}</div>}
    </div>
  );
};
