<script>
	import { getContext } from 'svelte';
	import { allTodos, safeUrl } from '$lib/derive.js';
	import { loadDone, saveDone } from '$lib/done.js';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);

	const repos = $derived(payload?.repos ?? []);
	const epics = $derived(payload?.epics ?? null);
	const external = $derived(payload?.external ?? null);

	const todos = $derived(allTodos(repos, epics, external));

	let done = $state(loadDone());
	let hideDone = $state(false);

	const groups = $derived(
		['now', 'soon', 'later'].map((u) => ({
			u,
			all: todos.filter((t) => t.urgency === u),
			shown: todos.filter((t) => t.urgency === u && !(hideDone && done.has(t.id)))
		}))
	);
	const openCount = $derived(todos.filter((t) => !done.has(t.id)).length);

	function toggle(id) {
		const s = new Set(done);
		if (s.has(id)) s.delete(id);
		else s.add(id);
		done = s;
		saveDone(s);
	}
</script>

<div class="bar">
	<span class="count"><b>{openCount}</b> open follow-ups · checked state survives regeneration</span>
	<button class="chip" class:active={hideDone} aria-pressed={hideDone} onclick={() => (hideDone = !hideDone)}>
		hide done
	</button>
</div>

{#each groups as { u, all, shown } (u)}
	{#if all.length}
		<section class="sec">
			<h2 class="u-{u}">{u} · {all.filter((t) => !done.has(t.id)).length} open</h2>
			{#each shown as t (t.id)}
				{@const url = safeUrl(t.url)}
				<div class="todo" class:isdone={done.has(t.id)}>
					<input type="checkbox" id={t.id} checked={done.has(t.id)} onchange={() => toggle(t.id)} />
					<label for={t.id}>
						<span class="action">
							{#if url}<a href={url} target="_blank" rel="noreferrer">{t.action}</a>{:else}{t.action}{/if}
						</span>
						{#if t.why}<span class="why">{t.why}</span>{/if}
					</label>
					{#if t.agent}<span class="lbl agent">→ {t.agent}</span>{/if}
					<span class="lbl">{t.kind}{t.manual ? ' ✦' : ''}</span>
					<span class="lbl repo">{t.repo}</span>
				</div>
			{/each}
		</section>
	{/if}
{/each}

{#if todos.length === 0}
	<p class="empty">Nothing to do. Enjoy it.</p>
{/if}

<style>
	.bar {
		display: flex;
		gap: 10px;
		align-items: center;
		flex-wrap: wrap;
		margin-bottom: 8px;
	}
	.count {
		color: var(--ink-2);
	}
	.u-now {
		color: var(--critical);
	}
	.u-soon {
		color: var(--serious);
	}
	.u-later {
		color: var(--muted);
	}
	.todo {
		display: flex;
		align-items: baseline;
		gap: 10px;
		padding: 7px 10px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 7px;
		margin-bottom: 5px;
	}
	.todo:nth-of-type(even) {
		background: color-mix(in srgb, var(--plane) 45%, var(--surface));
	}
	.todo input {
		margin: 0;
		accent-color: var(--accent);
	}
	.todo label {
		flex: 1;
		cursor: pointer;
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
		margin-top: 20px;
	}
</style>
