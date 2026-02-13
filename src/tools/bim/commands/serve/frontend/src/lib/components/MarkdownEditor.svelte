<script lang="ts">
	import { marked } from 'marked';

	interface Props {
		content: string;
		editable?: boolean;
		onsave?: (content: string) => void;
	}
	let { content, editable = false, onsave }: Props = $props();

	let editing = $state(false);
	let editText = $state('');

	const renderedHtml = $derived(marked.parse(content || '') as string);

	function startEdit() {
		if (!editable) return;
		editing = true;
		editText = content;
	}

	function save() {
		editing = false;
		if (editText !== content) {
			onsave?.(editText);
		}
	}

	function cancel() {
		editing = false;
		editText = content;
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') cancel();
		if (e.key === 's' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			save();
		}
	}
</script>

{#if editing}
	<div class="editor-wrap">
		<textarea
			class="md-textarea"
			bind:value={editText}
			onkeydown={handleKey}
		></textarea>
		<div class="editor-actions">
			<button class="btn btn-save" onclick={save}>Save</button>
			<button class="btn btn-cancel" onclick={cancel}>Cancel</button>
			<span class="hint">Cmd+S to save, Esc to cancel</span>
		</div>
	</div>
{:else}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="md-preview"
		class:editable
		onclick={startEdit}
	>
		{@html renderedHtml}
	</div>
{/if}

<style>
	.md-preview {
		font-size: 0.85rem;
		line-height: 1.6;
		color: var(--text-primary);
	}
	.md-preview.editable {
		cursor: pointer;
		border-radius: var(--radius);
		padding: 0.5rem;
		transition: background var(--transition);
	}
	.md-preview.editable:hover {
		background: var(--bg-tertiary);
	}
	.md-preview :global(h1),
	.md-preview :global(h2),
	.md-preview :global(h3) {
		font-family: var(--font-sans);
		color: var(--text-primary);
		margin: 0.75rem 0 0.35rem;
	}
	.md-preview :global(h2) {
		font-size: 1rem;
	}
	.md-preview :global(h3) {
		font-size: 0.9rem;
	}
	.md-preview :global(p) {
		margin: 0.3rem 0;
	}
	.md-preview :global(ul),
	.md-preview :global(ol) {
		padding-left: 1.25rem;
		margin: 0.3rem 0;
	}
	.md-preview :global(code) {
		font-family: var(--font-mono);
		font-size: 0.8rem;
		background: var(--bg-tertiary);
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
	}
	.md-preview :global(pre) {
		background: var(--bg-tertiary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
		margin: 0.5rem 0;
	}
	.md-preview :global(pre code) {
		background: none;
		padding: 0;
	}
	.md-preview :global(a) {
		color: var(--accent);
	}
	.md-preview :global(blockquote) {
		border-left: 3px solid var(--accent-dim);
		padding-left: 0.75rem;
		margin: 0.5rem 0;
		color: var(--text-secondary);
	}
	.editor-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.md-textarea {
		width: 100%;
		min-height: 200px;
		padding: 0.75rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--accent);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-family: var(--font-mono);
		font-size: 0.8rem;
		line-height: 1.5;
		resize: vertical;
		outline: none;
	}
	.editor-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.btn {
		padding: 0.3rem 0.7rem;
		border-radius: var(--radius);
		font-size: 0.75rem;
		font-family: var(--font-mono);
		cursor: pointer;
		border: 1px solid var(--border);
		transition: all var(--transition);
	}
	.btn-save {
		background: var(--accent-dim);
		color: var(--text-primary);
		border-color: var(--accent);
	}
	.btn-save:hover {
		background: var(--accent);
	}
	.btn-cancel {
		background: var(--bg-tertiary);
		color: var(--text-secondary);
	}
	.btn-cancel:hover {
		background: var(--bg-hover);
	}
	.hint {
		font-size: 0.7rem;
		color: var(--text-muted);
		font-family: var(--font-mono);
	}
</style>
