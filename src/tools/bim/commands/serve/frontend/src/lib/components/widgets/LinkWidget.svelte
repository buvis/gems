<script lang="ts">
	import { openFile } from '$lib/api';

	interface Props {
		value: unknown;
		filePath?: string;
	}
	let { value, filePath }: Props = $props();

	let openError = $state<string | null>(null);

	const display = $derived(String(value ?? ''));

	async function handleClick(e: MouseEvent) {
		e.preventDefault();
		if (filePath) {
			openError = null;
			try {
				await openFile(filePath);
			} catch (err) {
				openError = String(err);
			}
		}
	}
</script>

{#if filePath}
	<button class="link-cell" onclick={handleClick} title={filePath}>{display}</button>
	{#if openError}
		<span class="link-error" role="alert" title={openError}>{openError}</span>
	{/if}
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
	.link-error {
		color: var(--danger);
		font-size: 0.85em;
		margin-left: 0.5rem;
	}
</style>
