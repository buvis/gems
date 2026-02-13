<script lang="ts">
	import { queries, activeQuery } from '$lib/stores';

	interface Props {
		onselect: (name: string) => void;
	}
	let { onselect }: Props = $props();

	let search = $state('');

	const filtered = $derived.by(() => {
		const names = Object.keys($queries).sort();
		if (!search) return names;
		const q = search.toLowerCase();
		return names.filter((n) => n.toLowerCase().includes(q));
	});
</script>

<nav class="picker">
	<h2 class="picker-title">Queries</h2>
	<div class="picker-search-wrap">
		<input
			class="picker-search"
			type="text"
			placeholder="Search..."
			bind:value={search}
		/>
	</div>
	<ul class="picker-list">
		{#each filtered as name}
			<li>
				<button
					class="picker-item"
					class:active={$activeQuery === name}
					onclick={() => onselect(name)}
				>
					{name.replaceAll('_', ' ')}
				</button>
			</li>
		{/each}
		{#if filtered.length === 0}
			<li class="picker-empty">No matches</li>
		{/if}
	</ul>
</nav>

<style>
	.picker {
		padding: 1rem 0;
	}
	.picker-title {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-muted);
		padding: 0 1rem 0.75rem;
	}
	.picker-search-wrap {
		padding: 0 0.75rem 0.5rem;
	}
	.picker-search {
		width: 100%;
		padding: 0.3rem 0.5rem;
		background: var(--bg-primary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-family: var(--font-mono);
		font-size: 0.75rem;
		outline: none;
		transition: border-color var(--transition);
	}
	.picker-search:focus {
		border-color: var(--accent);
	}
	.picker-search::placeholder {
		color: var(--text-muted);
	}
	.picker-list {
		list-style: none;
	}
	.picker-item {
		display: block;
		width: 100%;
		padding: 0.5rem 1rem;
		background: none;
		border: none;
		text-align: left;
		color: var(--text-secondary);
		cursor: pointer;
		font-size: 0.85rem;
		transition: all var(--transition);
		border-left: 2px solid transparent;
	}
	.picker-item:hover {
		background: var(--bg-tertiary);
		color: var(--text-primary);
	}
	.picker-item.active {
		color: var(--accent);
		border-left-color: var(--accent);
		background: var(--bg-tertiary);
	}
	.picker-empty {
		padding: 0.5rem 1rem;
		color: var(--text-muted);
		font-size: 0.8rem;
	}
</style>
