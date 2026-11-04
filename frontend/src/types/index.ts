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

export interface HealthStatus {
  status: 'ok' | 'degraded';
  vault_writable: boolean;
  db_ok: boolean;
  indexed_notes: number;
  data_dir: string;
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
