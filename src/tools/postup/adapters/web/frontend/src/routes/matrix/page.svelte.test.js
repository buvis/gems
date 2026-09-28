// @vitest-environment jsdom
// Matrix view component test (PRD 00066 Phase 1).
// Mounts the real route against fixture payloads via the portfolio context.
import { describe, it, expect, beforeEach } from 'vitest';
import Matrix from './+page.svelte';
import { renderView, installMemoryStorage } from '../_test-harness.js';
import data from '../../fixtures/data.json';
import epics from '../../fixtures/epics.json';

describe('Matrix view', () => {
	beforeEach(installMemoryStorage);

	it('plots the four Eisenhower quadrants from the enriched fixture', () => {
		const { getByText, container } = renderView(Matrix, { data, epics });
		expect(getByText(/Do now ·/)).toBeTruthy();
		expect(getByText(/Schedule ·/)).toBeTruthy();
		expect(getByText(/Delegate to agents ·/)).toBeTruthy();
		expect(getByText(/Drop \/ batch ·/)).toBeTruthy();
		// gems has a failing-CI todo (now + high importance) -> Do now quadrant
		expect(container.querySelector('.q-do')?.textContent).toMatch(/Fix failing CI/);
	});

	it('falls back to a mechanical list with a "not enriched" cue when epics is absent', () => {
		const { getByText, queryByText } = renderView(Matrix, { data, epics: null });
		expect(getByText(/not enriched · mechanical todos only/)).toBeTruthy();
		// mechanical CI todo still plots; no judgment todo appears
		expect(getByText(/Fix failing CI/)).toBeTruthy();
		expect(queryByText(/Resume the parked PRD/)).toBeNull();
	});

	it('does not show the not-enriched cue when enrichment is present', () => {
		const { queryByText } = renderView(Matrix, { data, epics });
		expect(queryByText(/not enriched/)).toBeNull();
	});
});
