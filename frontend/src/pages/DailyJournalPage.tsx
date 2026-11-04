import React from 'react';
import { Calendar, Plus, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const DailyJournalPage: React.FC = () => {
  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-canvas-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Daily Engineering Journal</h1>
          <p className="text-sm text-text-secondary mt-1">
            Chronological log of daily learning, activities, problem solving, and progress.
          </p>
        </div>
        <Button
          variant="primary"
          icon={<Plus size={16} />}
        >
          Open Today's Entry ({todayStr})
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar / Timeline jump panel */}
        <div className="p-4 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
          <div className="flex items-center justify-between text-xs font-semibold text-text-muted uppercase tracking-wider">
            <span>Journal Timeline</span>
            <div className="flex items-center gap-1">
              <button className="p-1 hover:bg-canvas-elevated rounded text-text-muted hover:text-text-primary">
                <ChevronLeft size={14} />
              </button>
              <button className="p-1 hover:bg-canvas-elevated rounded text-text-muted hover:text-text-primary">
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
          <div className="text-xs text-text-muted py-6 text-center border border-dashed border-canvas-border rounded">
            No entries for this month yet.
          </div>
        </div>

        {/* Current Entry preview placeholder */}
        <div className="lg:col-span-3 p-6 rounded-lg bg-canvas-surface border border-canvas-border flex flex-col items-center justify-center py-20 text-center">
          <div className="w-12 h-12 rounded-xl bg-canvas-elevated flex items-center justify-center text-accent mb-3">
            <Calendar size={22} />
          </div>
          <h3 className="text-base font-semibold text-text-primary mb-1">
            Today's Log: {todayStr}
          </h3>
          <p className="text-xs text-text-secondary max-w-sm mb-4">
            Click below to initialize today's engineering journal from the Daily template.
          </p>
          <Button variant="primary" size="sm">
            Initialize Entry
          </Button>
        </div>
      </div>
    </div>
  );
};
