<script>
	import { slug, attentionHorizon } from '$lib/derive.js';

	// The attention horizon presented as a ranked strip (PRD 00066). Ranking
	// lives in derive's attentionHorizon; this only renders it. The SPA drew this
	// as a d3-force gravity field, which needs a runtime dep out of this PRD's
	// pinned toolchain — the PRD names it a "strip", so a ranked strip it is.
	let { repos = [] } = $props();
	const queue = $derived(attentionHorizon(repos));
	const worst = $derived(queue.length ? 150 : 1);
</script>

<div class="horizon">
	{#if queue.length === 0}
		<p class="calm">✓ Nothing on the horizon. All quiet.</p>
	{:else}
		<ul class="strip">
			{#each queue as { r, score, reasons, sev } (slug(r))}
				<li class="hrow sev-{sev}">
					<a href="/repo/{slug(r)}">
						<b class="hscore sev-{sev}">{score}</b>
						<span class="hname">{slug(r)}</span>
						<span class="meter"><span class="fill" style="width: {Math.min(100, (score / worst) * 100)}%; background: var(--{sev})"></span></span>
						<span class="hreason">{reasons[0]?.text}</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.horizon {
		width: 100%;
	}
	.calm {
		color: var(--good);
		font-weight: 650;
		margin: 0;
	}
	.strip {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.hrow a {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 10px;
		border: 1px solid var(--border);
		border-left: 5px solid var(--lcars-d);
		border-radius: 999px 8px 8px 999px;
		text-decoration: none;
		color: var(--ink);
	}
	.hrow a:hover {
		border-color: var(--axis);
	}
	.hscore {
		font-variant-numeric: tabular-nums;
		font-size: 12px;
	}
	.hname {
		font-weight: 650;
		font-size: 13px;
	}
	.meter {
		flex: none;
		width: 54px;
		height: 5px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--axis) 35%, transparent);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 999px;
	}
	.hreason {
		color: var(--ink-2);
		font-size: 11.5px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
