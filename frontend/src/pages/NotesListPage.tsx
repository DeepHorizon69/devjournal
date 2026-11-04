import React, { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus } from 'lucide-react';
import { api } from '../api/client';
import { useUIStore } from '../store/useUIStore';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { FilterBar, NoteFiltersState } from '../components/notes/FilterBar';
import { NoteRow } from '../components/notes/NoteRow';
import { useToastStore } from '../components/ui/Toast';
import { KnowledgeDomain, NoteSummary, NoteType } from '../types';

const DOMAIN_LABELS: Record<string, KnowledgeDomain> = {
  networking: 'Networking',
  linux: 'Linux',
  programming: 'Programming',
  iot: 'IoT',
  cybersecurity: 'Cybersecurity',
  homelab: 'Homelab',
  mathematics: 'Mathematics',
};

interface NotesListPageProps {
  fixedType?: NoteType;
}

const DEFAULT_FILTERS: NoteFiltersState = {
  search: '',
  type: '',
  domain: '',
  status: '',
  tag: '',
  folder: '',
  sort: 'updated_desc',
};

export const NotesListPage: React.FC<NotesListPageProps> = ({ fixedType }) => {
  const { domainSlug } = useParams<{ domainSlug?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { openNewNoteModal } = useUIStore();
  const { addToast } = useToastStore();

  const [filters, setFilters] = useState<NoteFiltersState>(DEFAULT_FILTERS);

  const domainName: KnowledgeDomain | null = domainSlug
    ? DOMAIN_LABELS[domainSlug.toLowerCase()] || null
    : null;

  const effectiveType = fixedType || filters.type;
  const effectiveDomain = domainName || filters.domain;

  const { data: taxonomy } = useQuery({
    queryKey: ['taxonomy'],
    queryFn: api.getTaxonomy,
  });

  const { data: notesData, isLoading } = useQuery({
    queryKey: [
      'notes',
      {
        type: effectiveType,
        domain: effectiveDomain,
        status: filters.status,
        tag: filters.tag,
        folder: filters.folder,
        sort: filters.sort,
      },
    ],
    queryFn: () =>
      api.listNotes({
        type: effectiveType,
        domain: effectiveDomain,
        status: filters.status,
        tag: filters.tag,
        folder: filters.folder,
        sort: filters.sort,
        trashed: false,
        limit: 100,
      }),
  });

  const togglePinMutation = useMutation({
    mutationFn: (note: NoteSummary) =>
      api.patchNote(note.id, {
        is_pinned: !note.is_pinned,
        expected_hash: note.content_hash,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (err: Error) => {
      addToast({
        title: 'Could not update pin state',
        description: err.message,
        variant: 'error',
      });
    },
  });

  const filteredNotes = useMemo(() => {
    const items = notesData?.notes || [];
    const q = filters.search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (n) =>
        n.title.toLowerCase().includes(q) ||
        n.excerpt.toLowerCase().includes(q) ||
        n.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [notesData, filters.search]);

  const availableTags = useMemo(
    () => Object.keys(taxonomy?.tags || {}),
    [taxonomy]
  );
  const availableFolders = useMemo(
    () => Object.keys(taxonomy?.folders || {}),
    [taxonomy]
  );

  const getPageTitle = () => {
    if (domainName) return `Domain: ${domainName}`;
    if (fixedType === 'experiment') return 'Experiments';
    if (fixedType === 'troubleshooting') return 'Troubleshooting';
    if (fixedType === 'project') return 'Projects';
    return 'All Notes';
  };

  const getPageSubtitle = () => {
    if (domainName) {
      return `All notes, experiments, and projects associated with the ${domainName} knowledge domain.`;
    }
    if (fixedType === 'experiment')
      return 'Structured engineering benchmarks, proof-of-concepts, and lab tests.';
    if (fixedType === 'troubleshooting')
      return 'Incident investigations, bug diagnostics, and root-cause analyses.';
    if (fixedType === 'project')
      return 'System architectures, implementations, and homelab projects.';
    return 'Master catalog of all knowledge records in your local vault.';
  };

  const getEmptyTitle = () => {
    if (domainName) return `No ${domainName} notes found`;
    if (fixedType === 'experiment') return 'No experiments found';
    if (fixedType === 'troubleshooting') return 'No troubleshooting notes found';
    if (fixedType === 'project') return 'No projects found';
    return 'No notes found';
  };

  const handleOpenNew = () => {
    openNewNoteModal({
      noteType: fixedType,
      template: fixedType || 'general',
      domain: domainName || undefined,
    });
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-canvas-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            {getPageTitle()}
          </h1>
          <p className="text-sm text-text-secondary mt-1">{getPageSubtitle()}</p>
        </div>
        <Button
          variant="primary"
          icon={<Plus size={16} />}
          onClick={handleOpenNew}
        >
          {fixedType
            ? `New ${fixedType.charAt(0).toUpperCase() + fixedType.slice(1)}`
            : 'New Note'}
        </Button>
      </div>

      {/* Filter toolbar */}
      <FilterBar
        filters={filters}
        onChange={(updated) => setFilters((prev) => ({ ...prev, ...updated }))}
        onReset={() => setFilters(DEFAULT_FILTERS)}
        hideTypeFilter={Boolean(fixedType)}
        hideDomainFilter={Boolean(domainName)}
        availableTags={availableTags}
        availableFolders={availableFolders}
        totalCount={filteredNotes.length}
      />

      {/* Notes list or empty state */}
      {isLoading ? (
        <div className="py-16 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-xl">
          Loading notes from vault...
        </div>
      ) : filteredNotes.length === 0 ? (
        <div className="py-12 bg-canvas-surface/40 border border-dashed border-canvas-border rounded-xl">
          <EmptyState
            icon={<FileText size={24} />}
            title={getEmptyTitle()}
            description="Create your first entry to start building this section of your personal knowledge base."
            actionLabel="Create Note"
            onAction={handleOpenNew}
          />
        </div>
      ) : (
        <div className="rounded-xl border border-canvas-border overflow-hidden bg-canvas-surface/30">
          {filteredNotes.map((note) => (
            <NoteRow
              key={note.id}
              note={note}
              onSelect={(id) => navigate(`/notes/${id}`)}
              onTogglePin={(n) => togglePinMutation.mutate(n)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
