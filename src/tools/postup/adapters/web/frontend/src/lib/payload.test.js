// Payload loader seam tests (PRD 00065 Phase 1).
// Covers: fixture (dev) mode via toState, prod fetch mode (mocked fetch),
// missing epics.json degradation, and soft-fail into needs-collect.
import { describe, it, expect } from 'vitest';
import { loadPayload, toState } from './payload.js';
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
});

describe('loadPayload — dev fixture mode', () => {
	it('loads the committed fixtures and enriches from epics.json', async () => {
		const s = await loadPayload({ dev: true });
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(true);
		expect(s.payload.repos.length).toBeGreaterThan(0);
	});
});

describe('loadPayload — prod fetch mode', () => {
	const okJson = (body) => ({ ok: true, json: async () => body });

	it('fetches data, epics, and prev from the /api endpoints', async () => {
		const seen = [];
		const fetchImpl = async (url) => {
			seen.push(url);
			if (url === '/api/data') return okJson(data);
			if (url === '/api/epics') return okJson(epics);
			if (url === '/api/data-prev') return okJson(data);
			return { ok: false };
		};
		const s = await loadPayload({ dev: false, fetchImpl });
		expect(seen).toContain('/api/data');
		expect(s.needsCollect).toBe(false);
		expect(s.enriched).toBe(true);
		expect(s.payload.prev).not.toBeNull();
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
