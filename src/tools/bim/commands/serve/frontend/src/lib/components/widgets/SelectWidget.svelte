<script lang="ts">
	interface Props {
		value: unknown;
		options: string[];
		onchange: (value: string, event: Event) => void;
	}
	let { value, options, onchange }: Props = $props();

	function handleChange(e: Event) {
		const target = e.target as HTMLSelectElement;
		onchange(target.value, e);
	}
</script>

<select class="select-input" value={String(value ?? '')} onchange={handleChange}>
	{#each options as opt}
		<option value={opt}>{opt}</option>
	{/each}
</select>

<style>
	.select-input {
		padding: 0.2rem 0.4rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-size: 0.8rem;
		outline: none;
		cursor: pointer;
	}
	.select-input:focus {
		border-color: var(--accent);
	}
	.select-input option {
		background: var(--bg-secondary);
		color: var(--text-primary);
	}
</style>
