import React from 'react';
import { clsx } from 'clsx';
import { Pin } from 'lucide-react';
import { NoteSummary, NoteStatus, NoteType } from '../../types';
import { Badge } from '../ui/Badge';
import { IconButton } from '../ui/IconButton';

export interface NoteRowProps {
  note: NoteSummary;
  onSelect: (noteId: string) => void;
  onTogglePin?: (note: NoteSummary, e: React.MouseEvent) => void;
  compact?: boolean;
}

const typeLabelMap: Record<NoteType, string> = {
  note: 'Note',
  experiment: 'Experiment',
  troubleshooting: 'Troubleshooting',
  project: 'Project',
  daily: 'Daily',
  snippet: 'Snippet',
};

const statusVariantMap: Record<
  NoteStatus,
  'default' | 'accent' | 'success' | 'warning' | 'danger' | 'muted'
> = {
  draft: 'muted',
  active: 'accent',
  investigating: 'warning',
  resolved: 'success',
  completed: 'success',
  archived: 'muted',
};

export function formatRelativeDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return isoDate;
  }
}

export const NoteRow: React.FC<NoteRowProps> = ({
  note,
  onSelect,
  onTogglePin,
  compact = false,
}) => {
  const isPinned = note.is_pinned;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(note.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(note.id);
        }
      }}
      className={clsx(
        'group flex items-start justify-between gap-4 border-b border-canvas-border/70 last:border-b-0 bg-canvas-surface/40 hover:bg-canvas-elevated/70 transition-colors duration-fast cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/60',
        compact ? 'px-3.5 py-2.5' : 'px-4 py-3'
      )}
    >
      {/* Left: Pin + Title + Excerpt + Metadata */}
      <div className="flex items-start gap-2.5 min-w-0 flex-1">
        {onTogglePin ? (
          <div
            className="mt-0.5 shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              onTogglePin(note, e);
            }}
          >
            <IconButton
              label={isPinned ? 'Unpin note' : 'Pin note'}
              size="xs"
              variant={isPinned ? 'active' : 'ghost'}
              className={clsx(
                !isPinned && 'opacity-40 group-hover:opacity-100'
              )}
              icon={<Pin size={12} />}
            />
          </div>
        ) : (
          isPinned && (
            <Pin size={13} className="text-accent mt-1 shrink-0" aria-label="Pinned" />
          )
        )}

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2 min-w-0">
            <h3 className="text-[13px] font-semibold text-text-primary group-hover:text-accent transition-colors truncate">
              {note.title}
            </h3>
            <span className="text-[11px] font-medium text-text-muted shrink-0">
              {typeLabelMap[note.note_type] || note.note_type}
            </span>
            {note.status && (
              <Badge
                variant={statusVariantMap[note.status] || 'default'}
                size="sm"
                dot
              >
                {note.status}
              </Badge>
            )}
          </div>

          {!compact && note.excerpt && (
            <p className="text-xs text-text-secondary line-clamp-1 leading-relaxed">
              {note.excerpt}
            </p>
          )}

          {/* Domains & Tags restrained inline metadata */}
          {(note.domains.length > 0 || note.tags.length > 0) && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              {note.domains.map((domain) => (
                <span
                  key={domain}
                  className="text-[11px] text-text-secondary bg-canvas-app/80 border border-canvas-border px-1.5 py-0.5 rounded leading-none"
                >
                  {domain}
                </span>
              ))}
              {note.tags.slice(0, 4).map((tag) => (
                <span
                  key={tag}
                  className="text-[11px] font-mono text-text-muted"
                >
                  #{tag}
                </span>
              ))}
              {note.tags.length > 4 && (
                <span className="text-[10px] text-text-muted">
                  +{note.tags.length - 4}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right: Timestamp */}
      <div className="flex flex-col items-end justify-between shrink-0 text-[11px] text-text-muted font-mono pt-0.5">
        <span>{formatRelativeDate(note.updated_at)}</span>
      </div>
    </div>
  );
};
