<script>
	import { getContext } from 'svelte';
	import { page } from '$app/state';
	import { slug } from '$lib/derive.js';
	import RepoDetail from './RepoDetail.svelte';

	const portfolio = getContext('portfolio');
	const payload = $derived(portfolio.state.payload);
	const repos = $derived(payload?.repos ?? []);
	const epics = $derived(payload?.epics ?? null);

	// The route param is the "owner/name" slug (a rest param, since it holds a
	// slash). Resolve it against the loaded portfolio; an unknown slug renders a
	// not-found cue rather than crashing. Presentation lives in RepoDetail.
	const name = $derived(decodeURIComponent(page.params.name ?? ''));
	const repo = $derived(repos.find((r) => slug(r) === name) ?? null);
</script>

{#if repo}
	<RepoDetail {repo} {epics} />
{:else}
	<p class="notfound">No repo <span class="mono">{name}</span> in this portfolio. <a href="/repos">Back to Repos</a></p>
{/if}

<style>
	.notfound {
		color: var(--muted);
		margin-top: 40px;
	}
</style>
