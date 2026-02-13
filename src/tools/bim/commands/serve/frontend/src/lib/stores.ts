import { writable } from 'svelte/store';
import type { ExecResult } from './api';

export const queries = writable<Record<string, string>>({});
export const activeQuery = writable<string | null>(null);
export const queryResult = writable<ExecResult | null>(null);
export const loading = writable(false);
export const error = writable<string | null>(null);
export const selectedRow = writable<Record<string, unknown> | null>(null);
