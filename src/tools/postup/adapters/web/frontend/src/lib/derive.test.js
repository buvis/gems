// Regression check for the signal->score->todo pipeline.
//
// Ported from the brief-portfolio SPA's `lib/derive.test.js` (node:assert ->
// vitest). Dropped from the SPA suite: the AUDIT_CADENCE / auditTodos
// assertions — those drive Claude-skill maintenance nags off fields
// (`purge_last_run`, `external.audit_cadence`) that do not exist in postup's
// `data.json` contract, so the corresponding derive code was not ported. Every
// other SPA assertion is preserved.
import { describe, it, expect } from 'vitest';
import {
	attention,
	todosFor,
	wipItems,
	quadrant,
	externalTodos,
	allTodos,
	quickWins,
	sinceLast,
	diffSinceLast,
	trendSeries,
	attentionHorizon,
	safeUrl,
	aggregate,
	weeklyBins,
	weekStart,
	monthLabels
} from './derive.js';

const day = (d) => new Date(Date.now() - d * 86400000).toISOString().slice(0, 10);

describe('aggregate', () => {
	it('sums commit_count, falling back to commits.length only when the key is absent', () => {
		expect(aggregate([{ commits: [{}, {}], commit_count: 717 }], 60).commits).toBe(717);
		expect(aggregate([{ commits: [{}, {}] }], 60).commits).toBe(2);
		expect(aggregate([{ commits: [{}, {}], commit_count: 0 }], 60).commits).toBe(0);
		expect(
			aggregate([{ commits: [{}, {}], commit_count: 717 }, { commits: [{}, {}, {}] }], 60).commits
		).toBe(720);
	});
});

const repo = {
	owner: 'o',
	name: 'r',
	default_branch: 'master',
	security: [
		{ kind: 'dependabot', severity: 'critical', title: 'pkg: bad', url: '' },
		{ kind: 'dependabot', severity: 'low', title: 'pkg2: meh', url: '' }
	],
	local: { dirty: 3, dirty_since_days: 11, ahead: 0, behind: 0, stashes: 0 },
	branches: {
		stray: [{ name: 'origin/old', date: '2026-01-01', merged: true }],
		worktrees: ['/tmp/wt']
	},
	prds: { backlog: [], wip: [{ title: 'Ship X', idle_days: 20 }], done_count: 0 }
};

describe('attention scoring', () => {
	it('produces human-readable reasons for every signal', () => {
		const texts = attention(repo).reasons.map((r) => r.text).join(' | ');
		expect(texts).toMatch(/1 critical\/high security alert/);
		expect(texts).toMatch(/1 low\/medium security alert/);
		expect(texts).toMatch(/dirty for 11d/);
		expect(texts).toMatch(/1 stray branch \(1 merged\)/);
		expect(texts).toMatch(/idle 20d/);
		expect(texts).toMatch(/1 extra worktree/);
	});
});

describe('todosFor', () => {
	const todos = todosFor([repo]);
	const byId = (id) => todos.find((t) => t.id === id);

	it('derives the expected mechanical todo ids', () => {
		const ids = todos.map((t) => t.id);
		expect(ids).toContain('o/r:security:crit');
		expect(ids).toContain('o/r:security:mild');
		expect(ids).toContain('o/r:branch:prune');
		expect(ids).toContain('o/r:branch:worktrees');
		expect(byId('o/r:prd:Ship X').urgency).toBe('now');
		expect(byId('o/r:local:dirty').why).toMatch(/dirty for 11d/);
	});

	it('handles pre-2026-07 data.json (wip as strings, no security/branches)', () => {
		expect(wipItems({ wip: ['Old'] })).toEqual([{ title: 'Old', idle_days: null }]);
		const legacy = {
			...repo,
			security: undefined,
			branches: undefined,
			prds: { backlog: [], wip: ['Old'], done_count: 0 }
		};
		expect(todosFor([legacy]).find((t) => t.id === 'o/r:prd:Old').urgency).toBe('soon');
		expect(attention(legacy).score).toBeGreaterThan(0);
	});

	it('maps importance/effort/agent to Eisenhower quadrants', () => {
		expect(quadrant(byId('o/r:security:crit'))).toBe('do'); // now + high
		expect(quadrant(byId('o/r:prd:Ship X'))).toBe('do'); // wip idle 20d -> now + high
		expect(quadrant(byId('o/r:branch:prune'))).toBe('delegate'); // low + agent
		expect(byId('o/r:branch:prune').effort).toBe('quick');
		expect(quadrant(byId('o/r:security:mild'))).toBe('drop'); // low, no agent
		expect(byId('o/r:local:dirty').effort).toBe('quick');
		expect(byId('o/r:local:dirty').importance).toBe('high');
	});
});

describe('PR / issue / release todos', () => {
	const prRepo = {
		owner: 'o',
		name: 'r',
		default_branch: 'master',
		prs: [
			{ number: 1, title: 'ok', author: 'x', draft: false, created: day(3), review: 'APPROVED', checks: 'passing', labels: [] },
			{ number: 2, title: 'red', author: 'x', draft: false, created: day(3), review: 'APPROVED', checks: 'failing', labels: [] },
			{ number: 3, title: 'dep', author: 'renovate', draft: false, created: day(3), review: '', checks: '', labels: [] }
		],
		issues: [
			{ number: 5, title: 'due', created: day(30), labels: [], comments: 0, reactions: 0, milestone: { title: 'v2', due: day(2) } },
			{ number: 6, title: 'hot', created: day(30), labels: [], comments: 4, reactions: 0, milestone: null },
			{ number: 7, title: 'quiet', created: day(30), labels: [], comments: 0, reactions: 0, milestone: null }
		],
		unreleased_commits: 12,
		last_tag: 'v1',
		changelog_unreleased: false
	};
	const prTodos = todosFor([prRepo]);

	it('classifies approved / failing / dependency PRs', () => {
		expect(prTodos.find((t) => t.id === 'o/r:pr:#1').action).toMatch(/^Merge approved/);
		expect(prTodos.find((t) => t.id === 'o/r:pr:#1').effort).toBe('quick');
		expect(prTodos.find((t) => t.id === 'o/r:pr:#2').action).toMatch(/^Fix checks on approved/);
		expect(prTodos.find((t) => t.id === 'o/r:pr:#3').agent).toBe('/review-deps-prs');
	});

	it('flags milestone-due, engaged, and triage issues', () => {
		expect(prTodos.find((t) => t.id === 'o/r:issue:#5').urgency).toBe('now'); // overdue
		expect(prTodos.find((t) => t.id === 'o/r:issue:#6').action).toMatch(/engaged issue/);
		expect(prTodos.find((t) => t.id === 'o/r:issue:triage').action).toMatch(/Triage 1 open issue/);
	});

	it('surfaces the CHANGELOG-empty release todo', () => {
		expect(prTodos.find((t) => t.kind === 'release').action).toMatch(/CHANGELOG entries/);
	});
});

describe('brush cadence', () => {
	const todos = todosFor([repo]);
	it('nags at >=30d or never, with an id that rolls with the last-run date', () => {
		const brushTodo = todos.find((t) => t.kind === 'brush');
		expect(brushTodo.id).toBe('o/r:brush:never');
		expect(brushTodo.agent).toBe('/brush');
		expect(quadrant(brushTodo)).toBe('delegate');
		expect(attention(repo).reasons.map((x) => x.text).join(' | ')).toMatch(/never brushed/);

		const brushed45 = { ...repo, brush_last_run: day(45) };
		expect(todosFor([brushed45]).find((t) => t.kind === 'brush').why).toMatch(/45d ago/);
		expect(todosFor([brushed45]).find((t) => t.kind === 'brush').id).toBe(`o/r:brush:${day(45)}`);
		expect(attention(brushed45).reasons.map((x) => x.text).join(' | ')).toMatch(
			/brush overdue \(45d ago\)/
		);
		expect(todosFor([{ ...repo, brush_last_run: day(30) }]).some((t) => t.kind === 'brush')).toBe(
			true
		); // boundary: due at 30
		const freshBrush = { ...repo, brush_last_run: day(10) };
		expect(todosFor([freshBrush]).find((t) => t.kind === 'brush')).toBeUndefined();
		expect(attention(freshBrush).reasons.some((x) => /brush/.test(x.text))).toBe(false);
	});
});

describe('external PRs', () => {
	it('ranks review-requested now and authored soon', () => {
		const ext = externalTodos({
			review_requested: [{ repo: 'a/b', number: 9, title: 'T', created: '2026-07-01', url: 'https://x/9' }],
			authored: [{ repo: 'c/d', number: 2, title: 'M', created: '2026-07-01', url: 'https://x/2' }]
		});
		expect(ext[0].urgency).toBe('now');
		expect(quadrant(ext[0])).toBe('do');
		expect(ext[1].effort).toBe('quick');
	});

	it('surfaces a lookup failure as its own todo with an id that varies by error text', () => {
		const isErr = (t) => t.id.startsWith('ext:error:');
		const failed = externalTodos({ error: 'gh auth login', review_requested: [], authored: [] });
		const errs = failed.filter(isErr);
		expect(errs.length).toBe(1);
		expect(errs[0].kind).toBe('external');
		expect(errs[0].urgency).toBe('now');
		expect(errs[0].why).toMatch(/gh auth login/);
		expect(errs[0].action).toMatch(/fail|error/i);

		const errText = (msg) =>
			externalTodos({ error: msg, review_requested: [], authored: [] }).find((t) => t.why === msg);
		const a = errText('gh auth login');
		const b = errText('network timeout: could not reach api.github.com');
		expect(a.id).not.toBe(b.id); // different error -> different id
		expect(errText('gh auth login').id).toBe(a.id); // same error -> same id

		expect(externalTodos(null).length).toBe(0);
		expect(externalTodos({ review_requested: [], authored: [] }).filter((t) => t.kind === 'external').length).toBe(0);
	});
});

describe('merged list + quick wins', () => {
	it('merges judgment + external + mechanical and filters quick wins by done-state', () => {
		const all = allTodos(
			[repo],
			{ todos: [{ id: 'o/r:judgment:x', repo: 'o/r', kind: 'judgment', urgency: 'now', action: 'A', why: 'w' }] },
			null
		);
		expect(all.find((t) => t.id === 'o/r:judgment:x').importance).toBe('high'); // judgment defaults
		const wins = quickWins(all, new Set());
		expect(wins.every((t) => t.effort === 'quick')).toBe(true);
		expect(wins.some((t) => t.id === 'o/r:local:dirty')).toBe(true);
		expect(quickWins(all, new Set(['o/r:local:dirty'])).find((t) => t.id === 'o/r:local:dirty')).toBeUndefined();
	});
});

describe('since-last diff', () => {
	it('reports movers, added and no prev', () => {
		const prevRepo = { ...repo, local: { ...repo.local, dirty: 0 } };
		const diff = sinceLast([repo], { generated_at: '2026-07-10T00:00:00+00:00', repos: [prevRepo] });
		expect(diff.at).toBe('2026-07-10T00:00:00+00:00');
		expect(diff.added).toBeGreaterThanOrEqual(1); // dirty todo is new
		expect(diff.movers[0].d).toBeGreaterThan(0); // score went up
		expect(sinceLast([repo], null)).toBeNull();
	});

	it('does not treat a repo dropped from the run as "cleared"', () => {
		const droppedPrev = { owner: 'd', name: 'gone', security: [{ kind: 'dependabot', severity: 'critical', title: 'pkg: bad', url: '' }] };
		const diff = sinceLast([], { generated_at: '2026-08-01T00:00:00+00:00', repos: [droppedPrev] });
		expect(diff.cleared).toBe(0);
	});

	it('counts a genuinely-resolved repo present in both runs as cleared', () => {
		const prev = { owner: 'e', name: 'ok', security: [{ kind: 'dependabot', severity: 'critical', title: 'pkg: bad', url: '' }] };
		const now = { owner: 'e', name: 'ok', security: [] };
		const diff = sinceLast([now], { generated_at: '2026-08-01T00:00:00+00:00', repos: [prev] });
		expect(diff.cleared).toBe(1);
	});
});

describe('safeUrl sanitization', () => {
	it('keeps http/https and drops every other scheme', () => {
		expect(safeUrl('https://a')).toBe('https://a');
		expect(safeUrl('HTTP://a')).toBe('HTTP://a');
		expect(safeUrl('javascript:1')).toBeUndefined();
		expect(safeUrl('data:text/html,x')).toBeUndefined();
		expect(safeUrl('')).toBeUndefined();
		expect(safeUrl(undefined)).toBeUndefined();
	});

	it('is wired into todosFor, externalTodos, and allManual mapping', () => {
		const ciUrlRepo = {
			owner: 'h',
			name: 'ci',
			default_branch: 'master',
			ci: [
				{ workflow: 'hostile-deploy', conclusion: 'failure', url: 'javascript:window.__m=1', date: '2026-01-01' },
				{ workflow: 'safe-deploy', conclusion: 'failure', url: 'https://example.org/run/safe', date: '2026-01-01' }
			]
		};
		const ciTodos = todosFor([ciUrlRepo]);
		expect(ciTodos.find((t) => t.id === 'h/ci:ci:hostile-deploy').url).toBeUndefined();
		expect(ciTodos.find((t) => t.id === 'h/ci:ci:safe-deploy').url).toBe('https://example.org/run/safe');

		const hostileExt = externalTodos({
			review_requested: [{ repo: 'a/b', number: 1, title: 'RR', created: '2026-07-01', url: 'javascript:window.__m=1' }],
			authored: [{ repo: 'c/d', number: 2, title: 'AU', created: '2026-07-01', url: 'javascript:window.__m=1' }]
		});
		expect(hostileExt.find((t) => t.id === 'ext:rr:a/b#1').url).toBeUndefined();
		expect(hostileExt.find((t) => t.id === 'ext:mine:c/d#2').url).toBeUndefined();

		const hostileManual = allTodos(
			[repo],
			{ todos: [{ id: 'o/r:judgment:hostile', repo: 'o/r', kind: 'judgment', urgency: 'now', action: 'A', why: 'w', url: 'javascript:window.__m=1' }] },
			null
		);
		expect(hostileManual.find((t) => t.id === 'o/r:judgment:hostile').url).toBeUndefined();
	});
});

// PRD 00066 Phase 0: temporal derive functions (diff / trend / horizon).

describe('diffSinceLast (PRD 00066 named diff)', () => {
	it('is the PRD-named alias for sinceLast semantics', () => {
		const prevRepo = { ...repo, local: { ...repo.local, dirty: 0 } };
		const prev = { generated_at: '2026-09-27T00:00:00+00:00', repos: [prevRepo] };
		expect(diffSinceLast([repo], prev)).toEqual(sinceLast([repo], prev));
	});

	it('reports movers, cleared and added against the previous snapshot', () => {
		const prevRepo = { ...repo, local: { ...repo.local, dirty: 0 } };
		const diff = diffSinceLast([repo], {
			generated_at: '2026-09-27T00:00:00+00:00',
			repos: [prevRepo]
		});
		expect(diff.at).toBe('2026-09-27T00:00:00+00:00');
		expect(diff.added).toBeGreaterThanOrEqual(1); // dirty todo is new this run
		expect(diff.movers[0].d).toBeGreaterThan(0); // gems got worse
	});

	it('returns null when there is no previous snapshot (first run)', () => {
		expect(diffSinceLast([repo], null)).toBeNull();
		expect(diffSinceLast([repo], undefined)).toBeNull();
		expect(diffSinceLast([repo], {})).toBeNull();
	});
});

describe('trendSeries (PRD 00066 sparkline series)', () => {
	const line = (at, open, extra = {}) => ({
		at,
		skipped: 0,
		repos: { 'buvis/gems': { i: open, p: 0, a: 0, f: 0 } },
		...extra
	});

	it('sums open items (issues+prs+alerts+failing CI) per run', () => {
		const series = trendSeries([
			{ at: 't1', skipped: 0, repos: { 'a/b': { i: 1, p: 2, a: 0, f: 0 }, 'c/d': { i: 0, p: 0, a: 1, f: 1 } } }
		]);
		expect(series).toHaveLength(1);
		expect(series[0].open).toBe(5); // 1+2 + 1+1
		expect(series[0].incomplete).toBe(false);
	});

	it('marks a run incomplete when any repo errored or a repo was skipped', () => {
		const errored = trendSeries([{ at: 't', skipped: 0, repos: { 'a/b': { i: 0, p: 0, a: 0, f: 0, e: 1 } } }]);
		expect(errored[0].incomplete).toBe(true);
		const skipped = trendSeries([{ at: 't', skipped: 2, repos: { 'a/b': { i: 0, p: 0, a: 0, f: 0 } } }]);
		expect(skipped[0].incomplete).toBe(true);
	});

	it('renders a single history line as one point, not an error', () => {
		const series = trendSeries([line('only', 3)]);
		expect(series).toHaveLength(1);
		expect(series[0].open).toBe(3);
	});

	it('degrades to an empty series for absent or empty history', () => {
		expect(trendSeries(null)).toEqual([]);
		expect(trendSeries(undefined)).toEqual([]);
		expect(trendSeries([])).toEqual([]);
	});

	it('tolerates a line with a missing repos map', () => {
		expect(trendSeries([{ at: 't', skipped: 0 }])[0].open).toBe(0);
	});
});

describe('attentionHorizon (PRD 00066 Brief horizon queue)', () => {
	// A repo with no brush_last_run always scores (never-brushed), so a
	// genuinely-quiet repo needs a recent brush date.
	const quietRepo = (owner, name) => ({ owner, name, brush_last_run: day(1) });

	it('ranks repos that need attention by descending score, dropping the quiet ones', () => {
		const horizon = attentionHorizon([repo, quietRepo('q', 'calm')]);
		expect(horizon.map((x) => `${x.r.owner}/${x.r.name}`)).toEqual(['o/r']);
		expect(horizon[0].score).toBeGreaterThan(0);
		expect(Array.isArray(horizon[0].reasons)).toBe(true);
		expect(horizon[0].sev).toBeDefined();
	});

	it('is stable-sorted so equal scores keep slug order', () => {
		const a = { owner: 'a', name: 'one', brush_last_run: day(1), security: [{ severity: 'high', title: 't', url: '' }] };
		const b = { owner: 'b', name: 'two', brush_last_run: day(1), security: [{ severity: 'high', title: 't', url: '' }] };
		const horizon = attentionHorizon([b, a]);
		expect(horizon.map((x) => x.r.owner)).toEqual(['a', 'b']);
	});

	it('returns an empty horizon for an all-quiet portfolio', () => {
		expect(attentionHorizon([quietRepo('x', 'y')])).toEqual([]);
		expect(attentionHorizon([])).toEqual([]);
	});
});

describe('commit-heat helpers (Activity view)', () => {
	const day = (d) => new Date(Date.now() - d * 86400000).toISOString().slice(0, 10);

	it('bins commits into weekly columns across the window', () => {
		const bins = weeklyBins([{ date: day(1) }, { date: day(2) }, { date: day(9) }], 21);
		expect(bins).toHaveLength(3); // ceil(21/7)
		expect(bins.reduce((a, b) => a + b, 0)).toBe(3);
		expect(bins[bins.length - 1]).toBe(2); // this week
	});

	it('ignores commits older than the window and handles no commits', () => {
		expect(weeklyBins([{ date: day(999) }], 14).reduce((a, b) => a + b, 0)).toBe(0);
		expect(weeklyBins(undefined, 14).reduce((a, b) => a + b, 0)).toBe(0);
	});

	it('labels a week-start column and produces a sparse month axis', () => {
		expect(typeof weekStart(0, 60)).toBe('string');
		const labels = monthLabels(Math.ceil(60 / 7), 60);
		expect(labels).toHaveLength(Math.ceil(60 / 7));
		// first column always carries a month name; repeats blank out
		expect(labels[0]).not.toBe('');
	});
});
