import { HealthStatus, TaxonomyCounts } from '../types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorData: { error?: { message?: string; details?: unknown } } = {};
    try {
      errorData = await response.json();
    } catch {
      // ignore json parse error
    }
    const message = errorData.error?.message || response.statusText || 'API Request failed';
    throw new ApiError(response.status, message, errorData.error?.details);
  }

  return response.json();
}

export const api = {
  getHealth: () => request<HealthStatus>('/system/health'),
  getTaxonomy: () => request<TaxonomyCounts>('/taxonomy'),
};
