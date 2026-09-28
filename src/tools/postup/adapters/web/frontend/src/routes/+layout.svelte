<script>
	import '../app.css';
	import { setContext } from 'svelte';
	import { page } from '$app/state';
	import { loadPayload } from '$lib/payload.js';
	import { allTodos, slug, ago } from '$lib/derive.js';
	import { pruneDone, isStorageBlocked } from '$lib/done.js';

	let { children } = $props();

	// The single payload seam: the layout is the ONE place that loads the
	// payload; views read it from context. Loaded once on mount.
	let state = $state({ needsCollect: true, enriched: false, payload: null, error: null });
	let loaded = $state(false);
	let storageBlocked = $state(false);

	$effect(() => {
		loadPayload().then((s) => {
			state = s;
			if (!s.needsCollect && s.payload) {
				const ids = new Set(
					allTodos(s.payload.repos, s.payload.epics, s.payload.external).map((t) => t.id)
				);
				pruneDone(ids);
				storageBlocked = isStorageBlocked();
			}
			loaded = true;
		});
	});

	// Views pull the loaded state from context rather than re-loading.
	setContext('portfolio', {
		get state() {
			return state;
		}
	});

	const repos = $derived(state.payload?.repos ?? []);
	const epics = $derived(state.payload?.epics ?? null);
	const external = $derived(state.payload?.external ?? null);
	const todos = $derived(
		state.payload ? allTodos(repos, epics, external) : []
	);

	const TABS = [
		{ href: '/', id: 'brief', label: 'Brief' },
		{ href: '/todos', id: 'todos', label: 'Todos' },
		{ href: '/repos', id: 'repos', label: 'Repos' }
	];
	const counts = $derived({ brief: null, todos: todos.length, repos: repos.length });
	const activePath = $derived(page.url.pathname);
</script>

<div class="shell">
	<header>
		<h1>Portfolio Standup</h1>
		{#if loaded && !state.needsCollect}
			<span class="meta">generated {ago(state.payload.generated_at)} · window {state.payload.since_days}d</span>
			{#if !state.enriched}
				<span class="lbl not-enriched" title="epics.json absent — run postup enrich for narrative + judgment todos">not enriched</span>
			{/if}
			{#if storageBlocked}
				<span class="meta">Checked state will not persist: this browser is blocking local storage.</span>
			{/if}
		{/if}
		<nav aria-label="Sections">
			{#each TABS as t (t.id)}
				<a href={t.href} class:active={activePath === t.href} aria-current={activePath === t.href ? 'page' : undefined}>
					{t.label}{#if counts[t.id] != null}<span class="cnt">{counts[t.id]}</span>{/if}
				</a>
			{/each}
		</nav>
	</header>

	<main>
		{#if !loaded}
			<p class="state">Loading…</p>
		{:else if state.needsCollect}
			<p class="state">
				No portfolio data. Run <span class="mono">postup collect</span> first, then reload.
			</p>
		{:else}
			{@render children()}
		{/if}
	</main>
</div>

<style>
	.shell {
		min-height: 100vh;
	}
	header {
		display: flex;
		align-items: center;
		gap: 10px 14px;
		flex-wrap: wrap;
		padding: 10px 22px;
		border-bottom: 1px solid var(--grid);
	}
	h1 {
		font-size: 19px;
		margin: 0;
		padding: 3px 20px 4px;
		background: var(--lcars-a);
		color: var(--lcars-ink);
		border-radius: 999px 6px 6px 999px;
	}
	.meta {
		padding: 5px 16px 6px;
		background: var(--lcars-d);
		color: var(--surface);
		border-radius: 6px 999px 999px 6px;
		font-size: 12px;
	}
	.not-enriched {
		border-color: var(--serious);
		color: var(--serious);
	}
	nav {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		margin-left: auto;
	}
	nav a {
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.07em;
		background: var(--surface);
		border: 1px solid var(--border);
		border-left: 7px solid var(--lcars-d);
		border-radius: 999px 6px 6px 999px;
		padding: 5px 16px 5px 14px;
		cursor: pointer;
		color: var(--ink-2);
		text-decoration: none;
	}
	nav a:hover {
		border-color: var(--axis);
		border-left-color: var(--lcars-c);
	}
	nav a.active {
		background: var(--lcars-a);
		border-color: var(--lcars-a);
		color: var(--lcars-ink);
		font-weight: 600;
	}
	nav .cnt {
		margin-left: 7px;
		font-size: 11px;
		font-variant-numeric: tabular-nums;
		border-radius: 999px;
		padding: 1px 7px;
		background: color-mix(in srgb, var(--plane) 75%, transparent);
	}
	main {
		padding: 18px 22px 60px;
		max-width: 1280px;
		margin: 0 auto;
	}
	.state {
		color: var(--muted);
		margin-top: 40px;
		text-align: center;
	}
</style>
