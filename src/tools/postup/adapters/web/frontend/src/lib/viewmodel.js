// JS ↔ Python derive-parity projection (PRD 00065 shared-fixture seam).
//
// The postup Python derive layer (`src/tools/postup/domain/derive.py`) computes
// a NARROW deterministic view-model: per-repo summaries, a ranked attention
// queue keyed by (kind, urgency, headline), a small mechanical-todo subset, and
// a since-last diff. The JS derive (`derive.js`, ported from the SPA) computes a
// RICHER model — transparent scoring with reasons, a broad mechanical todo set.
//
// The two are deliberately not identical in breadth (the PRD names the Python
// side a "subset"). What MUST match, fixture-for-fixture, is the OVERLAP: the
// values both sides compute. This module projects the JS derive output into the
// exact shape the Python `ViewModel` serialises, so a parity test can assert
// equality directly. It is the JS half of the parity seam PRD 00068 deferred.
//
// This module is pure and framework-free.

import { slug, ciFailing } from './derive.js';

const _CI_FAIL = new Set(['failure', 'timed_out', 'startup_failure']);
const _DIRTY_ATTENTION_DAYS = 7;
const _IDLE_WIP_ATTENTION_DAYS = 14;
const _URGENCY_RANK = { now: 0, soon: 1, later: 2 };

const _failingCi = (repo) => (repo.ci ?? []).filter((w) => _CI_FAIL.has(w.conclusion)).length;

/**
 * Per-repo summary rows, sorted by slug — mirrors Python `_repo_summaries`.
 * @param {object} data the data.json payload.
 * @returns {object[]}
 */
export function repoSummaries(data) {
	const rows = (data.repos ?? []).map((repo) => ({
		repo: slug(repo),
		commits: repo.commit_count ?? 0,
		open_prs: (repo.prs ?? []).length,
		open_issues: (repo.issues ?? []).length,
		failing_ci: _failingCi(repo),
		alerts: (repo.security ?? []).length,
		unreleased: repo.unreleased_commits ?? 0,
		dirty: repo.local?.dirty ?? 0,
		errors: [...(repo.errors ?? [])]
	}));
	return rows.sort((a, b) => a.repo.localeCompare(b.repo));
}

/**
 * Ranked attention queue keyed by (urgency, repo, headline) — mirrors Python
 * `_attention_queue`. Same signals, same headlines, same total ordering.
 * @param {object} data the data.json payload.
 * @returns {object[]}
 */
export function attentionQueue(data) {
	const items = [];
	for (const repo of data.repos ?? []) {
		const s = slug(repo);
		const failing = _failingCi(repo);
		if (failing)
			items.push({ repo: s, urgency: 'now', headline: `${failing} failing CI workflow(s)`, kind: 'ci' });
		if ((repo.security ?? []).length)
			items.push({
				repo: s,
				urgency: 'now',
				headline: `${repo.security.length} open security alert(s)`,
				kind: 'security'
			});
		const reviewPrs = (repo.prs ?? []).filter((pr) => !pr.draft);
		if (reviewPrs.length)
			items.push({
				repo: s,
				urgency: 'soon',
				headline: `${reviewPrs.length} open PR(s) awaiting attention`,
				kind: 'review'
			});
		const local = repo.local;
		if (local && local.dirty && (local.dirty_since_days ?? 0) >= _DIRTY_ATTENTION_DAYS)
			items.push({
				repo: s,
				urgency: 'soon',
				headline: `${local.dirty} file(s) dirty for ${local.dirty_since_days}d`,
				kind: 'dirty'
			});
		if (repo.prds)
			for (const wip of repo.prds.wip ?? [])
				if ((wip.idle_days ?? 0) >= _IDLE_WIP_ATTENTION_DAYS)
					items.push({
						repo: s,
						urgency: 'later',
						headline: `WIP PRD idle ${wip.idle_days}d: ${wip.title}`,
						kind: 'wip-idle'
					});
	}
	for (const pr of data.external?.review_requested ?? [])
		items.push({
			repo: pr.repo,
			urgency: 'soon',
			headline: `review requested: #${pr.number} ${pr.title}`,
			kind: 'external-review'
		});
	return items.sort(
		(a, b) =>
			(_URGENCY_RANK[a.urgency] ?? 9) - (_URGENCY_RANK[b.urgency] ?? 9) ||
			a.repo.localeCompare(b.repo) ||
			a.headline.localeCompare(b.headline)
	);
}

/**
 * The deterministic mechanical-todo SUBSET the Python side emits, in the same
 * shape — mirrors Python `_mechanical_todos`. This is intentionally narrower
 * than JS `todosFor`; it is exactly the overlap the parity contract covers.
 * @param {object} data the data.json payload.
 * @returns {object[]}
 */
export function mechanicalTodos(data) {
	const todos = [];
	for (const repo of data.repos ?? []) {
		const s = slug(repo);
		if (repo.changelog_unreleased && repo.unreleased_commits)
			todos.push({
				repo: s,
				action: 'cut a release',
				why: `${repo.unreleased_commits} unreleased commit(s) with a CHANGELOG entry`,
				kind: 'mechanical',
				urgency: 'soon'
			});
		if (_failingCi(repo))
			todos.push({
				repo: s,
				action: 'fix failing CI',
				why: 'the default branch has a failing workflow',
				kind: 'mechanical',
				urgency: 'now'
			});
		if (repo.branches && (repo.branches.stray ?? []).length) {
			const merged = repo.branches.stray.filter((b) => b.merged).length;
			if (merged)
				todos.push({
					repo: s,
					action: 'prune merged branches',
					why: `${merged} merged stray branch(es)`,
					kind: 'mechanical',
					urgency: 'later'
				});
		}
	}
	return todos.sort(
		(a, b) =>
			(_URGENCY_RANK[a.urgency] ?? 9) - (_URGENCY_RANK[b.urgency] ?? 9) ||
			a.repo.localeCompare(b.repo) ||
			a.action.localeCompare(b.action)
	);
}

/**
 * The full normalized view-model, matching the Python `ViewModel` serialisation
 * used by the parity fixture. Judgment todos come from epics.json (appended
 * after the mechanical subset, matching the Python ordering).
 * @param {object|null} data data.json payload.
 * @param {object|null} epics epics.json payload, or null when not enriched.
 * @returns {object}
 */
export function viewModel(data, epics = null) {
	if (!data || !Array.isArray(data.repos))
		return {
			needs_collect: true,
			enriched: false,
			generated_at: '',
			summary: '',
			attention: [],
			todos: [],
			repos: [],
			since_last: emptySinceLast(),
			errors: []
		};
	const mech = mechanicalTodos(data);
	const judgment = epics != null ? judgmentTodos(epics) : [];
	return {
		needs_collect: false,
		enriched: epics != null,
		generated_at: data.generated_at ?? '',
		summary: epics != null ? String(epics.summary ?? '') : '',
		attention: attentionQueue(data),
		todos: [...mech, ...judgment],
		repos: repoSummaries(data),
		since_last: emptySinceLast(),
		errors: portfolioErrors(data)
	};
}

/**
 * Judgment todos lifted from epics.json — mirrors Python `_judgment_todos`.
 * @param {object} epics parsed epics.json.
 * @returns {object[]}
 */
export function judgmentTodos(epics) {
	const raw = epics?.todos;
	if (!Array.isArray(raw)) return [];
	const todos = [];
	for (const entry of raw) {
		if (!entry || typeof entry !== 'object') continue;
		const { repo, action } = entry;
		if (typeof repo !== 'string' || typeof action !== 'string') continue;
		todos.push({
			repo,
			action,
			why: typeof entry.why === 'string' ? entry.why : '',
			kind: 'judgment',
			urgency: typeof entry.urgency === 'string' ? entry.urgency : 'later'
		});
	}
	return todos.sort(
		(a, b) =>
			(_URGENCY_RANK[a.urgency] ?? 9) - (_URGENCY_RANK[b.urgency] ?? 9) ||
			a.repo.localeCompare(b.repo) ||
			a.action.localeCompare(b.action)
	);
}

/**
 * Portfolio-level (non per-repo) degradation messages — mirrors Python
 * `_portfolio_errors`.
 * @param {object} data data.json payload.
 * @returns {string[]}
 */
export function portfolioErrors(data) {
	const errors = [];
	if (data.external?.error) errors.push(`external PRs: ${data.external.error}`);
	return errors;
}

const emptySinceLast = () => ({
	has_prev: false,
	commits: 0,
	open_prs: 0,
	open_issues: 0,
	alerts: 0,
	failing_ci: 0,
	new_repos: [],
	gone_repos: []
});

// re-export so the parity test can spot-check the raw SPA derive too.
export { ciFailing };
