<script>
	// Portfolio trend sparkline. Ported from the SPA. A single data point has no
	// line to draw, so it renders as a DOT (never an error / empty SVG); two or
	// more points draw a polyline. Values are non-negative counts.
	let { values = [], w = 130, h = 26 } = $props();
	const max = $derived(Math.max(...values, 1));
	const coords = $derived(
		values.map((v, i) => {
			const x = (i / Math.max(values.length - 1, 1)) * (w - 4) + 2;
			const y = h - 3 - (v / max) * (h - 8);
			return { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)) };
		})
	);
	const pts = $derived(coords.map((c) => `${c.x},${c.y}`).join(' '));
	const single = $derived(coords.length === 1);
</script>

<svg width={w} height={h} viewBox="0 0 {w} {h}" role="img" aria-label="portfolio trend">
	{#if single}
		<circle class="dot" cx={w / 2} cy={coords[0].y} r="3" />
	{:else if coords.length >= 2}
		<polyline points={pts} fill="none" stroke="var(--seq-4)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
	{/if}
</svg>

<style>
	.dot {
		fill: var(--seq-4);
	}
</style>
