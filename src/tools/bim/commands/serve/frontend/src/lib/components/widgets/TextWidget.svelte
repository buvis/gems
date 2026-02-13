<script lang="ts">
	interface Props {
		value: unknown;
	}
	let { value }: Props = $props();
</script>

<span class="text-cell">{String(value ?? '')}</span>

<style>
	.text-cell {
		color: var(--text-primary);
	}
</style>
