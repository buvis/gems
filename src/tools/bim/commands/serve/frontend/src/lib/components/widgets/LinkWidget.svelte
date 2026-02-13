<script lang="ts">
	import { openFile } from '$lib/api';

	interface Props {
		value: unknown;
		filePath?: string;
	}
	let { value, filePath }: Props = $props();

	const display = $derived(String(value ?? ''));

	function handleClick(e: MouseEvent) {
		e.preventDefault();
		if (filePath) openFile(filePath);
	}
</script>

{#if filePath}
	<button class="link-cell" onclick={handleClick} title={filePath}>{display}</button>
{:else}
	<span>{display}</span>
{/if}

<style>
	.link-cell {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		font-weight: 500;
		font-size: inherit;
		cursor: pointer;
		text-align: left;
	}
	.link-cell:hover {
		text-decoration: underline;
	}
</style>
