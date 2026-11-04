import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileText, Plus, Filter, ArrowUpDown } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { NoteType } from '../types';

const DOMAIN_LABELS: Record<string, string> = {
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

export const NotesListPage: React.FC<NotesListPageProps> = ({ fixedType }) => {
  const { domainSlug } = useParams<{ domainSlug?: string }>();
  const navigate = useNavigate();

  const domainName = domainSlug ? DOMAIN_LABELS[domainSlug.toLowerCase()] || (domainSlug.charAt(0).toUpperCase() + domainSlug.slice(1)) : null;

  // Determine title and view mode
  const getPageTitle = () => {
    if (domainName) {
      return `Domain: ${domainName}`;
    }
    if (fixedType === 'experiment') return 'Experiments';
    if (fixedType === 'troubleshooting') return 'Troubleshooting';
    if (fixedType === 'project') return 'Projects';
    return 'All Notes';
  };

  const getPageSubtitle = () => {
    if (domainName) {
      return `All notes, experiments, and projects associated with the ${domainName} knowledge domain.`;
    }
    if (fixedType === 'experiment') return 'Structured engineering benchmarks, proof-of-concepts, and lab tests.';
    if (fixedType === 'troubleshooting') return 'Incident investigations, bug diagnostics, and root-cause analyses.';
    if (fixedType === 'project') return 'System architectures, implementations, and homelab projects.';
    return 'Master catalog of all knowledge records in your local vault.';
  };

  const getEmptyTitle = () => {
    if (domainName) return `No ${domainName} notes found`;
    if (fixedType === 'experiment') return 'No experiments found';
    if (fixedType === 'troubleshooting') return 'No troubleshooting notes found';
    if (fixedType === 'project') return 'No projects found';
    return 'No notes found';
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-canvas-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">{getPageTitle()}</h1>
          <p className="text-sm text-text-secondary mt-1">{getPageSubtitle()}</p>
        </div>
        <Button
          variant="primary"
          icon={<Plus size={16} />}
          onClick={() => {
            const params = new URLSearchParams();
            if (fixedType) params.set('type', fixedType);
            if (domainSlug) params.set('domain', domainSlug);
            navigate(`/notes?new=true&${params.toString()}`);
          }}
        >
          {fixedType ? `New ${fixedType.charAt(0).toUpperCase() + fixedType.slice(1)}` : 'New Note'}
        </Button>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-canvas-surface border border-canvas-border">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary bg-canvas-app border border-canvas-border rounded-md">
            <Filter size={14} className="text-text-muted" />
            <span>Filter</span>
          </div>
          <span className="text-xs text-text-muted">Showing 0 records</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-text-muted">
            <ArrowUpDown size={14} />
            <span>Sort:</span>
            <span className="text-text-primary font-medium">Updated (Newest)</span>
          </div>
        </div>
      </div>

      {/* Empty State placeholder */}
      <div className="py-12 bg-canvas-surface/40 border border-dashed border-canvas-border rounded-xl">
        <EmptyState
          icon={<FileText size={24} />}
          title={getEmptyTitle()}
          description="Create your first entry to start building this section of your personal knowledge base."
          actionLabel="Create Note"
          onAction={() => {
            const params = new URLSearchParams();
            if (fixedType) params.set('type', fixedType);
            if (domainSlug) params.set('domain', domainSlug);
            navigate(`/notes?new=true&${params.toString()}`);
          }}
        />
      </div>
    </div>
  );
};
