<script lang="ts">
	import '../app.css';
	import type { Snippet } from 'svelte';

	interface Props {
		children: Snippet;
	}
	let { children }: Props = $props();
</script>

<div class="shell">
	{@render children()}
</div>

<style>
	.shell {
		display: flex;
		height: 100vh;
		overflow: hidden;
	}
</style>
