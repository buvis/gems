// @vitest-environment jsdom
// Activity view component test (PRD 00066 Phase 1).
import { describe, it, expect } from 'vitest';
import Activity from './+page.svelte';
import { renderView } from '../_test-harness.js';

const day = (d) => new Date(Date.now() - d * 86400000).toISOString().slice(0, 10);

const data = {
	repos: [
		{
			owner: 'buvis',
			name: 'gems',
			commit_count: 3,
			commits: [{ date: day(1) }, { date: day(2) }, { date: day(10) }],
			releases: [{ tag: 'v1.2.0', name: 'v1.2.0', date: '2026-09-20', prerelease: false }],
			errors: []
		},
		{
			owner: 'buvis',
			name: 'docs',
			commit_count: 0,
			commits: [],
			releases: [],
			errors: ['gh api: 403 rate limited', 'ci: could not resolve default branch']
		}
	],
	since_days: 60,
	external: null,
	generated_at: '2026-09-28T10:00:00+00:00'
};

describe('Activity view', () => {
	it('renders the commit-heat grid for repos with activity', () => {
		const { getByText } = renderView(Activity, { data });
		expect(getByText(/Commit heat · 1 active repos/)).toBeTruthy();
		expect(getByText('gems')).toBeTruthy();
	});

	it('lists recent releases most-recent-first', () => {
		const { getByText } = renderView(Activity, { data });
		expect(getByText(/Recent releases · 1/)).toBeTruthy();
		expect(getByText('v1.2.0')).toBeTruthy();
	});

	it('surfaces a degraded repo as an inline error badge, not a gap', () => {
		const { getByText, container } = renderView(Activity, { data });
		expect(getByText(/Collection warnings · 1/)).toBeTruthy();
		const badge = container.querySelector('.errbadge');
		expect(badge?.textContent).toMatch(/buvis\/docs/);
		expect(badge?.textContent).toMatch(/⚠ 2/); // both error lines counted
	});

	it('shows an empty-state when nothing was collected', () => {
		const { getByText } = renderView(Activity, {
			data: { repos: [], since_days: 60, external: null, generated_at: '' }
		});
		expect(getByText(/No commits in the last 60 days/)).toBeTruthy();
		expect(getByText(/No releases collected/)).toBeTruthy();
	});
});
