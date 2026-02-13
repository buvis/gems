<script lang="ts">
	interface Props {
		value: unknown;
		editable?: boolean;
		onchange?: (value: string[], event: Event) => void;
	}
	let { value, editable = false, onchange }: Props = $props();

	const tags = $derived.by(() => {
		if (Array.isArray(value)) return value.map(String);
		if (typeof value === 'string') return value.split(',').map((s: string) => s.trim()).filter(Boolean);
		return [] as string[];
	});

	let inputValue = $state('');

	function addTag(e: KeyboardEvent) {
		if (e.key !== 'Enter' || !inputValue.trim()) return;
		const newTags = [...tags, inputValue.trim()];
		inputValue = '';
		onchange?.(newTags, e);
	}

	function removeTag(idx: number, e: MouseEvent) {
		const newTags = tags.filter((_: string, i: number) => i !== idx);
		onchange?.(newTags, e);
	}
</script>

<div class="tags-wrap">
	{#each tags as tag, idx}
		<span class="tag-chip">
			{tag}
			{#if editable}
				<button class="tag-remove" onclick={(e) => removeTag(idx, e)}>x</button>
			{/if}
		</span>
	{/each}
	{#if editable}
		<input
			class="tag-input"
			type="text"
			placeholder="add..."
			bind:value={inputValue}
			onkeydown={addTag}
		/>
	{/if}
</div>

<style>
	.tags-wrap {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		align-items: center;
	}
	.tag-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		padding: 0.1rem 0.5rem;
		background: var(--accent-dim);
		color: var(--text-primary);
		border-radius: 999px;
		font-size: 0.75rem;
		font-family: var(--font-mono);
	}
	.tag-remove {
		background: none;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		font-size: 0.7rem;
		padding: 0;
		line-height: 1;
	}
	.tag-remove:hover {
		color: var(--danger);
	}
	.tag-input {
		padding: 0.1rem 0.4rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-size: 0.75rem;
		font-family: var(--font-mono);
		outline: none;
		width: 5rem;
	}
	.tag-input:focus {
		border-color: var(--accent);
	}
</style>
