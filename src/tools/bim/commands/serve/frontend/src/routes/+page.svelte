<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { fetchQueries, execQuery, patchZettel } from '$lib/api';
	import type { ExecResult } from '$lib/api';
	import { connectSSE, onFileChange, disconnectSSE } from '$lib/sse';
	import { queries, activeQuery, queryResult, loading, error, selectedRow } from '$lib/stores';
	import QueryPicker from '$lib/components/QueryPicker.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import KanbanBoard from '$lib/components/KanbanBoard.svelte';
	import ItemPanel from '$lib/components/ItemPanel.svelte';
	import ActionBar from '$lib/components/ActionBar.svelte';

	let unsubSSE: (() => void) | null = null;

	onMount(async () => {
		const qs = await fetchQueries();
		queries.set(qs);
		connectSSE();
		unsubSSE = onFileChange(() => {
			if ($activeQuery) runQuery($activeQuery);
		});
	});

	onDestroy(() => {
		unsubSSE?.();
		disconnectSSE();
	});

	async function runQuery(name: string) {
		activeQuery.set(name);
		loading.set(true);
		error.set(null);
		selectedRow.set(null);
		try {
			const result: ExecResult = await execQuery(name);
			queryResult.set(result);
		} catch (e) {
			error.set(String(e));
			queryResult.set(null);
		} finally {
			loading.set(false);
		}
	}

	async function handlePatch(filePath: string, field: string, value: unknown): Promise<void> {
		await patchZettel(filePath, field, value);
	}

	function handleRowClick(row: Record<string, unknown>) {
		selectedRow.set(row);
	}

	function closePanel() {
		selectedRow.set(null);
	}

	function refreshQuery() {
		if ($activeQuery) runQuery($activeQuery);
	}

	const dashboardTitle = $derived($queryResult?.dashboard?.title ?? $activeQuery?.replaceAll('_', ' ') ?? '');
	const listActions = $derived($queryResult?.actions ?? []);
</script>

<aside class="sidebar">
	<div class="sidebar-header">
		<span class="logo">bim</span>
	</div>
	<QueryPicker onselect={runQuery} />
</aside>

<main class="content">
	{#if !$activeQuery}
		<div class="empty">
			<p class="empty-text">Pick a query from the sidebar</p>
		</div>
	{:else}
		<header class="content-header">
			<h1 class="title">{dashboardTitle}</h1>
			{#if $loading}
				<span class="badge loading-badge">loading...</span>
			{/if}
		</header>

		{#if $error}
			<div class="error-banner">{$error}</div>
		{/if}

		{#if $queryResult}
			<ActionBar
				actions={listActions}
				scope="list"
				onactiondone={refreshQuery}
			/>
			{#if $queryResult.output?.format === 'kanban' && $queryResult.output?.group_by}
				<KanbanBoard
					rows={$queryResult.rows}
					columns={$queryResult.columns}
					groupBy={$queryResult.output.group_by}
					schema={$queryResult.schema}
					onpatch={handlePatch}
					onrowclick={handleRowClick}
				/>
			{:else}
				<DataTable
					rows={$queryResult.rows}
					columns={$queryResult.columns}
					schema={$queryResult.schema}
					onpatch={handlePatch}
					onrowclick={handleRowClick}
				/>
			{/if}
		{/if}
	{/if}
</main>

{#if $selectedRow && $queryResult}
	<ItemPanel
		row={$selectedRow}
		itemSpec={$queryResult.item}
		schema={$queryResult.schema}
		actions={$queryResult.actions}
		onclose={closePanel}
		onrefresh={refreshQuery}
	/>
{/if}

<style>
	.sidebar {
		width: 240px;
		min-width: 240px;
		background: var(--bg-secondary);
		border-right: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		overflow-y: auto;
	}
	.sidebar-header {
		padding: 1rem;
		border-bottom: 1px solid var(--border);
	}
	.logo {
		font-family: var(--font-mono);
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--accent);
		letter-spacing: 0.05em;
	}
	.content {
		flex: 1;
		padding: 1.5rem 2rem;
		overflow-y: auto;
	}
	.content-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}
	.title {
		font-family: var(--font-sans);
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--text-primary);
		text-transform: capitalize;
	}
	.badge {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
	}
	.loading-badge {
		background: var(--accent-dim);
		color: var(--text-primary);
		animation: pulse 1.2s ease-in-out infinite;
	}
	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}
	.empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
	}
	.empty-text {
		color: var(--text-muted);
		font-size: 1rem;
	}
	.error-banner {
		padding: 0.5rem 0.75rem;
		margin-bottom: 1rem;
		background: color-mix(in srgb, var(--danger) 15%, transparent);
		border: 1px solid var(--danger);
		border-radius: var(--radius);
		color: var(--danger);
		font-size: 0.85rem;
		font-family: var(--font-mono);
	}
</style>
