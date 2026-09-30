// @vitest-environment jsdom
// Meta-budget tile test (PRD 00072 Phase 1, web surface).
// Covers: percentage + within-ceiling (green) state, over-ceiling (red) state,
// and the "meta n/a" path when the snapshot is absent/unavailable.
import { describe, it, expect, beforeEach } from 'vitest';
import Brief from './+page.svelte';
import { renderView, installMemoryStorage } from './_test-harness.js';
import baseData from '../fixtures/data.json';

const withMeta = (meta) => ({ ...baseData, meta_share: meta });

describe('Brief — meta-budget tile', () => {
	beforeEach(installMemoryStorage);

	it('renders the tile header', () => {
		const { getByText } = renderView(Brief, { data: baseData });
		expect(getByText('Meta budget')).toBeTruthy();
	});

	it('shows the rounded percentage and within-ceiling state when under the ceiling', () => {
		const data = withMeta({
			available: true,
			meta_pct: 27.0,
			total_usd: 123.45,
			meta_usd: 33.33,
			window_days: 30,
			ceiling_pct: 30.0,
			over_ceiling: false
		});
		const { getByTestId, container } = renderView(Brief, { data });
		const pct = getByTestId('meta-pct');
		expect(pct.textContent).toBe('27%');
		expect(pct.classList.contains('sev-good')).toBe(true);
		expect(container.textContent).toMatch(/within ceiling/i);
	});

	it('shows the red over-ceiling state at or above the ceiling', () => {
		const data = withMeta({
			available: true,
			meta_pct: 30.0,
			total_usd: 100.0,
			meta_usd: 30.0,
			window_days: 30,
			ceiling_pct: 30.0,
			over_ceiling: true
		});
		const { getByTestId, container } = renderView(Brief, { data });
		const pct = getByTestId('meta-pct');
		expect(pct.textContent).toBe('30%');
		expect(pct.classList.contains('sev-critical')).toBe(true);
		expect(container.textContent).toMatch(/over 30% ceiling/i);
	});

	it('renders "meta n/a" when the share is unavailable', () => {
		const data = withMeta({
			available: false,
			meta_pct: 0.0,
			total_usd: 0.0,
			meta_usd: 0.0,
			window_days: 30,
			ceiling_pct: 30.0,
			over_ceiling: false
		});
		const { getByTestId } = renderView(Brief, { data });
		expect(getByTestId('meta-na').textContent).toMatch(/meta n\/a/i);
	});

	it('renders "meta n/a" when meta_share is absent from the payload', () => {
		const data = { ...baseData };
		delete data.meta_share;
		const { getByTestId } = renderView(Brief, { data });
		expect(getByTestId('meta-na').textContent).toMatch(/meta n\/a/i);
	});
});
