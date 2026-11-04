import React from 'react';
import { RotateCcw } from 'lucide-react';
import { KnowledgeDomain, NoteStatus, NoteType } from '../../types';
import { SearchInput } from '../ui/SearchInput';
import { Select } from '../ui/Select';
import { Button } from '../ui/Button';

export interface NoteFiltersState {
  search: string;
  type: NoteType | '';
  domain: KnowledgeDomain | '';
  status: NoteStatus | '';
  tag: string;
  folder: string;
  sort: 'updated_desc' | 'created_desc' | 'title_asc';
}

export interface FilterBarProps {
  filters: NoteFiltersState;
  onChange: (updated: Partial<NoteFiltersState>) => void;
  onReset: () => void;
  hideTypeFilter?: boolean;
  hideDomainFilter?: boolean;
  availableTags?: string[];
  availableFolders?: string[];
  totalCount?: number;
}

const DOMAIN_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Domains' },
  { value: 'Networking', label: 'Networking' },
  { value: 'Linux', label: 'Linux' },
  { value: 'Programming', label: 'Programming' },
  { value: 'IoT', label: 'IoT' },
  { value: 'Cybersecurity', label: 'Cybersecurity' },
  { value: 'Homelab', label: 'Homelab' },
  { value: 'Mathematics', label: 'Mathematics' },
];

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Types' },
  { value: 'note', label: 'General Note' },
  { value: 'experiment', label: 'Experiment' },
  { value: 'troubleshooting', label: 'Troubleshooting' },
  { value: 'project', label: 'Project' },
  { value: 'daily', label: 'Daily Journal' },
  { value: 'snippet', label: 'Snippet' },
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'investigating', label: 'Investigating' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
];

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'updated_desc', label: 'Sort: Updated (Newest)' },
  { value: 'created_desc', label: 'Sort: Created (Newest)' },
  { value: 'title_asc', label: 'Sort: Title (A–Z)' },
];

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  onChange,
  onReset,
  hideTypeFilter = false,
  hideDomainFilter = false,
  availableTags = [],
  availableFolders = [],
  totalCount,
}) => {
  const hasActiveFilters = Boolean(
    filters.search ||
      (!hideTypeFilter && filters.type) ||
      (!hideDomainFilter && filters.domain) ||
      filters.status ||
      filters.tag ||
      filters.folder
  );

  const tagOptions = [
    { value: '', label: 'All Tags' },
    ...availableTags.map((t) => ({ value: t, label: `#${t}` })),
  ];

  const folderOptions = [
    { value: '', label: 'All Folders' },
    ...availableFolders.map((f) => ({ value: f, label: f })),
  ];

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-canvas-surface/70 border border-canvas-border p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Left: Search + Compact Dropdowns */}
        <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[240px]">
          <div className="w-full sm:w-56">
            <SearchInput
              inputSize="sm"
              placeholder="Filter by title or keyword..."
              value={filters.search}
              onChange={(e) => onChange({ search: e.target.value })}
              onClear={() => onChange({ search: '' })}
            />
          </div>

          {!hideTypeFilter && (
            <Select
              aria-label="Filter by type"
              selectSize="sm"
              options={TYPE_OPTIONS}
              value={filters.type}
              onChange={(e) => onChange({ type: e.target.value as NoteType | '' })}
            />
          )}

          {!hideDomainFilter && (
            <Select
              aria-label="Filter by domain"
              selectSize="sm"
              options={DOMAIN_OPTIONS}
              value={filters.domain}
              onChange={(e) =>
                onChange({ domain: e.target.value as KnowledgeDomain | '' })
              }
            />
          )}

          <Select
            aria-label="Filter by status"
            selectSize="sm"
            options={STATUS_OPTIONS}
            value={filters.status}
            onChange={(e) => onChange({ status: e.target.value as NoteStatus | '' })}
          />

          {availableTags.length > 0 && (
            <Select
              aria-label="Filter by tag"
              selectSize="sm"
              options={tagOptions}
              value={filters.tag}
              onChange={(e) => onChange({ tag: e.target.value })}
            />
          )}

          {availableFolders.length > 0 && (
            <Select
              aria-label="Filter by folder"
              selectSize="sm"
              options={folderOptions}
              value={filters.folder}
              onChange={(e) => onChange({ folder: e.target.value })}
            />
          )}

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="xs"
              icon={<RotateCcw size={12} />}
              onClick={onReset}
            >
              Reset
            </Button>
          )}
        </div>

        {/* Right: Count + Sort */}
        <div className="flex items-center gap-3 shrink-0">
          {totalCount !== undefined && (
            <span className="text-xs text-text-muted font-mono">
              {totalCount} {totalCount === 1 ? 'note' : 'notes'}
            </span>
          )}
          <Select
            aria-label="Sort order"
            selectSize="sm"
            options={SORT_OPTIONS}
            value={filters.sort}
            onChange={(e) =>
              onChange({
                sort: e.target.value as NoteFiltersState['sort'],
              })
            }
          />
        </div>
      </div>
    </div>
  );
};
