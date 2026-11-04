import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { api } from '../../api/client';
import { useUIStore } from '../../store/useUIStore';
import {
  CreateNoteRequest,
  KnowledgeDomain,
  NoteStatus,
  NoteType,
} from '../../types';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { useToastStore } from '../ui/Toast';

const ALL_DOMAINS: KnowledgeDomain[] = [
  'Networking',
  'Linux',
  'Programming',
  'IoT',
  'Cybersecurity',
  'Homelab',
  'Mathematics',
];

const NOTE_TYPE_OPTIONS = [
  { value: 'note', label: 'General Note' },
  { value: 'experiment', label: 'Experiment' },
  { value: 'troubleshooting', label: 'Troubleshooting' },
  { value: 'project', label: 'Project' },
  { value: 'daily', label: 'Daily Journal' },
  { value: 'snippet', label: 'Snippet' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'None (No Status)' },
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'investigating', label: 'Investigating' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
];

const FOLDER_OPTIONS = [
  { value: '00-Inbox', label: '00-Inbox' },
  { value: '10-Notes', label: '10-Notes' },
  { value: '20-Projects', label: '20-Projects' },
  { value: '30-Experiments', label: '30-Experiments' },
  { value: '40-Troubleshooting', label: '40-Troubleshooting' },
  { value: '50-Snippets', label: '50-Snippets' },
  { value: '90-Daily', label: '90-Daily' },
];

const TYPE_TO_TEMPLATE_ID: Record<string, string> = {
  note: 'general',
  general: 'general',
  experiment: 'experiment',
  troubleshooting: 'troubleshooting',
  project: 'project',
  daily: 'daily',
};

export const NewNoteModal: React.FC = () => {
  const { isNewNoteModalOpen, newNoteDefaults, closeNewNoteModal } = useUIStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToastStore();

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: api.getTemplates,
    enabled: isNewNoteModalOpen,
  });

  const [title, setTitle] = useState('');
  const [templateId, setTemplateId] = useState<string>('general');
  const [noteType, setNoteType] = useState<NoteType>('note');
  const [status, setStatus] = useState<NoteStatus | ''>('');
  const [folder, setFolder] = useState<string>('10-Notes');
  const [domains, setDomains] = useState<KnowledgeDomain[]>([]);
  const [tagsInput, setTagsInput] = useState('');

  useEffect(() => {
    if (!isNewNoteModalOpen) return;

    const initialTplId =
      (newNoteDefaults.template && TYPE_TO_TEMPLATE_ID[newNoteDefaults.template]) ||
      (newNoteDefaults.noteType && TYPE_TO_TEMPLATE_ID[newNoteDefaults.noteType]) ||
      'general';

    setTemplateId(initialTplId);
    const tpl = templatesData?.templates.find((t) => t.id === initialTplId);
    if (tpl) {
      setNoteType(newNoteDefaults.noteType || tpl.note_type);
      setStatus(tpl.default_status ?? '');
      setFolder(tpl.folder);
    } else {
      const defType = newNoteDefaults.noteType || 'note';
      setNoteType(defType);
      setStatus(
        defType === 'note'
          ? ''
          : defType === 'troubleshooting'
          ? 'investigating'
          : 'active'
      );
      setFolder(
        defType === 'experiment'
          ? '30-Experiments'
          : defType === 'troubleshooting'
          ? '40-Troubleshooting'
          : defType === 'project'
          ? '20-Projects'
          : defType === 'daily'
          ? '90-Daily'
          : '10-Notes'
      );
    }

    setTitle('');
    setDomains(newNoteDefaults.domain ? [newNoteDefaults.domain] : []);
    setTagsInput('');
  }, [isNewNoteModalOpen, newNoteDefaults, templatesData]);

  const handleTemplateSelect = (selectedId: string) => {
    setTemplateId(selectedId);
    const tpl = templatesData?.templates.find((t) => t.id === selectedId);
    if (tpl) {
      setNoteType(tpl.note_type);
      setStatus(tpl.default_status ?? '');
      setFolder(tpl.folder);
    }
  };

  const toggleDomain = (domain: KnowledgeDomain) => {
    setDomains((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );
  };

  const createMutation = useMutation({
    mutationFn: (payload: CreateNoteRequest) => api.createNote(payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['taxonomy'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast({
        title: 'Note created',
        description: `Created "${created.title}" in ${created.folder}`,
        variant: 'success',
      });
      closeNewNoteModal();
      navigate(`/notes/${created.id}`);
    },
    onError: (err: Error) => {
      addToast({
        title: 'Failed to create note',
        description: err.message,
        variant: 'error',
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) return;

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const payload: CreateNoteRequest = {
      title: cleanTitle,
      template_id: templateId || null,
      note_type: noteType,
      status: status === '' ? null : status,
      folder,
      domains,
      tags,
    };

    createMutation.mutate(payload);
  };

  return (
    <Modal
      open={isNewNoteModalOpen}
      onClose={closeNewNoteModal}
      title="Create New Engineering Note"
      description="Instantiate a structured Markdown note in your local vault."
      maxWidth="lg"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={closeNewNoteModal}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={createMutation.isPending}
            disabled={!title.trim()}
            onClick={handleSubmit}
          >
            Create Note
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Title"
          placeholder="e.g. WireGuard Site-to-Site MTU Clamping"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          autoFocus
        />

        {/* Template Selector */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">
            Template
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
            {(
              templatesData?.templates || [
                { id: 'general', name: 'General Note' },
                { id: 'experiment', name: 'Experiment' },
                { id: 'troubleshooting', name: 'Troubleshooting' },
                { id: 'project', name: 'Project' },
                { id: 'daily', name: 'Daily Journal' },
              ]
            ).map((tpl) => (
              <button
                key={tpl.id}
                type="button"
                onClick={() => handleTemplateSelect(tpl.id)}
                className={clsx(
                  'px-2.5 py-1.5 text-xs rounded-md border text-center transition-colors truncate',
                  templateId === tpl.id
                    ? 'bg-accent/15 border-accent text-accent font-medium'
                    : 'bg-canvas-surface border-canvas-border text-text-secondary hover:text-text-primary'
                )}
              >
                {tpl.name}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Select
            label="Note Type"
            options={NOTE_TYPE_OPTIONS}
            value={noteType}
            onChange={(e) => setNoteType(e.target.value as NoteType)}
          />
          <Select
            label="Status"
            options={STATUS_OPTIONS}
            value={status}
            onChange={(e) => setStatus(e.target.value as NoteStatus | '')}
          />
          <Select
            label="Vault Folder"
            options={FOLDER_OPTIONS}
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
          />
        </div>

        {/* Domains */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">
            Knowledge Domains
          </label>
          <div className="flex flex-wrap gap-1.5">
            {ALL_DOMAINS.map((dom) => {
              const selected = domains.includes(dom);
              return (
                <button
                  key={dom}
                  type="button"
                  onClick={() => toggleDomain(dom)}
                  className={clsx(
                    'px-2.5 py-1 rounded text-xs border transition-colors',
                    selected
                      ? 'bg-accent/15 border-accent text-accent font-medium'
                      : 'bg-canvas-surface border-canvas-border text-text-secondary hover:text-text-primary'
                  )}
                >
                  {dom}
                </button>
              );
            })}
          </div>
        </div>

        <Input
          label="Tags (comma-separated)"
          placeholder="e.g. wireguard, mtu, linux-kernel"
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
        />
      </form>
    </Modal>
  );
};
