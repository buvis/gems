<script lang="ts">
	interface Props {
		message: string;
		onconfirm: () => void;
		oncancel: () => void;
	}
	let { message, onconfirm, oncancel }: Props = $props();

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') oncancel();
		if (e.key === 'Enter') onconfirm();
	}
</script>

<svelte:window onkeydown={handleKey} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="overlay" onclick={oncancel}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="dialog" onclick={(e) => e.stopPropagation()}>
		<p class="dialog-message">{message}</p>
		<div class="dialog-actions">
			<button class="btn btn-cancel" onclick={oncancel}>Cancel</button>
			<button class="btn btn-confirm" onclick={onconfirm}>Confirm</button>
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}
	.dialog {
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 1.5rem;
		max-width: 400px;
		width: 90%;
	}
	.dialog-message {
		color: var(--text-primary);
		font-size: 0.9rem;
		margin-bottom: 1.25rem;
		line-height: 1.5;
	}
	.dialog-actions {
		display: flex;
		gap: 0.75rem;
		justify-content: flex-end;
	}
	.btn {
		padding: 0.4rem 1rem;
		border-radius: var(--radius);
		font-size: 0.8rem;
		font-family: var(--font-mono);
		cursor: pointer;
		border: 1px solid var(--border);
		transition: all var(--transition);
	}
	.btn-cancel {
		background: var(--bg-tertiary);
		color: var(--text-secondary);
	}
	.btn-cancel:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
	.btn-confirm {
		background: var(--accent-dim);
		color: var(--text-primary);
		border-color: var(--accent);
	}
	.btn-confirm:hover {
		background: var(--accent);
	}
</style>
