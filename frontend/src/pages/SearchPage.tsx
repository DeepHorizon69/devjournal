import React from 'react';
import { Search, Filter } from 'lucide-react';
import { Badge } from '../components/ui/Badge';

export const SearchPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">Full-Text Knowledge Search</h1>
        <p className="text-sm text-text-secondary mt-1">
          Search across titles, headings, body text, tags, and knowledge domains powered by SQLite FTS5.
        </p>
      </div>

      {/* Search Input Box */}
      <div className="relative">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="Search by keywords, tags, or concepts (e.g. wireguard mtu, linux systemd)..."
          className="w-full pl-10 pr-4 py-2.5 text-sm rounded-lg bg-canvas-surface border border-canvas-border text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
        />
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
        <span className="text-text-muted flex items-center gap-1">
          <Filter size={13} />
          <span>Filters:</span>
        </span>
        <Badge variant="default">All Types</Badge>
        <Badge variant="default">All Domains</Badge>
        <Badge variant="default">All Tags</Badge>
      </div>

      {/* Results placeholder */}
      <div className="py-16 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-xl">
        Enter a search query above or press <kbd className="font-mono bg-canvas-surface px-1.5 py-0.5 rounded border border-canvas-border">Ctrl+K</kbd> to search anywhere.
      </div>
    </div>
  );
};
