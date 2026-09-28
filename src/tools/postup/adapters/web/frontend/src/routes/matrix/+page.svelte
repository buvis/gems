<script>
	import { getContext } from 'svelte';
	import { allTodos, quadrant, safeUrl } from '$lib/derive.js';
	import { loadDone, saveDone } from '$lib/done.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const enriched = $derived(portfolio.state.enriched);

	const repos = $derived(payload?.repos ?? []);
	const epics = $derived(payload?.epics ?? null);
	const external = $derived(payload?.external ?? null);

	const todos = $derived(allTodos(repos, epics, external));

	let done = $state(loadDone());
	let hideDone = $state(true);

	// Solo-dev Eisenhower quadrants (ported from the SPA Matrix). Judgment fields
	// (importance/effort) come from enrichment; without it every mechanical todo
	// carries the deterministic defaults, so the matrix still plots — but it can
	// only ever be a mechanical list, which the "not enriched" cue makes explicit.
	const QUADS = [
		['do', 'Do now', 'urgent and important — start here', 'critical'],
		['schedule', 'Schedule', 'important, waits for a real slot', 'serious'],
		['delegate', 'Delegate to agents', 'not important — dispatch a command', 'warning'],
		['drop', 'Drop / batch', 'batch monthly, or let it rot in peace', 'muted']
	];
	const byQuad = $derived.by(() => {
		const m = { do: [], schedule: [], delegate: [], drop: [] };
		for (const t of todos) m[quadrant(t)].push(t);
		return m;
	});

	function toggle(id) {
		const s = new Set(done);
		if (s.has(id)) s.delete(id);
		else s.add(id);
		done = s;
		saveDone(s);
	}
</script>

<div class="bar">
	<span class="count">
		urgency from age and severity · importance from consequence (security, data loss, users waiting)
	</span>
	{#if !enriched}
		<span class="lbl not-enriched" title="epics.json absent — judgment todos add the importance axis">
			not enriched · mechanical todos only
		</span>
	{/if}
	<button class="chip" class:active={hideDone} aria-pressed={hideDone} onclick={() => (hideDone = !hideDone)}>
		hide done
	</button>
</div>

<div class="matrix">
	{#each QUADS as [q, title, hint, tone] (q)}
		{@const items = byQuad[q]}
		{@const open = items.filter((t) => !done.has(t.id))}
		<section class="quad q-{q}">
			<h2 style="color: var(--{tone})">{title} · {open.length}</h2>
			<p class="hint">{hint}</p>
			{#each hideDone ? open : items as t (t.id)}
				{@const url = safeUrl(t.url)}
				<div class="item" class:isdone={done.has(t.id)}>
					<input type="checkbox" id="m-{t.id}" checked={done.has(t.id)} onchange={() => toggle(t.id)} />
					<label for="m-{t.id}">
						<span class="action">
							{#if url}<a href={url} target="_blank" rel="noreferrer">{t.action}</a>{:else}{t.action}{/if}
						</span>
						{#if t.why}<span class="why">{t.why}</span>{/if}
					</label>
					{#if t.agent}<span class="lbl agent">→ {t.agent}</span>{/if}
					{#if t.effort === 'quick'}<span class="lbl">quick</span>{/if}
					<a class="lbl repo" href="/repo/{t.repo}">{t.repo}</a>
				</div>
			{:else}
				<p class="empty">nothing here</p>
			{/each}
		</section>
	{/each}
</div>

<style>
	.bar {
		display: flex;
		gap: 10px;
		align-items: center;
		flex-wrap: wrap;
		margin-bottom: 14px;
	}
	.count {
		color: var(--muted);
		font-size: 12px;
	}
	.not-enriched {
		border-color: var(--serious);
		color: var(--serious);
	}
	.matrix {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	@media (max-width: 900px) {
		.matrix {
			grid-template-columns: 1fr;
		}
	}
	.quad {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 12px 14px;
		min-height: 140px;
	}
	.q-do {
		border-top: 5px solid var(--critical);
	}
	.q-schedule {
		border-top: 5px solid var(--serious);
	}
	.q-delegate {
		border-top: 5px solid var(--lcars-c);
	}
	.q-drop {
		border-top: 5px solid var(--grid);
	}
	.quad h2 {
		font-family: var(--display);
		font-size: 14px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin: 0;
	}
	.hint {
		color: var(--muted);
		font-size: 11.5px;
		margin: 2px 0 10px;
	}
	.item {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 6px 8px;
		border: 1px solid var(--grid);
		border-radius: 7px;
		margin-bottom: 5px;
		background: color-mix(in srgb, var(--plane) 40%, var(--surface));
	}
	.item input {
		margin: 0;
		accent-color: var(--accent);
	}
	.item label {
		flex: 1;
		cursor: pointer;
		min-width: 0;
	}
	.isdone .action,
	.isdone .action a {
		text-decoration: line-through;
		color: var(--muted);
	}
	.why {
		color: var(--muted);
		font-size: 12px;
		margin-left: 8px;
	}
	.agent {
		color: var(--accent);
		border-color: var(--accent);
	}
	.repo {
		white-space: nowrap;
	}
	.empty {
		color: var(--muted);
		font-size: 12.5px;
	}
</style>
