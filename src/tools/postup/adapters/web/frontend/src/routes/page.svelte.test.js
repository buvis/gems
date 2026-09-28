// @vitest-environment jsdom
// Brief view temporal-feature test (PRD 00066 Phase 2).
// Covers the Attention Horizon strip, since-last diff (with-prev/without-prev),
// and the trend sparkline (thin history = single dot).
import { describe, it, expect } from 'vitest';
import Brief from './+page.svelte';
import { renderView, installMemoryStorage } from './_test-harness.js';
import { beforeEach } from 'vitest';
import data from '../fixtures/data.json';
import prev from '../fixtures/data-prev.json';

const history = [
	{ at: '2026-09-25T10:00:00+00:00', skipped: 0, repos: { 'buvis/gems': { i: 1, p: 1, a: 1, f: 1 } } },
	{ at: '2026-09-27T10:00:00+00:00', skipped: 0, repos: { 'buvis/gems': { i: 1, p: 1, a: 0, f: 0 } } },
	{ at: '2026-09-28T10:00:00+00:00', skipped: 0, repos: { 'buvis/gems': { i: 1, p: 2, a: 1, f: 1 } } }
];

describe('Brief — temporal features', () => {
	beforeEach(installMemoryStorage);

	it('renders the attention horizon strip ranking repos that need you', () => {
		const { getByText, container } = renderView(Brief, { data });
		expect(getByText('Attention horizon')).toBeTruthy();
		// gems is burning in the fixture -> appears in the horizon strip
		const horizon = container.querySelector('.horizon');
		expect(horizon?.textContent).toMatch(/buvis\/gems/);
	});

	it('shows since-last diff badges and movers when a prev snapshot exists', () => {
		const { getByText, container } = renderView(Brief, { data, prev, history });
		expect(getByText('Since last brief')).toBeTruthy();
		expect(container.textContent).toMatch(/cleared/);
		expect(container.textContent).toMatch(/new/);
		// gems got worse vs the calmer prev -> a mover row exists
		expect(container.querySelector('.mover')).toBeTruthy();
	});

	it('renders no since-last section on the first run (no prev)', () => {
		const { queryByText } = renderView(Brief, { data, prev: null });
		expect(queryByText('Since last brief')).toBeNull();
	});

	it('renders a single history point as a dot sparkline, not an error', () => {
		const thin = [{ at: 't', skipped: 0, repos: { 'buvis/gems': { i: 1, p: 0, a: 0, f: 0 } } }];
		const { container, getByText } = renderView(Brief, { data, prev, history: thin });
		const svg = container.querySelector('.trend svg');
		expect(svg).toBeTruthy();
		expect(svg.querySelector('circle.dot')).toBeTruthy(); // dot, not polyline
		expect(svg.querySelector('polyline')).toBeNull();
		expect(getByText(/one brief so far/)).toBeTruthy();
	});

	it('draws a polyline once there are two or more complete history runs', () => {
		const { container } = renderView(Brief, { data, prev, history });
		const svg = container.querySelector('.trend svg');
		expect(svg.querySelector('polyline')).toBeTruthy();
	});
});
