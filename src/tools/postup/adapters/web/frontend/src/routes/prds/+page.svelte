<script>
	import { getContext } from 'svelte';
	import { slug, wipItems } from '$lib/derive.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const repos = $derived(payload?.repos ?? []);

	// Repos without a project-management specs/ bundle tree carry prds:null and are
	// OMITTED, not zero-filled — a repo that simply doesn't do PRDs should not read
	// as "0 wip".
	const rows = $derived(
		repos
			.filter((r) => r.prds)
			.map((r) => ({ r, p: { backlog: r.prds.backlog ?? [], wip: r.prds.wip ?? [], done_count: r.prds.done_count ?? 0 } }))
			.filter((x) => x.p.backlog.length || x.p.wip.length || x.p.done_count)
			.toSorted((a, b) => b.p.wip.length - a.p.wip.length || b.p.backlog.length - a.p.backlog.length)
	);
	const tot = $derived(
		rows.reduce(
			(s, x) => ({ b: s.b + x.p.backlog.length, w: s.w + x.p.wip.length, d: s.d + x.p.done_count }),
			{ b: 0, w: 0, d: 0 }
		)
	);
</script>

<section class="sec">
	<h2>PRD pipeline · {tot.w} wip · {tot.b} backlog · {tot.d} done</h2>
	{#if rows.length === 0}
		<p class="empty">No PRD pipeline found in any repo.</p>
	{:else}
		<div class="grid">
			{#each rows as { r, p } (slug(r))}
				<div class="card">
					<div class="head">
						<a href="/repo/{slug(r)}"><b>{slug(r)}</b></a>
						<span class="donen">{p.done_count} done</span>
					</div>
					{#if p.wip.length}
						<h3>in progress</h3>
						<ul>
							{#each wipItems(p) as w, i (i)}
								<li class="sev-serious">
									{w.title}{#if w.idle_days >= 7}<span class="idle">idle {w.idle_days}d</span>{/if}
								</li>
							{/each}
						</ul>
					{/if}
					{#if p.backlog.length}
						<h3>backlog</h3>
						<ul>{#each p.backlog as t, i (i)}<li>{t}</li>{/each}</ul>
					{/if}
				</div>
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
		margin: 0 0 12px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 10px;
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 9px;
		padding: 12px 14px;
	}
	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 4px;
	}
	.head a {
		color: var(--ink);
		text-decoration: none;
	}
	.head a:hover {
		color: var(--accent);
	}
	.donen {
		margin-left: auto;
		color: var(--muted);
		font-size: 11.5px;
	}
	h3 {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--muted);
		margin: 10px 0 4px;
	}
	ul {
		margin: 0;
		padding-left: 18px;
		color: var(--ink-2);
	}
	.idle {
		color: var(--muted);
		font-size: 11px;
		margin-left: 6px;
	}
	li {
		margin: 2px 0;
	}
	.empty {
		color: var(--muted);
	}
</style>
