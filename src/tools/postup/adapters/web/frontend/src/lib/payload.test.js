// Payload loader seam tests (PRD 00065 Phase 1).
// Covers: fixture (dev) mode via toState, prod fetch mode (mocked fetch),
// missing epics.json degradation, and soft-fail into needs-collect.
import { describe, it, expect } from 'vitest';
import { loadPayload, toState, parseHistory } from './payload.js';
import data from '../fixtures/data.json';
import epics from '../fixtures/epics.json';

describe('toState', () => {
	it('normalises a data.json + epics into an enriched state', () => {
		const s = toState(data, epics);
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(true);
		expect(s.payload.repos.length).toBe(data.repos.length);
		expect(s.payload.since_days).toBe(60);
		expect(s.payload.epics).not.toBeNull();
	});

	it('degrades to not-enriched when epics is absent', () => {
		const s = toState(data, null);
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(false);
		expect(s.payload.epics).toBeNull();
	});

	it('returns needs-collect for a null or shapeless payload', () => {
		expect(toState(null).needsCollect).toBe(true);
		expect(toState({}).needsCollect).toBe(true);
		expect(toState({ repos: 'nope' }).needsCollect).toBe(true);
	});

	it('threads prev and history through, defaulting history to an empty array', () => {
		const bare = toState(data, null);
		expect(bare.payload.prev).toBeNull();
		expect(bare.payload.history).toEqual([]);
		const full = toState(data, epics, data, [{ at: 't', repos: {} }]);
		expect(full.payload.prev).not.toBeNull();
		expect(full.payload.history).toHaveLength(1);
	});
});

describe('parseHistory', () => {
	it('parses newline-delimited json lines, skipping blanks', () => {
		const text = '{"at":"a","repos":{}}\n\n{"at":"b","repos":{}}\n';
		expect(parseHistory(text).map((h) => h.at)).toEqual(['a', 'b']);
	});

	it('skips a torn / corrupt line rather than failing the whole load', () => {
		const text = '{"at":"a","repos":{}}\n{"at":\n{"at":"c","repos":{}}';
		expect(parseHistory(text).map((h) => h.at)).toEqual(['a', 'c']);
	});

	it('degrades to [] for blank, whitespace, or non-string input', () => {
		expect(parseHistory('')).toEqual([]);
		expect(parseHistory('   \n  ')).toEqual([]);
		expect(parseHistory(null)).toEqual([]);
		expect(parseHistory(undefined)).toEqual([]);
	});

	it('keeps only the most recent `cap` lines', () => {
		const text = Array.from({ length: 5 }, (_, i) => `{"at":"${i}","repos":{}}`).join('\n');
		expect(parseHistory(text, 2).map((h) => h.at)).toEqual(['3', '4']);
	});
});

describe('loadPayload — dev fixture mode', () => {
	it('loads the committed fixtures and enriches from epics.json', async () => {
		const s = await loadPayload({ dev: true });
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(true);
		expect(s.payload.repos.length).toBeGreaterThan(0);
	});

	it('loads the rotated prev snapshot and the history series from fixtures', async () => {
		const s = await loadPayload({ dev: true });
		expect(s.payload.prev).not.toBeNull();
		expect(s.payload.prev.repos.length).toBeGreaterThan(0);
		expect(s.payload.history.length).toBeGreaterThanOrEqual(2);
		expect(s.payload.history.every((h) => typeof h.at === 'string')).toBe(true);
	});
});

describe('loadPayload — prod fetch mode', () => {
	const okJson = (body) => ({ ok: true, json: async () => body });

	it('fetches data, epics, prev, and history from the /api endpoints', async () => {
		const seen = [];
		const fetchImpl = async (url) => {
			seen.push(url);
			if (url === '/api/data') return okJson(data);
			if (url === '/api/epics') return okJson(epics);
			if (url === '/api/data-prev') return okJson(data);
			if (url === '/api/history')
				return { ok: true, text: async () => '{"at":"h1","repos":{}}\n{"at":"h2","repos":{}}' };
			return { ok: false };
		};
		const s = await loadPayload({ dev: false, fetchImpl });
		expect(seen).toContain('/api/data');
		expect(seen).toContain('/api/history');
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(true);
		expect(s.payload.prev).not.toBeNull();
		expect(s.payload.history.map((h) => h.at)).toEqual(['h1', 'h2']);
	});

	it('degrades to an empty history when the history endpoint is absent', async () => {
		const fetchImpl = async (url) => {
			if (url === '/api/data') return okJson(data);
			return { ok: false };
		};
		const s = await loadPayload({ dev: false, fetchImpl });
		expect(s.payload.history).toEqual([]);
	});

	it('degrades to not-enriched when the epics endpoint is absent (00067 not shipped)', async () => {
		const fetchImpl = async (url) => {
			if (url === '/api/data') return okJson(data);
			return { ok: false }; // no epics/prev endpoints yet
		};
		const s = await loadPayload({ dev: false, fetchImpl });
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(false);
		expect(s.payload.epics).toBeNull();
	});

	it('soft-fails into needs-collect when the data endpoint is unreachable', async () => {
		const fetchImpl = async () => {
			throw new Error('ECONNREFUSED');
		};
		const s = await loadPayload({ dev: false, fetchImpl });
		expect(s.needsCollect).toBe(true);
	});

	it('soft-fails into needs-collect when no fetch is available', async () => {
		const s = await loadPayload({ dev: false, fetchImpl: undefined });
		expect(s.needsCollect).toBe(true);
	});
});
