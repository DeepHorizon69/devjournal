import { KnowledgeDomain, NoteStatus, NoteType } from '../types';

export const DRAFT_STORAGE_PREFIX = 'devjournal:unsaved-draft:';

export const DRAFT_STORAGE_WARNING_MESSAGE =
  'Persistent browser storage is full or unavailable. Your current draft is kept in memory for this tab, but will be lost if you close the tab or refresh before saving to the server.';

export interface LocalDraftRecord {
  noteId: string;
  title: string;
  noteType: NoteType;
  status: NoteStatus | null;
  domains: KnowledgeDomain[];
  tags: string[];
  folder: string;
  isPinned: boolean;
  body: string;
  baseContentHash: string;
  updatedAt: string;
}

export interface SaveDraftResult {
  persistedToLocalStorage: boolean;
  warningMessage?: string;
}

// Module-scoped in-memory draft cache preserving unsaved drafts across component unmount/remount
// and in-app route navigation within the current browser tab session (P1-2).
const memoryDraftCache = new Map<string, LocalDraftRecord>();

/**
 * Save a draft to the in-memory tab cache and attempt persistent localStorage storage.
 * Never evicts or deletes any other note's persistent draft from localStorage on QuotaExceededError (P1-2).
 */
export function saveLocalDraft(
  noteId: string,
  record: LocalDraftRecord,
  onQuotaWarning?: (warningMessage: string) => void
): SaveDraftResult {
  memoryDraftCache.set(noteId, record);

  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(
        `${DRAFT_STORAGE_PREFIX}${noteId}`,
        JSON.stringify(record)
      );
      return { persistedToLocalStorage: true };
    }
  } catch {
    // QuotaExceededError or SecurityError: retain in memoryDraftCache without evicting any other note's draft!
    if (onQuotaWarning) {
      onQuotaWarning(DRAFT_STORAGE_WARNING_MESSAGE);
    }
    return {
      persistedToLocalStorage: false,
      warningMessage: DRAFT_STORAGE_WARNING_MESSAGE,
    };
  }

  return { persistedToLocalStorage: true };
}

/**
 * Load a draft for a note from the in-memory session cache or persistent localStorage.
 */
export function loadLocalDraft(noteId: string): LocalDraftRecord | null {
  const mem = memoryDraftCache.get(noteId);
  if (mem) {
    return mem;
  }

  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const raw = window.localStorage.getItem(`${DRAFT_STORAGE_PREFIX}${noteId}`);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as LocalDraftRecord;
      if (parsed && parsed.noteId === noteId && typeof parsed.body === 'string') {
        memoryDraftCache.set(noteId, parsed);
        return parsed;
      }
    }
  } catch {
    // Ignore storage read or JSON parse errors
  }

  return null;
}

/**
 * Remove a note's draft from both the in-memory session cache and localStorage after a successful save.
 */
export function removeLocalDraft(noteId: string): void {
  memoryDraftCache.delete(noteId);
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(`${DRAFT_STORAGE_PREFIX}${noteId}`);
    }
  } catch {
    // Ignore storage errors
  }
}

export function clearMemoryDraftCacheForTesting(): void {
  memoryDraftCache.clear();
}
