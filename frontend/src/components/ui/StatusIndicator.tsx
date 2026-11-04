import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Check, Loader2, AlertCircle, AlertTriangle } from 'lucide-react';

export type SaveState = 'saved' | 'unsaved' | 'saving' | 'failed' | 'conflict';

export interface StatusIndicatorProps {
  state: SaveState;
  className?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ state, className }) => {
  const configs: Record<
    SaveState,
    { label: string; colorClass: string; dotOrIcon: React.ReactNode }
  > = {
    saved: {
      label: 'Saved',
      colorClass: 'text-text-secondary bg-canvas-surface border-canvas-border',
      dotOrIcon: <Check size={12} className="text-status-success shrink-0" />,
    },
    unsaved: {
      label: 'Unsaved changes',
      colorClass: 'text-status-warning bg-status-warning/10 border-status-warning/25',
      dotOrIcon: <span className="w-1.5 h-1.5 rounded-full bg-status-warning shrink-0" />,
    },
    saving: {
      label: 'Saving...',
      colorClass: 'text-accent bg-accent/10 border-accent/25',
      dotOrIcon: <Loader2 size={12} className="text-accent animate-spin shrink-0" />,
    },
    failed: {
      label: 'Save failed',
      colorClass: 'text-status-danger bg-status-danger/10 border-status-danger/25',
      dotOrIcon: <AlertCircle size={12} className="text-status-danger shrink-0" />,
    },
    conflict: {
      label: 'Conflict with server',
      colorClass: 'text-status-danger bg-status-danger/15 border-status-danger/35 font-semibold',
      dotOrIcon: <AlertTriangle size={12} className="text-status-danger shrink-0" />,
    },
  };

  const cfg = configs[state];

  return (
    <span
      role="status"
      aria-live="polite"
      className={twMerge(
        clsx(
          'inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs select-none transition-colors duration-fast',
          cfg.colorClass,
          className
        )
      )}
    >
      {cfg.dotOrIcon}
      <span>{cfg.label}</span>
    </span>
  );
};
