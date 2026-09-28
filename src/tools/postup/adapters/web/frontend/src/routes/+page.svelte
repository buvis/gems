<script>
	import { getContext } from 'svelte';
	import {
		slug,
		attention,
		worstSev,
		aggregate,
		allTodos,
		quickWins,
		epicsFor,
		diffSinceLast,
		trendSeries,
		ago,
		safeUrl
	} from '$lib/derive.js';
	import { loadDone } from '$lib/done.js';
	import Horizon from './_components/Horizon.svelte';
	import Sparkline from './_components/Sparkline.svelte';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const enriched = $derived(portfolio.state.enriched);

	const repos = $derived(payload?.repos ?? []);
	const epics = $derived(payload?.epics ?? { summary: '', repos: {} });
	const external = $derived(payload?.external ?? null);
	const sinceDays = $derived(payload?.since_days ?? 60);
	const skipped = $derived(payload?.skipped ?? []);
	const prev = $derived(payload?.prev ?? null);
	const history = $derived(payload?.history ?? []);

	const scored = $derived(new Map(repos.map((r) => [slug(r), attention(r)])));
	const agg = $derived(aggregate(repos, sinceDays));
	const queue = $derived(
		repos
			.map((r) => ({ r, ...scored.get(slug(r)) }))
			.filter((x) => x.score > 0)
			.sort((a, b) => b.score - a.score)
	);
	const fires = $derived(queue.filter((x) => worstSev(x.reasons) === 'critical'));
	const paragraphs = $derived((epics.summary ?? '').split(/\n\n+/).filter(Boolean));
	const wins = $derived(quickWins(allTodos(repos, epics, external), loadDone()));

	// Temporal features (PRD 00066): since-last diff against the rotated prev
	// snapshot (null on first run -> no diff markers), and the portfolio trend
	// from complete history runs (a single point still renders, as a dot).
	const delta = $derived(diffSinceLast(repos, prev));
	const trend = $derived(trendSeries(history).filter((h) => !h.incomplete));

	// Deterministic stat row — always available, LLM or not.
	const STATS = $derived([
		['commits', agg.commits],
		['open PRs', agg.prs],
		['issues', agg.issues],
		['failing CI', agg.failing],
		['security', agg.alerts],
		['PRD backlog', agg.backlog],
		['releases', agg.releases],
		['local WIP', agg.localWip]
	]);
</script>

<div class="stage">
	<section class="glass">
		<p class="head">
			<b>{repos.length}</b> repos · <b class:hot={fires.length}>{fires.length}</b> burning
		</p>
		<div class="mini">
			{#each STATS as [label, v] (label)}
				<span class="stat"><b>{v}</b> <span class="lab">{label}</span></span>
			{/each}
		</div>
		{#if skipped.length}
			<p class="skiplist">
				<strong class="sev-warning">{skipped.length}</strong> not collected:
				{skipped.map((r) => `${r.owner}/${r.name}`).join(', ')}
			</p>
		{/if}
	</section>

	<section class="glass">
		<h2>Quick wins</h2>
		{#if wins.length}
			<div class="wins">
				{#each wins as t (t.id)}
					{@const url = safeUrl(t.url)}
					<span class="win">
						<span class="wact">{#if url}<a href={url} target="_blank" rel="noreferrer">{t.action}</a>{:else}{t.action}{/if}</span>
						<span class="wrepo">{t.repo}</span>
					</span>
				{/each}
			</div>
		{:else}
			<p class="calm">Nothing quick left.</p>
		{/if}
	</section>

	<section class="glass">
		<h2>Burning now</h2>
		{#if queue.length === 0}
			<p class="calm">All quiet. Nothing needs you.</p>
		{:else}
			<ul class="burn">
				{#each queue.slice(0, 5) as { r, score, reasons } (slug(r))}
					{@const sev = worstSev(reasons)}
					<li>
						<b class="sev-{sev}">{score}</b>
						<span class="bname">{slug(r)}</span>
						<span class="breasons">{reasons[0]?.text}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	<section class="glass">
		<h2>Attention horizon</h2>
		<Horizon {repos} />
	</section>

	{#if delta}
		<section class="glass">
			<h2>Since last brief</h2>
			<p class="delta">
				vs {ago(delta.at)}:
				<b class="sev-good">{delta.cleared} cleared</b> ·
				<b class:sev-serious={delta.added > 0}>{delta.added} new</b>
			</p>
			{#each delta.movers.slice(0, 3) as m (slug(m.r))}
				<a class="mover" href="/repo/{slug(m.r)}">
					<b class={m.d > 0 ? 'sev-critical' : 'sev-good'}>{m.d > 0 ? '▲' : '▼'} {Math.abs(m.d)}</b>
					{slug(m.r)}
				</a>
			{/each}
			{#if trend.length >= 1}
				<div class="trend">
					<Sparkline values={trend.map((h) => h.open)} w={300} h={22} />
					<span class="tlab">
						{#if trend.length === 1}open items (one brief so far){:else}open items across {trend.length} briefs{/if}
					</span>
				</div>
			{/if}
		</section>
	{/if}

	<section class="glass">
		<h2>The story</h2>
		{#if enriched && paragraphs.length}
			{#each paragraphs as p, i (i)}<p class="story">{p}</p>{/each}
			{#each repos as r (slug(r))}
				{@const grouped = epicsFor(r, epics)}
				{#if grouped.epics.length}
					<div class="epicgroup">
						<h3>{slug(r)}</h3>
						{#each grouped.epics as e, i (i)}
							<p class="epic"><b>{e.title}</b>{#if e.summary} — {e.summary}{/if} <span class="mono">({e.commits.length} commits)</span></p>
						{/each}
					</div>
				{/if}
			{/each}
		{:else}
			<p class="empty">
				No narrative yet — the enrichment step (<span class="mono">postup enrich</span> → epics.json)
				hasn't run. Showing the deterministic brief only.
			</p>
		{/if}
	</section>
</div>

<style>
	.stage {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.glass {
		padding: 14px 18px 16px;
		border: 1px solid var(--border);
		border-left: 14px solid var(--lcars-a);
		border-radius: 12px;
		background: color-mix(in srgb, var(--surface) 76%, transparent);
	}
	.head {
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-size: 17px;
		margin: 0 0 8px;
	}
	.head .hot {
		color: var(--critical);
	}
	.mini {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.stat {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 3px 12px;
		background: color-mix(in srgb, var(--surface) 60%, transparent);
		border: 1px solid var(--border);
		border-radius: 999px 8px 8px 999px;
	}
	.stat b {
		font-variant-numeric: tabular-nums;
	}
	.stat .lab {
		color: var(--ink-2);
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	h2 {
		font-family: var(--display);
		font-size: 13px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--accent);
		margin: 0 0 8px;
	}
	h3 {
		font-size: 13px;
		margin: 12px 0 4px;
	}
	.wins {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.win {
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		padding: 3px 12px;
		border: 1px solid var(--border);
		border-left: 5px solid var(--good);
		border-radius: 999px 8px 8px 999px;
	}
	.wrepo {
		color: var(--muted);
		font-size: 11px;
	}
	.calm {
		color: var(--good);
		font-weight: 650;
	}
	.burn {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.burn li {
		display: flex;
		align-items: baseline;
		gap: 10px;
		padding: 4px 0;
	}
	.bname {
		font-weight: 650;
	}
	.breasons {
		color: var(--ink-2);
		font-size: 12px;
	}
	.story {
		color: var(--ink-2);
		margin: 0 0 8px;
	}
	.story:first-of-type {
		color: var(--ink);
	}
	.epic {
		margin: 2px 0;
		font-size: 13px;
	}
	.empty {
		color: var(--muted);
	}
	.skiplist {
		margin: 8px 0 0;
		font-size: 12px;
		color: var(--ink-2);
	}
	.delta {
		margin: 0 0 8px;
		font-size: 13px;
	}
	.mover {
		display: block;
		width: 100%;
		padding: 3px 0;
		text-decoration: none;
		color: var(--ink);
		font-size: 13px;
	}
	.mover:hover {
		color: var(--accent);
	}
	.trend {
		margin-top: 8px;
	}
	.tlab {
		display: block;
		color: var(--muted);
		font-size: 11px;
	}
</style>
