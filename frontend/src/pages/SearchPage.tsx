import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, FileText } from 'lucide-react';
import { api } from '../api/client';
import { Badge } from '../components/ui/Badge';
import { Select } from '../components/ui/Select';
import { KnowledgeDomain, NoteType } from '../types';
import { renderHighlightedSnippet } from '../utils/highlight';

const TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: 'note', label: 'General Note' },
  { value: 'experiment', label: 'Experiment' },
  { value: 'troubleshooting', label: 'Troubleshooting' },
  { value: 'project', label: 'Project' },
  { value: 'daily', label: 'Daily Journal' },
  { value: 'snippet', label: 'Snippet' },
];

const DOMAIN_OPTIONS = [
  { value: '', label: 'All Domains' },
  { value: 'Networking', label: 'Networking' },
  { value: 'Linux', label: 'Linux' },
  { value: 'Programming', label: 'Programming' },
  { value: 'IoT', label: 'IoT' },
  { value: 'Cybersecurity', label: 'Cybersecurity' },
  { value: 'Homelab', label: 'Homelab' },
  { value: 'Mathematics', label: 'Mathematics' },
];

export const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<NoteType | ''>('');
  const [domainFilter, setDomainFilter] = useState<KnowledgeDomain | ''>('');
  const [tagFilter, setTagFilter] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: taxonomy } = useQuery({
    queryKey: ['taxonomy'],
    queryFn: api.getTaxonomy,
  });

  const { data: searchData, isLoading } = useQuery({
    queryKey: [
      'search',
      {
        q: debouncedQuery,
        type: typeFilter,
        domain: domainFilter,
        tag: tagFilter,
      },
    ],
    queryFn: () =>
      api.search({
        q: debouncedQuery,
        type: typeFilter,
        domain: domainFilter,
        tag: tagFilter,
        limit: 50,
      }),
    enabled: debouncedQuery.length > 0,
  });

  const tagOptions = [
    { value: '', label: 'All Tags' },
    ...Object.keys(taxonomy?.tags || {}).map((t) => ({
      value: t,
      label: `#${t}`,
    })),
  ];

  const results = searchData?.results || [];

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          Full-Text Knowledge Search
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Search across titles, headings, body text, tags, and knowledge domains powered by SQLite FTS5.
        </p>
      </div>

      {/* Search Input Box */}
      <div className="relative">
        <Search
          size={18}
          className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by keywords, tags, or concepts (e.g. wireguard mtu, linux systemd)..."
          autoFocus
          className="w-full pl-10 pr-4 py-2.5 text-sm rounded-lg bg-canvas-surface border border-canvas-border text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
        />
      </div>

      {/* Filter dropdowns */}
      <div className="flex flex-wrap items-center gap-2.5 pt-1 text-xs">
        <span className="text-text-muted flex items-center gap-1">
          <Filter size={13} />
          <span>Filters:</span>
        </span>
        <Select
          aria-label="Filter search by type"
          selectSize="sm"
          options={TYPE_OPTIONS}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as NoteType | '')}
        />
        <Select
          aria-label="Filter search by domain"
          selectSize="sm"
          options={DOMAIN_OPTIONS}
          value={domainFilter}
          onChange={(e) =>
            setDomainFilter(e.target.value as KnowledgeDomain | '')
          }
        />
        <Select
          aria-label="Filter search by tag"
          selectSize="sm"
          options={tagOptions}
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
        />
      </div>

      {/* Results */}
      {!debouncedQuery ? (
        <div className="py-16 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-xl">
          Enter a search query above or press{' '}
          <kbd className="font-mono bg-canvas-surface px-1.5 py-0.5 rounded border border-canvas-border">
            Ctrl+K
          </kbd>{' '}
          to search anywhere.
        </div>
      ) : isLoading ? (
        <div className="py-16 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-xl">
          Searching FTS5 BM25 index...
        </div>
      ) : results.length === 0 ? (
        <div className="py-16 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-xl">
          No matching notes found for &ldquo;{debouncedQuery}&rdquo;.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-text-muted font-mono">
            Found {searchData?.total_matches ?? results.length} matching{' '}
            {(searchData?.total_matches ?? results.length) === 1 ? 'note' : 'notes'}
          </div>
          <div className="divide-y divide-canvas-border rounded-xl border border-canvas-border bg-canvas-surface/40 overflow-hidden">
            {results.map((item) => (
              <div
                key={item.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/notes/${item.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/notes/${item.id}`);
                  }
                }}
                className="p-4 hover:bg-canvas-elevated/70 transition-colors cursor-pointer space-y-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={14} className="text-accent shrink-0" />
                    <h3 className="text-sm font-semibold text-text-primary truncate">
                      {item.title}
                    </h3>
                    <Badge variant="default" size="sm">
                      {item.note_type}
                    </Badge>
                    {item.status && (
                      <Badge variant="muted" size="sm">
                        {item.status}
                      </Badge>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-text-muted shrink-0">
                    {item.folder}
                  </span>
                </div>

                <p className="text-xs text-text-secondary leading-relaxed">
                  {renderHighlightedSnippet(item.snippet, item.snippet_segments)}
                </p>

                {(item.domains.length > 0 || item.tags.length > 0) && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {item.domains.map((dom) => (
                      <span
                        key={dom}
                        className="text-[11px] text-text-secondary bg-canvas-app/80 border border-canvas-border px-1.5 py-0.5 rounded leading-none"
                      >
                        {dom}
                      </span>
                    ))}
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[11px] font-mono text-text-muted"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
