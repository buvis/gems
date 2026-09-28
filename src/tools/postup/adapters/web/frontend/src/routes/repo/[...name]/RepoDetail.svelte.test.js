// @vitest-environment jsdom
// RepoDetail component test (PRD 00066 Phase 2).
// Mounts the prop-driven detail component directly (no router needed).
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import RepoDetail from './RepoDetail.svelte';

const degraded = {
	owner: 'buvis',
	name: 'gems',
	default_branch: 'master',
	description: 'the monorepo',
	commit_count: 1,
	commits: [{ sha: 'abc1234', date: '2026-09-20', subject: 'feat: x' }],
	prs: [{ number: 1, title: 'feat: y', author: 'bob', created: null, draft: false, labels: [] }],
	issues: [],
	ci: [{ workflow: 'test', status: 'completed', conclusion: 'failure', url: 'u', date: null }],
	security: [],
	errors: [
		'gh api graphql: 502 Bad Gateway (query: securityVulnerabilities)',
		'ci: workflow list truncated at 100'
	]
};

describe('RepoDetail', () => {
	it('renders a degraded repo\'s errors[] VERBATIM', () => {
		const { getByText, container } = render(RepoDetail, { props: { repo: degraded, epics: null } });
		expect(getByText(/Collection warnings · 2/)).toBeTruthy();
		// verbatim: the exact collector message, not a summarised one
		expect(getByText('gh api graphql: 502 Bad Gateway (query: securityVulnerabilities)')).toBeTruthy();
		expect(getByText('ci: workflow list truncated at 100')).toBeTruthy();
		// rest of the page is intact around the warnings
		expect(container.textContent).toMatch(/buvis\/gems/);
		expect(container.textContent).toMatch(/#1 feat: y/);
	});

	it('renders a clean repo with no warnings section', () => {
		const clean = { owner: 'buvis', name: 'docs', default_branch: 'main', commit_count: 0, commits: [], errors: [] };
		const { queryByText, container } = render(RepoDetail, { props: { repo: clean, epics: null } });
		expect(queryByText(/Collection warnings/)).toBeNull();
		expect(container.textContent).toMatch(/buvis\/docs/);
		expect(container.textContent).toMatch(/No commits in window/);
	});
});
