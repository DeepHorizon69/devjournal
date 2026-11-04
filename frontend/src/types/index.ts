export type NoteType = 'note' | 'experiment' | 'troubleshooting' | 'project' | 'daily' | 'snippet';

export type KnowledgeDomain =
  | 'Networking'
  | 'Linux'
  | 'Programming'
  | 'IoT'
  | 'Cybersecurity'
  | 'Homelab'
  | 'Mathematics';

export type NoteStatus =
  | 'draft'
  | 'active'
  | 'investigating'
  | 'resolved'
  | 'completed'
  | 'archived';

export type EditorMode = 'raw' | 'split' | 'preview';

export interface NoteSummary {
  id: string;
  title: string;
  slug: string;
  rel_path: string;
  folder: string;
  note_type: NoteType;
  status?: NoteStatus | null;
  excerpt: string;
  word_count: number;
  reading_time_mins: number;
  content_hash: string;
  is_pinned: boolean;
  is_trashed: boolean;
  domains: KnowledgeDomain[];
  tags: string[];
  created_at: string;
  updated_at: string;
  last_opened_at?: string | null;
}

export interface NoteDetail extends NoteSummary {
  body: string;
}

export interface NotesListResponse {
  total: number;
  notes: NoteSummary[];
}

export interface TemplateItem {
  id: string;
  name: string;
  note_type: NoteType;
  default_status: NoteStatus | null;
  folder: string;
  body: string;
}

export interface TemplatesListResponse {
  templates: TemplateItem[];
}

export interface CreateNoteRequest {
  title: string;
  note_type?: NoteType | null;
  status?: NoteStatus | null;
  domains?: KnowledgeDomain[];
  tags?: string[];
  folder?: string | null;
  body?: string | null;
  template_id?: string | null;
  is_pinned?: boolean;
}

export interface UpdateNoteRequest {
  title: string;
  note_type: NoteType;
  status: NoteStatus | null;
  domains: KnowledgeDomain[];
  tags: string[];
  folder?: string | null;
  is_pinned: boolean;
  body: string;
  expected_hash?: string | null;
  force?: boolean;
}

export interface PatchNoteRequest {
  title?: string;
  note_type?: NoteType;
  status?: NoteStatus | null;
  domains?: KnowledgeDomain[];
  tags?: string[];
  folder?: string;
  is_pinned?: boolean;
  expected_hash: string;
}

export interface DeleteNoteResponse {
  status: string;
  deleted_id: string;
  permanent: boolean;
}

export interface EmptyTrashResponse {
  status: string;
  deleted_count: number;
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'maintenance';
  vault_writable: boolean;
  db_ok: boolean;
  indexed_notes: number;
  data_dir: string;
}

export interface ReindexResult {
  status: string;
  indexed: number;
  updated?: number;
  unchanged?: number;
  removed: number;
  warnings?: number;
  warning_details?: string[];
  duration_ms: number;
}

export interface TaxonomyCounts {
  types: Record<string, number>;
  domains: Record<string, number>;
  tags: Record<string, number>;
  folders: Record<string, number>;
  total_active: number;
  total_trashed: number;
}

export interface DashboardData {
  counts: {
    total_notes: number;
    experiments: number;
    troubleshooting: number;
    projects: number;
    daily: number;
    snippets: number;
  };
  domain_counts: Record<KnowledgeDomain, number>;
  recently_opened: NoteSummary[];
  recently_updated: NoteSummary[];
}

export interface SnippetSegment {
  text: string;
  highlight: boolean;
}

export interface SearchResultItem {
  id: string;
  title: string;
  slug: string;
  rel_path: string;
  folder: string;
  note_type: NoteType;
  status: NoteStatus | null;
  domains: KnowledgeDomain[];
  tags: string[];
  updated_at: string;
  snippet: string;
  snippet_segments?: SnippetSegment[];
  score: number;
}

export interface SearchResponse {
  query: string;
  total_matches: number;
  results: SearchResultItem[];
}

export interface AppSettings {
  default_editor_mode: EditorMode;
  editor_font_size: number;
  editor_word_wrap: boolean;
  autosave_delay_ms: number;
  updated_at: string;
}

export interface UpdateSettingsRequest {
  default_editor_mode: EditorMode;
  editor_font_size: number;
  editor_word_wrap: boolean;
  autosave_delay_ms: number;
}

export interface BackupResponse {
  status: string;
  filename: string;
  size_bytes: number;
  created_at: string;
}

export interface RestoreResponse {
  status: string;
  indexed: number;
  safety_backup_filename: string;
  duration_ms: number;
}
