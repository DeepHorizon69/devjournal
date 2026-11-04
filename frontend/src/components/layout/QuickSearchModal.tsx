import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, FileText, ArrowRight } from 'lucide-react';
import { api } from '../../api/client';
import { useUIStore } from '../../store/useUIStore';
import { Modal } from '../ui/Modal';
import { Badge } from '../ui/Badge';
import { renderHighlightedSnippet } from '../../utils/highlight';

export const QuickSearchModal: React.FC = () => {
  const { isCommandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 180);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!isCommandPaletteOpen) {
      setQuery('');
      setDebouncedQuery('');
    }
  }, [isCommandPaletteOpen]);

  const { data, isLoading } = useQuery({
    queryKey: ['quick-search', debouncedQuery],
    queryFn: () => api.search({ q: debouncedQuery, limit: 10 }),
    enabled: isCommandPaletteOpen && debouncedQuery.length > 0,
  });

  const handleSelectNote = (noteId: string) => {
    setCommandPaletteOpen(false);
    navigate(`/notes/${noteId}`);
  };

  return (
    <Modal
      open={isCommandPaletteOpen}
      onClose={() => setCommandPaletteOpen(false)}
      title="Quick Knowledge Search"
      maxWidth="lg"
    >
      <div className="space-y-3">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search notes, headings, code blocks, tags..."
            autoFocus
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-canvas-app border border-canvas-border text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        <div className="max-h-80 overflow-y-auto divide-y divide-canvas-border/60 rounded-lg border border-canvas-border bg-canvas-app/50">
          {!debouncedQuery ? (
            <div className="py-8 text-center text-xs text-text-muted">
              Type a keyword to search across your vault, or{' '}
              <button
                type="button"
                onClick={() => {
                  setCommandPaletteOpen(false);
                  navigate('/search');
                }}
                className="text-accent hover:underline"
              >
                open full Search page
              </button>
              .
            </div>
          ) : isLoading ? (
            <div className="py-8 text-center text-xs text-text-muted">
              Searching FTS5 index...
            </div>
          ) : !data || data.results.length === 0 ? (
            <div className="py-8 text-center text-xs text-text-muted">
              No matching notes found for &ldquo;{debouncedQuery}&rdquo;.
            </div>
          ) : (
            data.results.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => handleSelectNote(item.id)}
                className="w-full text-left p-3 hover:bg-canvas-elevated transition-colors flex items-start justify-between gap-3"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <FileText size={13} className="text-accent shrink-0" />
                    <span className="text-xs font-semibold text-text-primary truncate">
                      {item.title}
                    </span>
                    <Badge variant="default" size="sm">
                      {item.note_type}
                    </Badge>
                    {item.status && (
                      <Badge variant="muted" size="sm">
                        {item.status}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
                    {renderHighlightedSnippet(item.snippet, item.snippet_segments)}
                  </p>
                </div>
                <ArrowRight size={14} className="text-text-muted shrink-0 mt-1" />
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
};
