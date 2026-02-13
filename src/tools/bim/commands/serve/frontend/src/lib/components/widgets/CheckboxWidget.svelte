<script lang="ts">
	interface Props {
		value: unknown;
		onchange: (value: boolean, event: Event) => void;
	}
	let { value, onchange }: Props = $props();

	function handleChange(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange(target.checked, e);
	}
</script>

<label class="checkbox-wrap">
	<input
		type="checkbox"
		checked={Boolean(value)}
		onchange={handleChange}
	/>
</label>

<style>
	.checkbox-wrap {
		display: inline-flex;
		align-items: center;
		cursor: pointer;
	}
	input[type='checkbox'] {
		appearance: none;
		width: 16px;
		height: 16px;
		border: 1px solid var(--border);
		border-radius: 3px;
		background: var(--bg-tertiary);
		cursor: pointer;
		position: relative;
		transition: all var(--transition);
	}
	input[type='checkbox']:checked {
		background: var(--accent-dim);
		border-color: var(--accent);
	}
	input[type='checkbox']:checked::after {
		content: '';
		position: absolute;
		left: 4px;
		top: 1px;
		width: 5px;
		height: 9px;
		border: solid var(--text-primary);
		border-width: 0 2px 2px 0;
		transform: rotate(45deg);
	}
	input[type='checkbox']:hover {
		border-color: var(--accent);
	}
</style>
