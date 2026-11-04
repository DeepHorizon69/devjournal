import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Save,
  Split,
  Eye,
  Edit3,
  Pin,
  Download,
  Trash2,
  RotateCcw,
  AlertTriangle,
  X,
  Plus,
} from 'lucide-react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import { EditorState, Compartment } from '@codemirror/state';
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  drawSelection,
} from '@codemirror/view';
import { markdown } from '@codemirror/lang-markdown';
import { languages } from '@codemirror/language-data';
import { oneDark } from '@codemirror/theme-one-dark';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useUIStore } from '../store/useUIStore';
import { api, ApiError } from '../api/client';
import {
  KnowledgeDomain,
  NoteDetail,
  NoteStatus,
  NoteType,
  UpdateNoteRequest,
} from '../types';
import {
  saveLocalDraft,
  loadLocalDraft,
  removeLocalDraft,
  LocalDraftRecord,
} from '../utils/draftStorage';

const NOTE_TYPES: NoteType[] = [
  'note',
  'project',
  'experiment',
  'troubleshooting',
  'snippet',
  'daily',
];

const NOTE_STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'None (No Status)' },
  { value: 'draft', label: 'draft' },
  { value: 'active', label: 'active' },
  { value: 'investigating', label: 'investigating' },
  { value: 'resolved', label: 'resolved' },
  { value: 'completed', label: 'completed' },
  { value: 'archived', label: 'archived' },
];

const VAULT_FOLDERS = [
  '00-Inbox',
  '10-Notes',
  '20-Projects',
  '30-Experiments',
  '40-Troubleshooting',
  '50-Snippets',
  '90-Daily',
];

const ALL_DOMAINS: KnowledgeDomain[] = [
  'Networking',
  'Linux',
  'Programming',
  'IoT',
  'Cybersecurity',
  'Homelab',
  'Mathematics',
];

type SaveState = 'saved' | 'unsaved' | 'saving' | 'conflict' | 'error';

export const NoteEditorPage: React.FC = () => {
  const { noteId } = useParams<{ noteId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { editorViewMode, setEditorViewMode } = useUIStore();

  // Fetch note details
  const {
    data: serverNote,
    isLoading,
    error: loadError,
    refetch: refetchNote,
  } = useQuery({
    queryKey: ['note', noteId],
    queryFn: () => api.getNote(noteId!),
    enabled: Boolean(noteId),
  });

  // Fetch editor settings
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: api.getSettings,
  });

  // Local mutable draft state
  const [title, setTitle] = useState<string>('');
  const [noteType, setNoteType] = useState<NoteType>('note');
  const [status, setStatus] = useState<NoteStatus | null>(null);
  const [folder, setFolder] = useState<string>('10-Notes');
  const [domains, setDomains] = useState<KnowledgeDomain[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState<string>('');
  const [pinned, setPinned] = useState<boolean>(false);
  const [bodyMarkdown, setBodyMarkdown] = useState<string>('');
  const [debouncedPreviewMarkdown, setDebouncedPreviewMarkdown] = useState<string>('');
  const [expectedHash, setExpectedHash] = useState<string>('');

  const [saveState, setSaveState] = useState<SaveState>('saved');
  const [saveErrorText, setSaveErrorText] = useState<string | null>(null);
  const [quotaWarning, setQuotaWarning] = useState<string | null>(null);
  const [restoredLocalBanner, setRestoredLocalBanner] = useState<boolean>(false);

  // Refs for single-flight autosave & CodeMirror lifecycle
  const draftRevisionRef = useRef<number>(0);
  const savedRevisionRef = useRef<number>(0);
  const saveInFlightRef = useRef<boolean>(false);
  const pendingSaveAfterFlightRef = useRef<boolean>(false);
  const initializedNoteIdRef = useRef<string | null>(null);

  const editorContainerRef = useRef<HTMLDivElement | null>(null);
  const editorViewRef = useRef<EditorView | null>(null);
  const wrapCompartmentRef = useRef(new Compartment());
  const fontSizeCompartmentRef = useRef(new Compartment());
  const readOnlyCompartmentRef = useRef(new Compartment());

  // Latest draft snapshot ref for unmount/flush and single-flight callbacks
  const latestDraftRef = useRef<{
    noteId: string;
    title: string;
    note_type: NoteType;
    status: NoteStatus | null;
    folder: string;
    domains: KnowledgeDomain[];
    tags: string[];
    is_pinned: boolean;
    body: string;
    expected_hash: string;
    is_trashed: boolean;
  } | null>(null);

  // Apply default editor view mode from settings on initial mount
  useEffect(() => {
    if (settings?.default_editor_mode) {
      const mapped =
        settings.default_editor_mode === 'raw' ? 'edit' : settings.default_editor_mode;
      setEditorViewMode(mapped);
    }
  }, [settings?.default_editor_mode, setEditorViewMode]);

  // Initialize local state from serverNote (and check local unsaved draft recovery)
  useEffect(() => {
    if (!serverNote || !noteId) return;
    if (initializedNoteIdRef.current === noteId) return;

    initializedNoteIdRef.current = noteId;

    const cachedDraft = loadLocalDraft(noteId);
    if (
      cachedDraft &&
      cachedDraft.baseContentHash === serverNote.content_hash &&
      (cachedDraft.body !== serverNote.body ||
        cachedDraft.title !== serverNote.title)
    ) {
      setTitle(cachedDraft.title);
      setNoteType(cachedDraft.noteType);
      setStatus(cachedDraft.status ?? null);
      setFolder(cachedDraft.folder);
      setDomains(cachedDraft.domains);
      setTags(cachedDraft.tags);
      setPinned(cachedDraft.isPinned);
      setBodyMarkdown(cachedDraft.body);
      setDebouncedPreviewMarkdown(cachedDraft.body);
      setExpectedHash(serverNote.content_hash);
      draftRevisionRef.current = 1;
      savedRevisionRef.current = 0;
      setSaveState('unsaved');
      setRestoredLocalBanner(true);
    } else {
      setTitle(serverNote.title);
      setNoteType(serverNote.note_type);
      setStatus(serverNote.status ?? null);
      setFolder(serverNote.folder);
      setDomains(serverNote.domains);
      setTags(serverNote.tags);
      setPinned(serverNote.is_pinned);
      setBodyMarkdown(serverNote.body);
      setDebouncedPreviewMarkdown(serverNote.body);
      setExpectedHash(serverNote.content_hash);
      draftRevisionRef.current = 0;
      savedRevisionRef.current = 0;
      setSaveState('saved');
      setRestoredLocalBanner(false);
    }
  }, [serverNote, noteId]);

  // Reset initialized ref when route noteId changes
  useEffect(() => {
    return () => {
      initializedNoteIdRef.current = null;
    };
  }, [noteId]);

  // Keep latestDraftRef synchronized and persist unsaved drafts to draftStorage
  useEffect(() => {
    if (!noteId || !serverNote) return;
    latestDraftRef.current = {
      noteId,
      title,
      note_type: noteType,
      status,
      folder,
      domains,
      tags,
      is_pinned: pinned,
      body: bodyMarkdown,
      expected_hash: expectedHash,
      is_trashed: serverNote.is_trashed,
    };

    if (draftRevisionRef.current > savedRevisionRef.current && !serverNote.is_trashed) {
      const draftPayload: LocalDraftRecord = {
        noteId,
        title,
        noteType,
        status,
        folder,
        domains,
        tags,
        isPinned: pinned,
        body: bodyMarkdown,
        baseContentHash: expectedHash,
        updatedAt: new Date().toISOString(),
      };
      const res = saveLocalDraft(noteId, draftPayload);
      if (!res.persistedToLocalStorage && res.warningMessage) {
        setQuotaWarning(res.warningMessage);
      }
    }
  }, [
    noteId,
    serverNote,
    title,
    noteType,
    status,
    folder,
    domains,
    tags,
    pinned,
    bodyMarkdown,
    expectedHash,
  ]);

  // Debounce live preview rendering (150ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedPreviewMarkdown(bodyMarkdown);
    }, 150);
    return () => clearTimeout(timer);
  }, [bodyMarkdown]);

  // Helper to mark dirty revision
  const markDirty = useCallback(() => {
    draftRevisionRef.current += 1;
    setSaveState((prev) => (prev === 'conflict' ? 'conflict' : 'unsaved'));
  }, []);

  // Single-flight save function
  const executeSave = useCallback(
    async (forceOverwrite = false) => {
      const snapshot = latestDraftRef.current;
      if (!snapshot || snapshot.is_trashed) return;

      if (saveInFlightRef.current) {
        pendingSaveAfterFlightRef.current = true;
        return;
      }

      const targetRevision = draftRevisionRef.current;
      if (!forceOverwrite && targetRevision <= savedRevisionRef.current) {
        return;
      }

      saveInFlightRef.current = true;
      setSaveState('saving');
      setSaveErrorText(null);

      const payload: UpdateNoteRequest = {
        title: snapshot.title.trim() || 'Untitled Note',
        note_type: snapshot.note_type,
        status: snapshot.status,
        folder: snapshot.folder,
        domains: snapshot.domains,
        tags: snapshot.tags,
        is_pinned: snapshot.is_pinned,
        body: snapshot.body,
        expected_hash: snapshot.expected_hash,
        force: forceOverwrite,
      };

      try {
        const updated: NoteDetail = await api.updateNote(snapshot.noteId, payload);
        setExpectedHash(updated.content_hash);
        if (latestDraftRef.current) {
          latestDraftRef.current.expected_hash = updated.content_hash;
        }
        setFolder(updated.folder);
        queryClient.setQueryData(['note', snapshot.noteId], updated);
        queryClient.invalidateQueries({ queryKey: ['notes'] });
        queryClient.invalidateQueries({ queryKey: ['dashboard'] });
        queryClient.invalidateQueries({ queryKey: ['taxonomy'] });

        savedRevisionRef.current = Math.max(savedRevisionRef.current, targetRevision);
        if (draftRevisionRef.current <= savedRevisionRef.current) {
          removeLocalDraft(snapshot.noteId);
          setRestoredLocalBanner(false);
          setSaveState('saved');
        } else {
          setSaveState('unsaved');
          pendingSaveAfterFlightRef.current = true;
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setSaveState('conflict');
          setSaveErrorText(
            'This note was modified on disk or in another tab. Choose whether to reload the server version or force overwrite.'
          );
        } else {
          setSaveState('error');
          setSaveErrorText(err instanceof Error ? err.message : 'Failed to save note');
        }
      } finally {
        saveInFlightRef.current = false;
        if (
          pendingSaveAfterFlightRef.current &&
          draftRevisionRef.current > savedRevisionRef.current
        ) {
          pendingSaveAfterFlightRef.current = false;
          void executeSave(false);
        } else {
          pendingSaveAfterFlightRef.current = false;
        }
      }
    },
    [queryClient]
  );

  // Debounced autosave effect
  useEffect(() => {
    if (
      !serverNote ||
      serverNote.is_trashed ||
      saveState !== 'unsaved' ||
      draftRevisionRef.current <= savedRevisionRef.current
    ) {
      return;
    }
    const delay = settings?.autosave_delay_ms ?? 1000;
    const timer = setTimeout(() => {
      void executeSave(false);
    }, delay);
    return () => clearTimeout(timer);
  }, [
    title,
    noteType,
    status,
    folder,
    domains,
    tags,
    pinned,
    bodyMarkdown,
    saveState,
    serverNote,
    settings?.autosave_delay_ms,
    executeSave,
  ]);

  // Ctrl+S / Cmd+S keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void executeSave(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [executeSave]);

  // beforeunload warning + background flush on unmount
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (draftRevisionRef.current > savedRevisionRef.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      if (draftRevisionRef.current > savedRevisionRef.current) {
        void executeSave(false);
      }
    };
  }, [executeSave]);

  // CodeMirror 6 lifecycle
  useEffect(() => {
    const container = editorContainerRef.current;
    if (!container || !serverNote || editorViewMode === 'preview') {
      if (editorViewRef.current) {
        editorViewRef.current.destroy();
        editorViewRef.current = null;
      }
      return;
    }

    if (editorViewRef.current) {
      return;
    }

    const wordWrap = settings?.editor_word_wrap ?? true;
    const fontSize = settings?.editor_font_size ?? 14;

    const state = EditorState.create({
      doc: bodyMarkdown,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        drawSelection(),
        markdown({ codeLanguages: languages }),
        oneDark,
        wrapCompartmentRef.current.of(wordWrap ? EditorView.lineWrapping : []),
        fontSizeCompartmentRef.current.of(
          EditorView.theme({
            '&': {
              height: '100%',
              fontSize: `${fontSize}px`,
              backgroundColor: 'transparent',
            },
            '.cm-scroller': {
              fontFamily: '"JetBrains Mono", monospace',
              overflow: 'auto',
              padding: '12px 0',
            },
            '.cm-gutters': {
              backgroundColor: 'transparent',
              borderRight: '1px solid rgba(255,255,255,0.06)',
            },
          })
        ),
        readOnlyCompartmentRef.current.of(EditorState.readOnly.of(serverNote.is_trashed)),
        keymap.of([
          {
            key: 'Mod-s',
            run: () => {
              void executeSave(false);
              return true;
            },
          },
        ]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const nextDoc = update.state.doc.toString();
            setBodyMarkdown(nextDoc);
            draftRevisionRef.current += 1;
            setSaveState((prev) => (prev === 'conflict' ? 'conflict' : 'unsaved'));
          }
        }),
      ],
    });

    const view = new EditorView({
      state,
      parent: container,
    });
    editorViewRef.current = view;

    return () => {
      view.destroy();
      editorViewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editorViewMode, Boolean(serverNote)]);

  // Sync external bodyMarkdown changes (e.g. reload server version) into CodeMirror
  useEffect(() => {
    const view = editorViewRef.current;
    if (!view) return;
    const currentDoc = view.state.doc.toString();
    if (currentDoc !== bodyMarkdown) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: bodyMarkdown },
      });
    }
  }, [bodyMarkdown]);

  // Sync settings changes (word wrap & font size) into CodeMirror compartments
  useEffect(() => {
    const view = editorViewRef.current;
    if (!view || !settings) return;
    view.dispatch({
      effects: [
        wrapCompartmentRef.current.reconfigure(
          settings.editor_word_wrap ? EditorView.lineWrapping : []
        ),
        fontSizeCompartmentRef.current.reconfigure(
          EditorView.theme({
            '&': {
              height: '100%',
              fontSize: `${settings.editor_font_size}px`,
              backgroundColor: 'transparent',
            },
            '.cm-scroller': {
              fontFamily: '"JetBrains Mono", monospace',
              overflow: 'auto',
              padding: '12px 0',
            },
          })
        ),
      ],
    });
  }, [settings]);

  const handleReloadServerVersion = async () => {
    if (!noteId) return;
    removeLocalDraft(noteId);
    initializedNoteIdRef.current = null;
    const res = await refetchNote();
    if (res.data) {
      setTitle(res.data.title);
      setNoteType(res.data.note_type);
      setStatus(res.data.status ?? null);
      setFolder(res.data.folder);
      setDomains(res.data.domains);
      setTags(res.data.tags);
      setPinned(res.data.is_pinned);
      setBodyMarkdown(res.data.body);
      setDebouncedPreviewMarkdown(res.data.body);
      setExpectedHash(res.data.content_hash);
      draftRevisionRef.current = 0;
      savedRevisionRef.current = 0;
      setSaveState('saved');
      setSaveErrorText(null);
      setRestoredLocalBanner(false);
    }
  };

  const handleToggleDomain = (domain: KnowledgeDomain) => {
    markDirty();
    setDomains((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );
  };

  const handleAddTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const cleaned = tagInput.trim().toLowerCase().replace(/^#/, '');
      if (cleaned && !tags.includes(cleaned)) {
        markDirty();
        setTags((prev) => [...prev, cleaned]);
      }
      setTagInput('');
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    markDirty();
    setTags((prev) => prev.filter((t) => t !== tagToRemove));
  };

  const handleMoveToTrash = async () => {
    if (!noteId) return;
    await api.deleteNote(noteId, false);
    removeLocalDraft(noteId);
    queryClient.invalidateQueries({ queryKey: ['notes'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    navigate('/notes');
  };

  const handleRestoreFromTrash = async () => {
    if (!noteId) return;
    await api.restoreNote(noteId);
    initializedNoteIdRef.current = null;
    await refetchNote();
    queryClient.invalidateQueries({ queryKey: ['notes'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const handlePermanentDelete = async () => {
    if (!noteId) return;
    await api.deleteNote(noteId, true);
    removeLocalDraft(noteId);
    queryClient.invalidateQueries({ queryKey: ['notes'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    navigate('/settings');
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs text-text-muted">Loading note workspace...</div>
    );
  }

  if (loadError || !serverNote) {
    return (
      <div className="p-8 text-center space-y-3">
        <div className="text-sm font-semibold text-rose-400">Note Not Found</div>
        <p className="text-xs text-text-secondary">
          {loadError instanceof Error ? loadError.message : 'Unable to load requested note.'}
        </p>
        <Button variant="secondary" size="sm" onClick={() => navigate('/notes')}>
          Back to Notes
        </Button>
      </div>
    );
  }

  const saveBadgeVariant =
    saveState === 'saved'
      ? 'success'
      : saveState === 'saving'
        ? 'accent'
        : saveState === 'unsaved'
          ? 'warning'
          : 'danger';

  const saveBadgeText =
    saveState === 'saved'
      ? 'Saved'
      : saveState === 'saving'
        ? 'Saving...'
        : saveState === 'unsaved'
          ? 'Unsaved changes'
          : saveState === 'conflict'
            ? '409 Conflict'
            : 'Save Error';

  return (
    <div className="flex flex-col h-full bg-canvas-app overflow-hidden">
      {/* Top action toolbar */}
      <div className="h-12 border-b border-canvas-border px-4 flex items-center justify-between shrink-0 bg-canvas-sidebar/40">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            icon={<ArrowLeft size={16} />}
            onClick={() => navigate(-1)}
          >
            Back
          </Button>
          <span className="text-xs text-text-muted">/</span>
          <span className="text-xs font-mono text-text-secondary truncate">
            {serverNote.rel_path}
          </span>
          <Badge variant={saveBadgeVariant} size="sm">
            {saveBadgeText}
          </Badge>
          {serverNote.is_trashed && (
            <Badge variant="danger" size="sm">
              In Trash
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Mode Switcher */}
          <div className="flex items-center bg-canvas-surface border border-canvas-border rounded-md p-0.5">
            <button
              onClick={() => setEditorViewMode('edit')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'edit'
                  ? 'bg-canvas-elevated text-text-primary'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Edit3 size={13} />
              <span>Edit</span>
            </button>
            <button
              onClick={() => setEditorViewMode('split')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'split'
                  ? 'bg-canvas-elevated text-text-primary'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Split size={13} />
              <span>Split</span>
            </button>
            <button
              onClick={() => setEditorViewMode('preview')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'preview'
                  ? 'bg-canvas-elevated text-text-primary'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Eye size={13} />
              <span>Preview</span>
            </button>
          </div>

          {!serverNote.is_trashed ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                icon={<Pin size={14} className={pinned ? 'text-amber-400 fill-amber-400/20' : ''} />}
                onClick={() => {
                  markDirty();
                  setPinned((prev) => !prev);
                }}
              >
                {pinned ? 'Pinned' : 'Pin'}
              </Button>
              <a
                href={api.getNoteExportUrl(serverNote.id)}
                download
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-canvas-surface hover:bg-canvas-elevated text-text-secondary hover:text-text-primary border border-canvas-border transition-colors"
              >
                <Download size={13} />
                <span>Export .md</span>
              </a>
              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 size={14} className="text-rose-400" />}
                onClick={handleMoveToTrash}
              >
                Trash
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<Save size={14} />}
                disabled={saveState === 'saving'}
                onClick={() => void executeSave(false)}
              >
                Save
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                icon={<RotateCcw size={14} />}
                onClick={handleRestoreFromTrash}
              >
                Restore Note
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<Trash2 size={14} />}
                onClick={handlePermanentDelete}
              >
                Delete Permanently
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Non-evicting Quota Warning Banner */}
      {quotaWarning && (
        <div className="px-4 py-2 bg-amber-950/40 border-b border-amber-800/60 flex items-center justify-between text-xs text-amber-200 shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-amber-400 shrink-0" />
            <span>{quotaWarning}</span>
          </div>
          <button
            onClick={() => setQuotaWarning(null)}
            className="text-amber-300 hover:text-white ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Restored Local Unsaved Draft Banner */}
      {restoredLocalBanner && (
        <div className="px-4 py-2 bg-indigo-950/40 border-b border-indigo-800/60 flex items-center justify-between text-xs text-indigo-200 shrink-0">
          <span>Recovered unsaved local draft changes. Autosaving to vault...</span>
          <button
            onClick={handleReloadServerVersion}
            className="underline hover:text-white ml-4"
          >
            Discard Local Draft
          </button>
        </div>
      )}

      {/* 409 Conflict / Save Error Banner */}
      {(saveState === 'conflict' || saveState === 'error') && saveErrorText && (
        <div className="px-4 py-2.5 bg-rose-950/50 border-b border-rose-800/60 flex items-center justify-between text-xs text-rose-200 shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-rose-400 shrink-0" />
            <span>{saveErrorText}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="secondary" size="sm" onClick={handleReloadServerVersion}>
              Reload Server Version
            </Button>
            {saveState === 'conflict' && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => void executeSave(true)}
              >
                Force Overwrite
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Metadata & Frontmatter Controls */}
      <div className="px-6 py-3 border-b border-canvas-border bg-canvas-surface/40 space-y-2.5 shrink-0">
        <input
          type="text"
          value={title}
          disabled={serverNote.is_trashed}
          onChange={(e) => {
            markDirty();
            setTitle(e.target.value);
          }}
          placeholder="Note Title..."
          className="w-full bg-transparent text-lg font-bold text-text-primary focus:outline-none placeholder:text-text-muted"
        />

        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Note Type */}
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted">Type:</span>
            <select
              value={noteType}
              disabled={serverNote.is_trashed}
              onChange={(e) => {
                markDirty();
                setNoteType(e.target.value as NoteType);
              }}
              className="px-2 py-1 rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
            >
              {NOTE_TYPES.map((nt) => (
                <option key={nt} value={nt}>
                  {nt}
                </option>
              ))}
            </select>
          </div>

          {/* Status (including null / No Status) */}
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted">Status:</span>
            <select
              value={status ?? ''}
              disabled={serverNote.is_trashed}
              onChange={(e) => {
                markDirty();
                const val = e.target.value;
                setStatus(val === '' ? null : (val as NoteStatus));
              }}
              className="px-2 py-1 rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
            >
              {NOTE_STATUS_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Folder */}
          {!serverNote.is_trashed && (
            <div className="flex items-center gap-1.5">
              <span className="text-text-muted">Folder:</span>
              <select
                value={folder}
                onChange={(e) => {
                  markDirty();
                  setFolder(e.target.value);
                }}
                className="px-2 py-1 rounded bg-canvas-app border border-canvas-border text-text-primary font-mono focus:outline-none focus:border-accent"
              >
                {VAULT_FOLDERS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Domains */}
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-text-muted mr-1">Domains:</span>
            {ALL_DOMAINS.map((d) => {
              const active = domains.includes(d);
              return (
                <button
                  key={d}
                  type="button"
                  disabled={serverNote.is_trashed}
                  onClick={() => handleToggleDomain(d)}
                  className={`px-2 py-0.5 rounded text-[11px] border transition-colors ${
                    active
                      ? 'bg-accent/15 border-accent/50 text-accent font-medium'
                      : 'bg-canvas-app border-canvas-border text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {d}
                </button>
              );
            })}
          </div>

          {/* Tags */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-text-muted">Tags:</span>
            {tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-canvas-elevated border border-canvas-border font-mono text-[11px] text-text-secondary"
              >
                #{tag}
                {!serverNote.is_trashed && (
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="text-text-muted hover:text-rose-400"
                  >
                    <X size={10} />
                  </button>
                )}
              </span>
            ))}
            {!serverNote.is_trashed && (
              <div className="inline-flex items-center">
                <Plus size={11} className="text-text-muted mr-1" />
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleAddTag}
                  placeholder="add-tag..."
                  className="w-24 px-1.5 py-0.5 text-[11px] font-mono rounded bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:border-accent"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Workspace: Split / Edit / Preview */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {editorViewMode === 'split' ? (
          <PanelGroup direction="horizontal" className="h-full">
            <Panel defaultSize={50} minSize={25} className="h-full overflow-hidden">
              <div ref={editorContainerRef} className="h-full w-full overflow-auto" />
            </Panel>
            <PanelResizeHandle className="w-1.5 bg-canvas-border/60 hover:bg-accent/60 transition-colors cursor-col-resize" />
            <Panel defaultSize={50} minSize={25} className="h-full overflow-y-auto p-6 bg-canvas-surface/20">
              <article className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize, rehypeHighlight]}
                >
                  {debouncedPreviewMarkdown || '*Empty Markdown body*'}
                </ReactMarkdown>
              </article>
            </Panel>
          </PanelGroup>
        ) : editorViewMode === 'edit' ? (
          <div ref={editorContainerRef} className="h-full w-full overflow-auto" />
        ) : (
          <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
            <article className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize, rehypeHighlight]}
              >
                {debouncedPreviewMarkdown || '*Empty Markdown body*'}
              </ReactMarkdown>
            </article>
          </div>
        )}
      </div>
    </div>
  );
};
