// @vitest-environment jsdom
// PRDs view component test (PRD 00066 Phase 1).
import { describe, it, expect } from 'vitest';
import Prds from './+page.svelte';
import { renderView } from '../_test-harness.js';
import data from '../../fixtures/data.json';

describe('PRDs view', () => {
	it('shows per-repo pipeline counts from the fixture', () => {
		const { getByText, container } = renderView(Prds, { data });
		const h2 = container.querySelector('h2').textContent.replace(/\s+/g, ' ');
		expect(h2).toMatch(/1 wip/);
		expect(h2).toMatch(/1 backlog/);
		expect(h2).toMatch(/3 done/);
		expect(getByText('buvis/gems')).toBeTruthy();
		expect(getByText(/stalled/)).toBeTruthy();
		expect(getByText(/idle 30d/)).toBeTruthy();
	});

	it('omits repos with no prds tree rather than zero-filling them', () => {
		// docs (prds: null) and a repo with an empty tree must not appear.
		const custom = {
			repos: [
				{ owner: 'buvis', name: 'gems', prds: { backlog: ['a'], wip: [], done_count: 0 } },
				{ owner: 'buvis', name: 'docs', prds: null },
				{ owner: 'buvis', name: 'empty', prds: { backlog: [], wip: [], done_count: 0 } }
			],
			since_days: 60,
			external: null,
			generated_at: ''
		};
		const { getByText, queryByText } = renderView(Prds, { data: custom });
		expect(getByText('buvis/gems')).toBeTruthy();
		expect(queryByText('buvis/docs')).toBeNull(); // no prds tree -> omitted
		expect(queryByText('buvis/empty')).toBeNull(); // empty tree -> omitted
	});

	it('shows an empty-state when no repo has a pipeline', () => {
		const { getByText } = renderView(Prds, {
			data: { repos: [{ owner: 'x', name: 'y', prds: null }], since_days: 60, external: null, generated_at: '' }
		});
		expect(getByText(/No PRD pipeline found in any repo/)).toBeTruthy();
	});
});
