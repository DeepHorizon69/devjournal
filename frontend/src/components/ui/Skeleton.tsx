import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className, ...props }) => {
  return (
    <div
      aria-hidden="true"
      className={twMerge(
        clsx('animate-pulse rounded bg-canvas-elevated/70 border border-canvas-border/40', className)
      )}
      {...props}
    />
  );
};
