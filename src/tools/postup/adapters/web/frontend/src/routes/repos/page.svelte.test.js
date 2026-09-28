// @vitest-environment jsdom
// Repos view since-last-badge test (PRD 00066 Phase 2 — diff on Repos).
import { describe, it, expect } from 'vitest';
import Repos from './+page.svelte';
import { renderView } from '../_test-harness.js';
import data from '../../fixtures/data.json';
import prev from '../../fixtures/data-prev.json';

describe('Repos view — since-last badges', () => {
	it('shows a per-repo score-delta badge when a prev snapshot exists', () => {
		const { container } = renderView(Repos, { data, prev });
		const badges = container.querySelectorAll('.delta');
		expect(badges.length).toBeGreaterThanOrEqual(1);
		// gems got worse vs the calmer prev -> an upward (critical) delta
		const text = [...badges].map((b) => b.textContent.replace(/\s+/g, ' ').trim());
		expect(text.some((t) => /▲/.test(t))).toBe(true);
	});

	it('shows no diff badges on the first run (no prev)', () => {
		const { container } = renderView(Repos, { data, prev: null });
		expect(container.querySelectorAll('.delta')).toHaveLength(0);
	});

	it('links each repo card to its drill-down', () => {
		const { container } = renderView(Repos, { data });
		const link = container.querySelector('.cname');
		expect(link?.getAttribute('href')).toMatch(/^\/repo\//);
	});
});
