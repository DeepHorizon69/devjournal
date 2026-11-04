import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, Trash2, Sliders, HardDrive } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';

export const SettingsPage: React.FC = () => {
  const { data: health, isLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
  });

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">Settings & Storage Diagnostics</h1>
        <p className="text-sm text-text-secondary mt-1">
          Inspect storage status, manage persistent data, and configure local vault settings.
        </p>
      </div>

      {/* Storage Diagnostics */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <HardDrive size={18} className="text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Vault Diagnostics</h2>
          </div>
          <Badge variant={health?.status === 'ok' ? 'success' : 'warning'}>
            {isLoading ? 'Checking...' : health?.status === 'ok' ? 'Online' : 'Degraded'}
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-text-muted block mb-1">Data Directory (Host Mount)</span>
            <span className="font-mono text-text-primary bg-canvas-app px-2 py-1 rounded border border-canvas-border block truncate">
              {health?.data_dir || 'Loading...'}
            </span>
          </div>
          <div>
            <span className="text-text-muted block mb-1">Indexed Active Notes</span>
            <span className="font-mono text-text-primary bg-canvas-app px-2 py-1 rounded border border-canvas-border block">
              {health?.indexed_notes ?? 0} notes
            </span>
          </div>
          <div>
            <span className="text-text-muted block mb-1">Vault Filesystem Status</span>
            <span className="text-text-secondary block">
              {health?.vault_writable ? 'Writable (healthy)' : 'Read-only / Error'}
            </span>
          </div>
          <div>
            <span className="text-text-muted block mb-1">SQLite WAL Database</span>
            <span className="text-text-secondary block">
              {health?.db_ok ? 'Accessible (healthy)' : 'Error'}
            </span>
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between border-t border-canvas-border/40">
          <div className="text-xs text-text-secondary">
            Rebuilds SQLite metadata and FTS5 full-text search index from the Markdown files on disk.
          </div>
          <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />}>
            Rebuild Index
          </Button>
        </div>
      </div>

      {/* Trash Management */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <Trash2 size={18} className="text-amber-400" />
            <h2 className="text-sm font-semibold text-text-primary">Trash Management</h2>
          </div>
          <Badge variant="default">0 items</Badge>
        </div>
        <p className="text-xs text-text-secondary leading-relaxed">
          Notes deleted in DevJournal are soft-deleted into <code className="text-text-primary">vault/99-Trash/</code> with original path metadata preserved. Emptying trash will permanently unlink the files.
        </p>
        <div className="py-6 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded">
          Trash is currently empty.
        </div>
      </div>

      {/* Editor Preferences */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-canvas-border/60">
          <Sliders size={18} className="text-indigo-400" />
          <h2 className="text-sm font-semibold text-text-primary">Editor & Writing Preferences</h2>
        </div>
        <div className="space-y-3 text-xs text-text-secondary">
          <div className="flex items-center justify-between">
            <span>Default View Mode</span>
            <span className="font-medium text-text-primary">Split View (Editor + Preview)</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Autosave Delay</span>
            <span className="font-mono text-text-primary">1000ms (Debounced)</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Editor Typography</span>
            <span className="font-medium text-text-primary">JetBrains Mono / Inter</span>
          </div>
        </div>
      </div>
    </div>
  );
};
