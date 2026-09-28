<script>
	import { getContext } from 'svelte';
	import { slug, isDepBot, daysAgo, safeUrl } from '$lib/derive.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const repos = $derived(payload?.repos ?? []);
	const external = $derived(payload?.external ?? null);

	// A repo is "in flight" when it carries local WIP, branch/worktree litter, or
	// open PRs (drafts and deps included — this is the working view, not the
	// review queue). Grouped by repo so one repo's whole state reads together.
	function workOf(r) {
		const l = r.local ?? {};
		const stray = r.branches?.stray ?? [];
		const worktrees = r.branches?.worktrees ?? [];
		const prs = (r.prs ?? []).map((p) => ({
			...p,
			url: safeUrl(`https://github.com/${slug(r)}/pull/${p.number}`)
		}));
		const localBits = [];
		if (l.branch && l.branch !== r.default_branch) localBits.push({ cls: '', text: `on ${l.branch}` });
		if (l.dirty) localBits.push({ cls: 'sev-serious', text: `${l.dirty} dirty${l.dirty_since_days >= 2 ? ` (${l.dirty_since_days}d)` : ''}` });
		if (l.ahead) localBits.push({ cls: 'sev-serious', text: `${l.ahead} unpushed` });
		if (l.behind) localBits.push({ cls: 'sev-warning', text: `${l.behind} behind` });
		if (l.stashes) localBits.push({ cls: '', text: `${l.stashes} stashed` });
		const hasWork = localBits.length || stray.length || worktrees.length || prs.length;
		return { r, localBits, stray, worktrees, prs, hasWork };
	}

	const groups = $derived(repos.map(workOf).filter((g) => g.hasWork).toSorted((a, b) => slug(a.r).localeCompare(slug(b.r))));

	const extRows = $derived([
		...(external?.review_requested ?? []).map((p) => ({ ...p, role: 'review requested', url: safeUrl(p.url) })),
		...(external?.authored ?? []).map((p) => ({ ...p, role: 'your PR', url: safeUrl(p.url) }))
	]);
	const age = (c) => `${daysAgo(c) ?? '?'}d`;
</script>

{#if extRows.length || external?.error}
	<section class="sec">
		<h2>Waiting on you elsewhere{#if extRows.length}&nbsp;· {extRows.length}{/if}</h2>
		{#if external?.error}
			<p class="empty sev-critical">Could not check external PRs: {external.error}</p>
		{:else}
			<ul class="ext">
				{#each extRows as p (p.role + p.repo + p.number)}
					<li>
						<span class="age">{age(p.created)}</span>
						<span class="lbl" class:sev-serious={p.role === 'review requested'}>{p.role}</span>
						<span class="erepo">{p.repo}</span>
						{#if p.url}<a href={p.url} target="_blank" rel="noreferrer">#{p.number} {p.title}</a>{:else}#{p.number} {p.title}{/if}
						{#if p.draft}<span class="lbl">draft</span>{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<section class="sec">
	<h2>In flight · {groups.length} {groups.length === 1 ? 'repo' : 'repos'}</h2>
	{#if groups.length === 0}
		<p class="clean">✓ Clean. No local WIP, branch litter, or open PRs anywhere.</p>
	{:else}
		<div class="grid">
			{#each groups as g (slug(g.r))}
				<article class="card">
					<h3><a href="/repo/{slug(g.r)}">{slug(g.r)}</a></h3>
					{#if g.localBits.length}
						<div class="local">
							{#each g.localBits as b, i (i)}<span class="lbl {b.cls}">{b.text}</span>{/each}
						</div>
					{/if}
					{#if g.prs.length}
						<h4>open PRs · {g.prs.length}</h4>
						<ul>
							{#each g.prs as p (p.number)}
								<li>
									{#if p.url}<a href={p.url} target="_blank" rel="noreferrer">#{p.number} {p.title}</a>{:else}#{p.number} {p.title}{/if}
									<span class="pmeta">{p.author}{#if daysAgo(p.created) != null} · {daysAgo(p.created)}d{/if}</span>
									{#if p.draft}<span class="lbl">draft</span>{/if}
									{#if isDepBot(p)}<span class="lbl">deps</span>{/if}
								</li>
							{/each}
						</ul>
					{/if}
					{#if g.stray.length || g.worktrees.length}
						<h4>branch litter</h4>
						<ul class="litter">
							{#each g.stray as b (b.name)}
								<li class="mono">{b.name}{#if b.merged}<span class="lbl">merged</span>{/if}</li>
							{/each}
							{#each g.worktrees as w (w)}<li class="mono">worktree {w}</li>{/each}
						</ul>
					{/if}
				</article>
			{/each}
		</div>
	{/if}
</section>

<style>
	.sec {
		margin-bottom: 22px;
	}
	h2 {
		font-family: var(--display);
		font-size: 13px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--accent);
		margin: 0 0 10px;
	}
	.clean {
		color: var(--good);
		font-weight: 650;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 10px;
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 9px;
		padding: 12px 14px;
	}
	.card h3 {
		font-size: 14px;
		margin: 0 0 8px;
	}
	.card h3 a {
		color: var(--ink);
		text-decoration: none;
	}
	.card h3 a:hover {
		color: var(--accent);
	}
	h4 {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--muted);
		margin: 10px 0 4px;
	}
	.local {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	ul {
		margin: 0;
		padding-left: 16px;
		color: var(--ink-2);
		font-size: 13px;
	}
	.litter {
		color: var(--muted);
	}
	.pmeta {
		color: var(--muted);
		font-size: 11.5px;
		margin-left: 6px;
	}
	.ext {
		list-style: none;
		margin: 0;
		padding: 0;
		font-size: 13px;
	}
	.ext li {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 4px 0;
		border-top: 1px solid var(--grid);
	}
	.age {
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}
	.erepo {
		color: var(--ink-2);
	}
	.empty {
		color: var(--muted);
	}
</style>
