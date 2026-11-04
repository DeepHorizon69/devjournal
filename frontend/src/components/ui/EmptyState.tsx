import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Button } from './Button';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  compact?: boolean;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  compact = false,
  className,
}) => {
  return (
    <div
      className={twMerge(
        clsx(
          'flex flex-col items-center justify-center text-center mx-auto max-w-md',
          compact ? 'py-5 px-4' : 'py-10 px-4',
          className
        )
      )}
    >
      {icon && (
        <div
          className={clsx(
            'rounded-lg bg-canvas-elevated/60 border border-canvas-border flex items-center justify-center text-text-muted shrink-0',
            compact ? 'w-8 h-8 mb-2' : 'w-10 h-10 mb-3'
          )}
        >
          {icon}
        </div>
      )}
      <h3
        className={clsx(
          'font-medium text-text-primary',
          compact ? 'text-xs' : 'text-sm'
        )}
      >
        {title}
      </h3>
      {description && (
        <p
          className={clsx(
            'text-text-secondary leading-relaxed',
            compact ? 'text-xs mt-1' : 'text-xs mt-1.5'
          )}
        >
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <div className={compact ? 'mt-3' : 'mt-4'}>
          <Button variant="secondary" size="xs" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  );
};
