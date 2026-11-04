import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar, Plus } from 'lucide-react';
import { api } from '../api/client';
import { Button } from '../components/ui/Button';
import { NoteRow } from '../components/notes/NoteRow';
import { useToastStore } from '../components/ui/Toast';

export const DailyJournalPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToastStore();
  const todayStr = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(todayStr);

  const { data: dailyNotes, isLoading } = useQuery({
    queryKey: ['notes', { type: 'daily' }],
    queryFn: () => api.listNotes({ type: 'daily', sort: 'created_desc', limit: 60 }),
  });

  const openDailyMutation = useMutation({
    mutationFn: (date?: string) => api.openOrCreateDaily(date),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['taxonomy'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate(`/notes/${note.id}`);
    },
    onError: (err: Error) => {
      addToast({
        title: 'Failed to open daily entry',
        description: err.message,
        variant: 'error',
      });
    },
  });

  const entries = dailyNotes?.notes || [];

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-canvas-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Daily Engineering Journal
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Chronological log of daily learning, activities, problem solving, and progress.
          </p>
        </div>
        <Button
          variant="primary"
          loading={openDailyMutation.isPending}
          icon={<Plus size={16} />}
          onClick={() => openDailyMutation.mutate(undefined)}
        >
          Open Today&apos;s Entry ({todayStr})
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar / Date jump panel */}
        <div className="p-4 rounded-lg bg-canvas-surface border border-canvas-border space-y-4 h-fit">
          <div className="text-xs font-semibold text-text-muted uppercase tracking-wider">
            <span>Jump to Date</span>
          </div>
          <div className="space-y-2.5">
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-md bg-canvas-app border border-canvas-border text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-center"
              loading={openDailyMutation.isPending}
              onClick={() => openDailyMutation.mutate(selectedDate)}
            >
              Open / Create {selectedDate}
            </Button>
          </div>
        </div>

        {/* Entries list or initializer */}
        <div className="lg:col-span-3 space-y-4">
          {isLoading ? (
            <div className="p-12 rounded-lg bg-canvas-surface border border-canvas-border text-center text-xs text-text-muted">
              Loading daily journal entries...
            </div>
          ) : entries.length === 0 ? (
            <div className="p-6 rounded-lg bg-canvas-surface border border-canvas-border flex flex-col items-center justify-center py-20 text-center">
              <div className="w-12 h-12 rounded-xl bg-canvas-elevated flex items-center justify-center text-accent mb-3">
                <Calendar size={22} />
              </div>
              <h3 className="text-base font-semibold text-text-primary mb-1">
                Today&apos;s Log: {todayStr}
              </h3>
              <p className="text-xs text-text-secondary max-w-sm mb-4">
                Click below to initialize today&apos;s engineering journal from the Daily template.
              </p>
              <Button
                variant="primary"
                size="sm"
                loading={openDailyMutation.isPending}
                onClick={() => openDailyMutation.mutate(undefined)}
              >
                Initialize Entry
              </Button>
            </div>
          ) : (
            <div className="rounded-xl border border-canvas-border overflow-hidden bg-canvas-surface/30">
              {entries.map((entry) => (
                <NoteRow
                  key={entry.id}
                  note={entry}
                  onSelect={(id) => navigate(`/notes/${id}`)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
