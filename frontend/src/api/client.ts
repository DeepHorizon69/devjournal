import {
  AppSettings,
  BackupResponse,
  CreateNoteRequest,
  DashboardData,
  DeleteNoteResponse,
  EmptyTrashResponse,
  HealthStatus,
  NoteDetail,
  NotesListResponse,
  NoteStatus,
  NoteType,
  PatchNoteRequest,
  ReindexResult,
  RestoreResponse,
  SearchResponse,
  TaxonomyCounts,
  TemplatesListResponse,
  UpdateNoteRequest,
  UpdateSettingsRequest,
  KnowledgeDomain,
} from '../types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: Record<string, unknown>,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const headers: Record<string, string> = isFormData
    ? {}
    : { 'Content-Type': 'application/json' };

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...headers,
      ...(options?.headers as Record<string, string> | undefined),
    },
  });

  if (!response.ok) {
    let errorData: {
      error?: { code?: string; message?: string; details?: Record<string, unknown> };
    } = {};
    try {
      errorData = await response.json();
    } catch {
      // ignore json parse error
    }
    const message =
      errorData.error?.message || response.statusText || 'API Request failed';
    throw new ApiError(
      response.status,
      message,
      errorData.error?.details,
      errorData.error?.code
    );
  }

  return response.json();
}

export interface ListNotesParams {
  type?: NoteType | '';
  domain?: KnowledgeDomain | '';
  tag?: string;
  folder?: string;
  status?: NoteStatus | '';
  trashed?: boolean;
  sort?: 'updated_desc' | 'created_desc' | 'title_asc';
  limit?: number;
  offset?: number;
}

export interface SearchParams {
  q: string;
  type?: NoteType | '';
  domain?: KnowledgeDomain | '';
  tag?: string;
  folder?: string;
  status?: NoteStatus | '';
  trashed?: boolean;
  limit?: number;
}

function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== null && val !== '') {
      searchParams.set(key, String(val));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

export const api = {
  getHealth: () => request<HealthStatus>('/system/health'),
  reindex: () => request<ReindexResult>('/system/reindex', { method: 'POST' }),
  getTemplates: () => request<TemplatesListResponse>('/templates'),
  getTaxonomy: () => request<TaxonomyCounts>('/taxonomy'),
  getDashboard: () => request<DashboardData>('/dashboard'),

  listNotes: (params: ListNotesParams = {}) =>
    request<NotesListResponse>(`/notes${buildQueryString(params as Record<string, unknown>)}`),

  createNote: (payload: CreateNoteRequest) =>
    request<NoteDetail>('/notes', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getNote: (noteId: string, recordOpen = true) =>
    request<NoteDetail>(
      `/notes/${encodeURIComponent(noteId)}?record_open=${recordOpen}`
    ),

  updateNote: (noteId: string, payload: UpdateNoteRequest) =>
    request<NoteDetail>(`/notes/${encodeURIComponent(noteId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  patchNote: (noteId: string, payload: PatchNoteRequest) =>
    request<NoteDetail>(`/notes/${encodeURIComponent(noteId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteNote: (noteId: string, permanent = false) =>
    request<DeleteNoteResponse>(
      `/notes/${encodeURIComponent(noteId)}?permanent=${permanent}`,
      { method: 'DELETE' }
    ),

  restoreNote: (noteId: string) =>
    request<NoteDetail>(`/notes/${encodeURIComponent(noteId)}/restore`, {
      method: 'POST',
    }),

  emptyTrash: () =>
    request<EmptyTrashResponse>('/notes/trash', { method: 'DELETE' }),

  openOrCreateDaily: (date?: string) =>
    request<NoteDetail>('/notes/daily/today', {
      method: 'POST',
      body: JSON.stringify(date ? { date } : {}),
    }),

  getNoteExportUrl: (noteId: string) =>
    `${API_BASE}/notes/${encodeURIComponent(noteId)}/export`,

  importMarkdown: (file: File, folder = '00-Inbox') => {
    const form = new FormData();
    form.append('file', file);
    form.append('folder', folder);
    return request<NoteDetail>('/system/import-md', {
      method: 'POST',
      body: form,
    });
  },

  createBackup: () =>
    request<BackupResponse>('/system/backup', { method: 'POST' }),

  getBackupDownloadUrl: (filename: string) =>
    `${API_BASE}/system/backups/${encodeURIComponent(filename)}`,

  restoreBackup: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<RestoreResponse>('/system/restore', {
      method: 'POST',
      body: form,
    });
  },

  search: (params: SearchParams) =>
    request<SearchResponse>(`/search${buildQueryString(params as unknown as Record<string, unknown>)}`),

  getSettings: () => request<AppSettings>('/settings'),

  updateSettings: (payload: UpdateSettingsRequest) =>
    request<AppSettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
};
