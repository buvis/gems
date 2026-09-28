// @vitest-environment jsdom
// Work view component test (PRD 00066 Phase 1).
import { describe, it, expect } from 'vitest';
import Work from './+page.svelte';
import { renderView } from '../_test-harness.js';

const busy = {
	repos: [
		{
			owner: 'buvis',
			name: 'gems',
			default_branch: 'master',
			local: { branch: 'feat/x', dirty: 4, dirty_since_days: 9, ahead: 2, behind: 0, stashes: 1 },
			branches: { stray: [{ name: 'old', date: '2026-01-01', merged: true }], worktrees: ['/tmp/wt'] },
			prs: [{ number: 1, title: 'feat: y', author: 'bob', created: null, draft: false, labels: [] }]
		},
		{ owner: 'buvis', name: 'docs', default_branch: 'main', local: null, branches: null, prs: [] }
	],
	external: {
		review_requested: [{ repo: 'other/thing', number: 77, title: 'please review', created: null, url: 'u', draft: false }],
		authored: []
	},
	since_days: 60,
	generated_at: ''
};

describe('Work view', () => {
	it('groups in-flight work by repo and omits clean repos', () => {
		const { getByText, queryByText, container } = renderView(Work, { data: busy });
		expect(getByText(/In flight · 1 repo/)).toBeTruthy();
		const card = container.querySelector('.card');
		expect(card?.textContent).toMatch(/buvis\/gems/);
		expect(card?.textContent).toMatch(/4 dirty \(9d\)/);
		expect(card?.textContent).toMatch(/2 unpushed/);
		expect(card?.textContent).toMatch(/worktree \/tmp\/wt/);
		// docs is clean -> not a card
		expect(queryByText('buvis/docs')).toBeNull();
	});

	it('lists external review-requested / authored PRs', () => {
		const { getByText, container } = renderView(Work, { data: busy });
		const heads = [...container.querySelectorAll('h2')].map((h) => h.textContent.replace(/\s+/g, ' ').trim());
		expect(heads.some((t) => /Waiting on you elsewhere.*1/.test(t))).toBe(true);
		expect(getByText(/#77 please review/)).toBeTruthy();
	});

	it('shows a "clean" empty state when nothing is in flight', () => {
		const clean = {
			repos: [{ owner: 'buvis', name: 'docs', default_branch: 'main', local: null, branches: null, prs: [] }],
			external: { review_requested: [], authored: [] },
			since_days: 60,
			generated_at: ''
		};
		const { getByText } = renderView(Work, { data: clean });
		expect(getByText(/✓ Clean\. No local WIP/)).toBeTruthy();
	});

	it('surfaces an external-lookup error instead of the PR list', () => {
		const errored = {
			repos: [],
			external: { review_requested: [], authored: [], error: 'gh auth login' },
			since_days: 60,
			generated_at: ''
		};
		const { getByText } = renderView(Work, { data: errored });
		expect(getByText(/Could not check external PRs: gh auth login/)).toBeTruthy();
	});
});
