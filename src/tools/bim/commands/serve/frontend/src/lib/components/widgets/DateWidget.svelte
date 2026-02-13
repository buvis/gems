<script lang="ts">
	interface Props {
		value: unknown;
		onchange: (value: string, event: Event) => void;
	}
	let { value, onchange }: Props = $props();

	function toInputDate(v: unknown): string {
		if (!v) return '';
		const s = String(v);
		return s.length >= 10 ? s.slice(0, 10) : s;
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange(target.value, e);
	}
</script>

<input
	class="date-input"
	type="date"
	value={toInputDate(value)}
	onchange={handleInput}
/>

<style>
	.date-input {
		padding: 0.2rem 0.4rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-family: var(--font-mono);
		font-size: 0.8rem;
		outline: none;
		cursor: pointer;
	}
	.date-input:focus {
		border-color: var(--accent);
	}
	.date-input::-webkit-calendar-picker-indicator {
		filter: invert(0.7);
	}
</style>
