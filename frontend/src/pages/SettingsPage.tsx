import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw,
  Trash2,
  Sliders,
  HardDrive,
  Download,
  Upload,
  FileUp,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';
import { UpdateSettingsRequest } from '../types';

const VAULT_FOLDERS = [
  '00-Inbox',
  '10-Notes',
  '20-Projects',
  '30-Experiments',
  '40-Troubleshooting',
  '50-Snippets',
  '90-Daily',
];

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const [importFolder, setImportFolder] = useState<string>('00-Inbox');
  const restoreInputRef = useRef<HTMLInputElement | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);

  // Health query
  const { data: health, isLoading: isHealthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
  });

  // Trashed notes query
  const { data: trashedData, isLoading: isTrashLoading } = useQuery({
    queryKey: ['notes', { trashed: true }],
    queryFn: () => api.listNotes({ trashed: true, limit: 200 }),
  });
  const trashedNotes = trashedData?.notes ?? [];

  // Editor settings query
  const { data: serverSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: api.getSettings,
  });

  const [localSettings, setLocalSettings] = useState<UpdateSettingsRequest>({
    default_editor_mode: 'split',
    autosave_delay_ms: 1000,
    editor_font_size: 14,
    editor_word_wrap: true,
  });

  useEffect(() => {
    if (serverSettings) {
      setLocalSettings({
        default_editor_mode: serverSettings.default_editor_mode,
        autosave_delay_ms: serverSettings.autosave_delay_ms,
        editor_font_size: serverSettings.editor_font_size,
        editor_word_wrap: serverSettings.editor_word_wrap,
      });
    }
  }, [serverSettings]);

  // Mutations
  const reindexMutation = useMutation({
    mutationFn: api.reindex,
    onSuccess: (res) => {
      queryClient.invalidateQueries();
      setStatusMessage({
        type: 'success',
        text: `Index rebuilt in ${res.duration_ms}ms (${res.indexed} indexed, ${res.updated ?? 0} updated, ${res.unchanged ?? 0} unchanged).`,
      });
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const backupMutation = useMutation({
    mutationFn: api.createBackup,
    onSuccess: (res) => {
      setStatusMessage({
        type: 'success',
        text: `Backup created: ${res.filename} (${(res.size_bytes / 1024).toFixed(1)} KB). Downloading...`,
      });
      const link = document.createElement('a');
      link.href = api.getBackupDownloadUrl(res.filename);
      link.download = res.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (file: File) => api.restoreBackup(file),
    onSuccess: (res) => {
      queryClient.invalidateQueries();
      setStatusMessage({
        type: 'success',
        text: `Vault restored (${res.indexed} notes indexed). Pre-restore safety snapshot saved as ${res.safety_backup_filename}.`,
      });
      if (restoreInputRef.current) restoreInputRef.current.value = '';
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
      if (restoreInputRef.current) restoreInputRef.current.value = '';
    },
  });

  const importMutation = useMutation({
    mutationFn: ({ file, folder }: { file: File; folder: string }) =>
      api.importMarkdown(file, folder),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['taxonomy'] });
      setStatusMessage({
        type: 'success',
        text: `Imported "${note.title}" into ${note.folder}.`,
      });
      if (importInputRef.current) importInputRef.current.value = '';
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
      if (importInputRef.current) importInputRef.current.value = '';
    },
  });

  const restoreNoteMutation = useMutation({
    mutationFn: (noteId: string) => api.restoreNote(noteId),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
      setStatusMessage({
        type: 'success',
        text: `Restored "${note.title}" to ${note.folder}.`,
      });
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const deleteNotePermanentMutation = useMutation({
    mutationFn: (noteId: string) => api.deleteNote(noteId, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
      setStatusMessage({
        type: 'success',
        text: 'Note permanently deleted from Trash.',
      });
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const emptyTrashMutation = useMutation({
    mutationFn: api.emptyTrash,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
      setStatusMessage({
        type: 'success',
        text: `Emptied trash (${res.deleted_count} note(s) permanently removed).`,
      });
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const updateSettingsMutation = useMutation({
    mutationFn: (payload: UpdateSettingsRequest) => api.updateSettings(payload),
    onSuccess: (updated) => {
      setLocalSettings({
        default_editor_mode: updated.default_editor_mode,
        autosave_delay_ms: updated.autosave_delay_ms,
        editor_font_size: updated.editor_font_size,
        editor_word_wrap: updated.editor_word_wrap,
      });
      queryClient.setQueryData(['settings'], updated);
      setStatusMessage({
        type: 'success',
        text: 'Editor preferences saved.',
      });
    },
    onError: (err: Error) => {
      setStatusMessage({ type: 'error', text: err.message });
    },
  });

  const handleRestoreFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    restoreMutation.mutate(file);
  };

  const handleImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    importMutation.mutate({ file, folder: importFolder });
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          Settings & Storage Diagnostics
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Inspect storage status, manage backups and trash, and configure local editor preferences.
        </p>
      </div>

      {statusMessage && (
        <div
          className={`p-3.5 rounded-lg border flex items-center justify-between text-xs ${
            statusMessage.type === 'success'
              ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-200'
              : 'bg-rose-950/30 border-rose-800/60 text-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle size={15} className="text-rose-400 shrink-0" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-text-muted hover:text-text-primary ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Storage Diagnostics */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <HardDrive size={18} className="text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Vault Diagnostics</h2>
          </div>
          <Badge variant={health?.status === 'ok' ? 'success' : 'warning'}>
            {isHealthLoading
              ? 'Checking...'
              : health?.status === 'ok'
                ? 'Online'
                : health?.status === 'maintenance'
                  ? 'Maintenance'
                  : 'Degraded'}
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
              {health?.indexed_notes ?? 0} notes ({trashedNotes.length} in Trash)
            </span>
          </div>
          <div>
            <span className="text-text-muted block mb-1">Vault Filesystem Status</span>
            <span className="text-text-secondary block">
              {health?.vault_writable ? 'Writable (healthy)' : 'Read-only / Error'}
            </span>
          </div>
          <div>
            <span className="text-text-muted block mb-1">SQLite WAL + FTS5 Database</span>
            <span className="text-text-secondary block">
              {health?.db_ok ? 'Accessible (healthy)' : 'Error'}
            </span>
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between border-t border-canvas-border/40">
          <div className="text-xs text-text-secondary">
            Rebuilds SQLite metadata and FTS5 full-text search index from the Markdown files on disk.
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} className={reindexMutation.isPending ? 'animate-spin' : ''} />}
            disabled={reindexMutation.isPending}
            onClick={() => reindexMutation.mutate()}
          >
            {reindexMutation.isPending ? 'Rebuilding...' : 'Rebuild Index'}
          </Button>
        </div>
      </div>

      {/* Backup, Restore & Markdown Import */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <Download size={18} className="text-sky-400" />
            <h2 className="text-sm font-semibold text-text-primary">
              Backup, Restore & Markdown Import
            </h2>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {/* Full Backup */}
          <div className="p-3.5 rounded bg-canvas-app border border-canvas-border flex flex-col justify-between space-y-3">
            <div>
              <div className="font-semibold text-text-primary mb-1">Full Vault Backup</div>
              <p className="text-text-secondary leading-relaxed">
                Creates a verified ZIP snapshot of all vault Markdown files, SQLite database, and SHA-256 manifest.
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              icon={<Download size={14} />}
              disabled={backupMutation.isPending}
              onClick={() => backupMutation.mutate()}
            >
              {backupMutation.isPending ? 'Packaging...' : 'Create & Download Backup'}
            </Button>
          </div>

          {/* Restore Backup */}
          <div className="p-3.5 rounded bg-canvas-app border border-canvas-border flex flex-col justify-between space-y-3">
            <div>
              <div className="font-semibold text-text-primary mb-1">Restore Snapshot (.zip)</div>
              <p className="text-text-secondary leading-relaxed">
                Atomically creates a safety snapshot and restores the vault and settings from a backup archive.
              </p>
            </div>
            <div>
              <input
                ref={restoreInputRef}
                type="file"
                accept=".zip"
                onChange={handleRestoreFileChange}
                className="hidden"
                data-testid="restore-zip-input"
              />
              <Button
                variant="secondary"
                size="sm"
                icon={<Upload size={14} />}
                disabled={restoreMutation.isPending}
                onClick={() => restoreInputRef.current?.click()}
              >
                {restoreMutation.isPending ? 'Restoring...' : 'Restore from ZIP'}
              </Button>
            </div>
          </div>

          {/* Import Markdown */}
          <div className="p-3.5 rounded bg-canvas-app border border-canvas-border flex flex-col justify-between space-y-3">
            <div className="space-y-2">
              <div className="font-semibold text-text-primary">Import Markdown (.md)</div>
              <p className="text-text-secondary leading-relaxed">
                Import an existing Markdown file and normalize frontmatter into a vault folder.
              </p>
              <select
                value={importFolder}
                onChange={(e) => setImportFolder(e.target.value)}
                className="w-full px-2 py-1 text-xs rounded bg-canvas-surface border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
              >
                {VAULT_FOLDERS.map((folder) => (
                  <option key={folder} value={folder}>
                    {folder}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <input
                ref={importInputRef}
                type="file"
                accept=".md,.markdown"
                onChange={handleImportFileChange}
                className="hidden"
                data-testid="import-md-input"
              />
              <Button
                variant="secondary"
                size="sm"
                icon={<FileUp size={14} />}
                disabled={importMutation.isPending}
                onClick={() => importInputRef.current?.click()}
              >
                {importMutation.isPending ? 'Importing...' : 'Select .md File'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Trash Management */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <Trash2 size={18} className="text-amber-400" />
            <h2 className="text-sm font-semibold text-text-primary">Trash Management</h2>
            <Badge variant="default">{trashedNotes.length} items</Badge>
          </div>
          {trashedNotes.length > 0 && (
            <Button
              variant="danger"
              size="sm"
              icon={<Trash2 size={13} />}
              disabled={emptyTrashMutation.isPending}
              onClick={() => emptyTrashMutation.mutate()}
            >
              {emptyTrashMutation.isPending ? 'Emptying...' : 'Empty Trash'}
            </Button>
          )}
        </div>
        <p className="text-xs text-text-secondary leading-relaxed">
          Notes deleted in DevJournal are soft-deleted into{' '}
          <code className="text-text-primary">vault/99-Trash/</code> with original path metadata
          preserved.
        </p>

        {isTrashLoading ? (
          <div className="py-6 text-center text-xs text-text-muted">Loading trashed notes...</div>
        ) : trashedNotes.length === 0 ? (
          <div className="py-6 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded">
            Trash is currently empty.
          </div>
        ) : (
          <div className="divide-y divide-canvas-border border border-canvas-border rounded-md bg-canvas-app">
            {trashedNotes.map((note) => (
              <div
                key={note.id}
                className="p-3 flex items-center justify-between gap-4 text-xs"
              >
                <div className="min-w-0">
                  <button
                    onClick={() => navigate(`/notes/${note.id}`)}
                    className="font-medium text-text-primary hover:text-accent truncate block text-left"
                  >
                    {note.title}
                  </button>
                  <span className="text-[11px] font-mono text-text-muted">
                    {note.note_type} • Updated {new Date(note.updated_at).toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<RotateCcw size={13} />}
                    disabled={restoreNoteMutation.isPending}
                    onClick={() => restoreNoteMutation.mutate(note.id)}
                  >
                    Restore
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    icon={<Trash2 size={13} />}
                    disabled={deleteNotePermanentMutation.isPending}
                    onClick={() => deleteNotePermanentMutation.mutate(note.id)}
                  >
                    Delete Permanently
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Editor Preferences */}
      <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-canvas-border/60">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-indigo-400" />
            <h2 className="text-sm font-semibold text-text-primary">
              Editor & Writing Preferences
            </h2>
          </div>
          <Button
            variant="primary"
            size="sm"
            disabled={updateSettingsMutation.isPending}
            onClick={() => updateSettingsMutation.mutate(localSettings)}
          >
            {updateSettingsMutation.isPending ? 'Saving...' : 'Save Preferences'}
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-text-secondary block mb-1 font-medium">
              Default Editor View Mode
            </label>
            <select
              value={localSettings.default_editor_mode}
              onChange={(e) =>
                setLocalSettings((prev) => ({
                  ...prev,
                  default_editor_mode: e.target.value as UpdateSettingsRequest['default_editor_mode'],
                }))
              }
              className="w-full px-2.5 py-1.5 rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
            >
              <option value="split">Split View (Editor + Preview)</option>
              <option value="raw">Raw Markdown Only</option>
              <option value="preview">Rendered Preview Only</option>
            </select>
          </div>

          <div>
            <label className="text-text-secondary block mb-1 font-medium">
              Autosave Delay (300ms – 10000ms)
            </label>
            <input
              type="number"
              min={300}
              max={10000}
              step={100}
              value={localSettings.autosave_delay_ms}
              onChange={(e) =>
                setLocalSettings((prev) => ({
                  ...prev,
                  autosave_delay_ms: Math.min(10000, Math.max(300, Number(e.target.value) || 1000)),
                }))
              }
              className="w-full px-2.5 py-1.5 font-mono rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
            />
          </div>

          <div>
            <label className="text-text-secondary block mb-1 font-medium">
              Editor Font Size (11px – 22px)
            </label>
            <input
              type="number"
              min={11}
              max={22}
              value={localSettings.editor_font_size}
              onChange={(e) =>
                setLocalSettings((prev) => ({
                  ...prev,
                  editor_font_size: Math.min(22, Math.max(11, Number(e.target.value) || 14)),
                }))
              }
              className="w-full px-2.5 py-1.5 font-mono rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
            />
          </div>

          <div className="flex items-center justify-between pt-5">
            <span className="text-text-secondary font-medium">Editor Line Wrapping</span>
            <input
              type="checkbox"
              checked={localSettings.editor_word_wrap}
              onChange={(e) =>
                setLocalSettings((prev) => ({
                  ...prev,
                  editor_word_wrap: e.target.checked,
                }))
              }
              className="rounded border-canvas-border bg-canvas-app text-accent focus:ring-accent"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
