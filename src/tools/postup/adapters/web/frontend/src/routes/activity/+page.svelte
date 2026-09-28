<script>
	import { getContext } from 'svelte';
	import { slug, weeklyBins, weekStart, monthLabels, safeUrl } from '$lib/derive.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const repos = $derived(payload?.repos ?? []);
	const sinceDays = $derived(payload?.since_days ?? 60);

	const rows = $derived(
		repos
			.map((r) => ({ r, bins: weeklyBins(r.commits, sinceDays), total: r.commits?.length ?? 0 }))
			.filter((x) => x.total > 0)
			.toSorted((a, b) => b.total - a.total)
	);
	const max = $derived(Math.max(1, ...rows.flatMap((x) => x.bins)));
	const ncols = $derived(Math.ceil(sinceDays / 7));
	const labels = $derived(monthLabels(ncols, sinceDays));
	const level = (v) => (v === 0 ? 0 : Math.max(1, Math.round((v / max) * 5)));

	// Portfolio-wide recent releases, most recent first.
	const releases = $derived(
		repos
			.flatMap((r) =>
				(r.releases ?? []).map((x) => ({
					...x,
					r,
					url: safeUrl(`https://github.com/${slug(r)}/releases/tag/${x.tag}`)
				}))
			)
			.filter((x) => x.date)
			.toSorted((a, b) => b.date.localeCompare(a.date))
	);

	// Degraded collection is surfaced inline, not as a gap: any repo carrying
	// errors[] gets a badge row here so a missing heat cell is never mistaken
	// for "no activity" when it was really "collection failed".
	const degraded = $derived(repos.filter((r) => r.errors?.length));
</script>

{#if degraded.length}
	<section class="sec">
		<h2 class="sev-warning">Collection warnings · {degraded.length}</h2>
		<div class="errbadges">
			{#each degraded as r (slug(r))}
				<a class="errbadge" href="/repo/{slug(r)}">
					<span class="lbl err">⚠ {r.errors.length}</span>
					{slug(r)}
				</a>
			{/each}
		</div>
	</section>
{/if}

<section class="sec">
	<h2>Commit heat · {rows.length} active repos</h2>
	{#if rows.length === 0}
		<p class="empty">No commits in the last {sinceDays} days.</p>
	{:else}
		<div class="hm" style="--ncols: {ncols}">
			<span></span>
			{#each labels as m, i (i)}<span class="axis">{m}</span>{/each}
			{#each rows as { r, bins, total } (slug(r))}
				<a class="repobtn" href="/repo/{slug(r)}">{r.name}<span class="tot">{total}</span></a>
				{#each bins as v, i (i)}
					<div class="cell l{level(v)}" role="img" aria-label="{v} commits, week of {weekStart(i, sinceDays)}"></div>
				{/each}
			{/each}
		</div>
		<div class="legend">
			less
			{#each [0, 1, 2, 3, 4, 5] as l (l)}<div class="cell l{l}"></div>{/each}
			more
		</div>
	{/if}
</section>

<section class="sec">
	<h2>Recent releases · {releases.length}</h2>
	{#if releases.length === 0}
		<p class="empty">No releases collected.</p>
	{:else}
		<table>
			<thead><tr><th>date</th><th>repo</th><th>release</th></tr></thead>
			<tbody>
				{#each releases as x (slug(x.r) + x.tag)}
					<tr>
						<td class="num">{x.date}</td>
						<td><a href="/repo/{slug(x.r)}">{slug(x.r)}</a></td>
						<td>
							{#if x.url}<a href={x.url} target="_blank" rel="noreferrer">{x.name}</a>{:else}{x.name}{/if}
							{#if x.prerelease}<span class="lbl">pre</span>{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
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
	.errbadges {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.errbadge {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 3px 10px;
		border: 1px solid var(--serious);
		border-radius: 999px 8px 8px 999px;
		color: var(--ink-2);
		text-decoration: none;
		font-size: 12.5px;
	}
	.errbadge .err {
		color: var(--serious);
		border-color: var(--serious);
	}
	.hm {
		display: grid;
		grid-template-columns: minmax(150px, max-content) repeat(var(--ncols), 15px);
		gap: 2px;
		align-items: center;
		overflow-x: auto;
		padding-bottom: 6px;
	}
	.repobtn {
		padding-right: 12px;
		font-size: 12.5px;
		color: var(--ink);
		text-decoration: none;
	}
	.repobtn:hover {
		color: var(--accent);
	}
	.tot {
		color: var(--muted);
		margin-left: 6px;
		font-size: 11px;
	}
	.axis {
		font-size: 10px;
		color: var(--muted);
	}
	.cell {
		width: 13px;
		height: 13px;
		border-radius: 3px;
	}
	.cell.l0 {
		box-shadow: inset 0 0 0 1px var(--grid);
	}
	.cell.l1 {
		background: var(--seq-1);
	}
	.cell.l2 {
		background: var(--seq-2);
	}
	.cell.l3 {
		background: var(--seq-3);
	}
	.cell.l4 {
		background: var(--seq-4);
	}
	.cell.l5 {
		background: var(--seq-5);
	}
	.legend {
		display: flex;
		align-items: center;
		gap: 3px;
		margin-top: 8px;
		color: var(--muted);
		font-size: 11px;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}
	th {
		text-align: left;
		color: var(--muted);
		font-weight: 500;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 4px 8px;
	}
	td {
		padding: 4px 8px;
		border-top: 1px solid var(--grid);
	}
	.num {
		font-variant-numeric: tabular-nums;
		color: var(--ink-2);
	}
	.empty {
		color: var(--muted);
	}
</style>
