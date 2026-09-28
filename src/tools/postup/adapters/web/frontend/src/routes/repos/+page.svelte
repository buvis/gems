<script>
	import { getContext } from 'svelte';
	import { slug, ciFailing, attention } from '$lib/derive.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const repos = $derived(payload?.repos ?? []);

	const scored = $derived(new Map(repos.map((r) => [slug(r), attention(r)])));

	let search = $state('');
	let sort = $state('attention');

	const sorts = {
		attention: (a, b) => scored.get(slug(b)).score - scored.get(slug(a)).score,
		activity: (a, b) => (b.commit_count ?? 0) - (a.commit_count ?? 0),
		name: (a, b) => slug(a).localeCompare(slug(b))
	};
	const shown = $derived(
		repos
			.filter((r) =>
				`${slug(r)} ${r.description ?? ''} ${r.language ?? ''}`.toLowerCase().includes(search.toLowerCase())
			)
			.toSorted(sorts[sort])
	);
</script>

<div class="bar">
	<input bind:value={search} placeholder="filter repos…" aria-label="Filter repos" />
	<select bind:value={sort} aria-label="Sort repos">
		<option value="attention">sort: attention</option>
		<option value="activity">sort: activity</option>
		<option value="name">sort: name</option>
	</select>
	<span class="count">{shown.length} shown</span>
</div>

<div class="grid">
	{#each shown as r (slug(r))}
		{@const fails = ciFailing(r)}
		{@const sc = scored.get(slug(r))}
		{@const wip = (r.local?.dirty ?? 0) + (r.local?.ahead ?? 0) > 0}
		<article class="card">
			<div class="head">
				<b>{slug(r)}</b>
				{#if sc.score > 0}<span class="scorelbl">{sc.score}</span>{/if}
			</div>
			{#if r.description}<p class="desc">{r.description}</p>{/if}
			<div class="badges">
				{#if r.ci?.length}
					<span class={fails.length ? 'sev-critical' : 'sev-good'}>
						{fails.length ? `✗ CI ${fails.length}` : '✓ CI'}
					</span>
				{/if}
				{#if r.prs?.length}<span>⇄ {r.prs.length} PR</span>{/if}
				{#if r.issues?.length}<span>◎ {r.issues.length}</span>{/if}
				{#if r.security?.length}<span class="sev-warning">⚠ {r.security.length}</span>{/if}
				{#if r.unreleased_commits >= 10}<span class="sev-warning">↟ {r.unreleased_commits}</span>{/if}
				{#if wip}<span class="sev-serious">● WIP</span>{/if}
				{#if r.prds?.backlog?.length}<span>▤ {r.prds.backlog.length}</span>{/if}
			</div>
			{#if r.errors?.length}
				<div class="errors">
					<span class="lbl err">⚠ {r.errors.length} collection {r.errors.length === 1 ? 'warning' : 'warnings'}</span>
					<ul>
						{#each r.errors as e, i (i)}<li>{e}</li>{/each}
					</ul>
				</div>
			{/if}
			<div class="foot">
				<span class="meta">{r.language || '—'} · {r.commit_count} commits</span>
			</div>
		</article>
	{/each}
</div>

{#if shown.length === 0}
	<p class="empty">No repos match.</p>
{/if}

<style>
	.bar {
		display: flex;
		gap: 10px;
		align-items: center;
		margin-bottom: 14px;
	}
	input,
	select {
		font: inherit;
		color: var(--ink);
		background: var(--surface);
		border: 1px solid var(--grid);
		border-radius: 7px;
		padding: 6px 10px;
	}
	input {
		width: 260px;
	}
	.count {
		color: var(--muted);
		font-size: 12px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
		gap: 10px;
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 9px;
		padding: 12px 14px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.head {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.head b {
		font-size: 15px;
	}
	.scorelbl {
		margin-left: auto;
		font-size: 12px;
		color: var(--ink-2);
		font-variant-numeric: tabular-nums;
	}
	.desc {
		margin: 0;
		color: var(--ink-2);
		font-size: 12.5px;
	}
	.badges {
		display: flex;
		gap: 12px;
		font-size: 12.5px;
		color: var(--ink-2);
		flex-wrap: wrap;
	}
	.errors {
		font-size: 12px;
	}
	.errors .err {
		border-color: var(--serious);
		color: var(--serious);
	}
	.errors ul {
		margin: 4px 0 0;
		padding-left: 18px;
		color: var(--muted);
	}
	.foot {
		display: flex;
		justify-content: space-between;
		margin-top: auto;
	}
	.meta {
		color: var(--muted);
		font-size: 11.5px;
	}
	.empty {
		color: var(--muted);
	}
</style>
