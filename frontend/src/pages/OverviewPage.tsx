import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Plus, BookOpen, Clock, Activity } from 'lucide-react';
import { api } from '../api/client';
import { useUIStore } from '../store/useUIStore';
import { Button } from '../components/ui/Button';
import { NoteRow } from '../components/notes/NoteRow';
import { useToastStore } from '../components/ui/Toast';

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { openNewNoteModal } = useUIStore();
  const { addToast } = useToastStore();

  const { data: dashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.getDashboard,
  });

  const dailyMutation = useMutation({
    mutationFn: () => api.openOrCreateDaily(),
    onSuccess: (note) => {
      navigate(`/notes/${note.id}`);
    },
    onError: (err: Error) => {
      addToast({
        title: 'Failed to open daily journal',
        description: err.message,
        variant: 'error',
      });
    },
  });

  const counts = dashboard?.counts || {
    total_notes: 0,
    experiments: 0,
    troubleshooting: 0,
    projects: 0,
    daily: 0,
    snippets: 0,
  };

  const statCards = [
    { label: 'Total Notes', count: counts.total_notes, path: '/notes', color: 'text-text-primary' },
    { label: 'Experiments', count: counts.experiments, path: '/experiments', color: 'text-indigo-400' },
    { label: 'Troubleshooting', count: counts.troubleshooting, path: '/troubleshooting', color: 'text-amber-400' },
    { label: 'Projects', count: counts.projects, path: '/projects', color: 'text-emerald-400' },
  ];

  const quickTemplates = [
    { name: 'General Note', templateId: 'general', type: 'note' as const, desc: 'Concept, learning or reference note' },
    { name: 'Experiment', templateId: 'experiment', type: 'experiment' as const, desc: 'Structured lab benchmark or test' },
    { name: 'Troubleshooting', templateId: 'troubleshooting', type: 'troubleshooting' as const, desc: 'Incident diagnosis and root cause' },
    { name: 'Project', templateId: 'project', type: 'project' as const, desc: 'Engineering project plan & progress' },
  ];

  const recentlyOpened = dashboard?.recently_opened || [];
  const recentlyUpdated = dashboard?.recently_updated || [];

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      {/* Top Greeting & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-canvas-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Engineering Overview
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Welcome to your local engineering knowledge vault.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="md"
            loading={dailyMutation.isPending}
            icon={<Clock size={16} />}
            onClick={() => dailyMutation.mutate()}
          >
            Today&apos;s Journal
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Plus size={16} />}
            onClick={() => openNewNoteModal()}
          >
            New Note
          </Button>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            onClick={() => navigate(card.path)}
            className="p-4 rounded-lg bg-canvas-surface border border-canvas-border hover:border-canvas-border/80 hover:bg-canvas-elevated transition-all cursor-pointer shadow-sm group"
          >
            <span className="text-xs font-medium text-text-muted uppercase tracking-wider block mb-1">
              {card.label}
            </span>
            <div className="flex items-baseline justify-between">
              <span className={`text-2xl font-bold font-mono ${card.color}`}>
                {card.count}
              </span>
              <span className="text-xs text-text-muted group-hover:text-accent transition-colors">
                View &rarr;
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Capture Templates */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider flex items-center gap-2">
          <BookOpen size={16} />
          <span>Quick Capture Templates</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {quickTemplates.map((tmpl) => (
            <div
              key={tmpl.templateId}
              onClick={() =>
                openNewNoteModal({
                  template: tmpl.templateId,
                  noteType: tmpl.type,
                })
              }
              className="p-3.5 rounded-lg bg-canvas-surface/70 border border-canvas-border hover:border-accent/40 hover:bg-canvas-elevated transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-text-primary group-hover:text-accent transition-colors">
                  {tmpl.name}
                </span>
                <Plus size={14} className="text-text-muted group-hover:text-accent" />
              </div>
              <p className="text-xs text-text-secondary line-clamp-1">{tmpl.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Two-Column Activity & Reading Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Continue Reading */}
        <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <BookOpen size={16} className="text-text-muted" />
              <span>Continue Reading</span>
            </h3>
            <span className="text-xs text-text-muted">Recently Opened</span>
          </div>
          {recentlyOpened.length === 0 ? (
            <div className="py-8 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-md">
              No recently opened notes. Open any note to pin it here.
            </div>
          ) : (
            <div className="rounded-lg border border-canvas-border overflow-hidden">
              {recentlyOpened.map((note) => (
                <NoteRow
                  key={note.id}
                  note={note}
                  compact
                  onSelect={(id) => navigate(`/notes/${id}`)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="p-5 rounded-lg bg-canvas-surface border border-canvas-border space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Activity size={16} className="text-text-muted" />
              <span>Recent Activity</span>
            </h3>
            <span className="text-xs text-text-muted">Vault Updates</span>
          </div>
          {recentlyUpdated.length === 0 ? (
            <div className="py-8 text-center text-xs text-text-muted border border-dashed border-canvas-border rounded-md">
              No note activity recorded yet.
            </div>
          ) : (
            <div className="rounded-lg border border-canvas-border overflow-hidden">
              {recentlyUpdated.map((note) => (
                <NoteRow
                  key={note.id}
                  note={note}
                  compact
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
