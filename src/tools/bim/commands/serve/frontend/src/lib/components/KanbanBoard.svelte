<script lang="ts">
	import type { Column, PropertyDef } from '$lib/api';
	import TextWidget from './widgets/TextWidget.svelte';
	import TagsWidget from './widgets/TagsWidget.svelte';

	interface Props {
		rows: Record<string, unknown>[];
		columns: Column[];
		groupBy: string;
		schema?: Record<string, PropertyDef>;
		onpatch: (filePath: string, field: string, value: unknown) => Promise<void>;
		onrowclick?: (row: Record<string, unknown>) => void;
	}
	let { rows, columns, groupBy, schema = {}, onpatch, onrowclick }: Props = $props();

	let filterText = $state('');

	const displayColumns = $derived(
		columns.filter((c) => {
			const key = c.field || c.label;
			return key !== 'file_path' && key !== groupBy;
		})
	);

	function colKey(col: Column): string {
		return col.label || col.field || col.expr || '?';
	}

	function resolveWidget(col: Column): string {
		if (col.widget) return col.widget;
		const fieldName = col.field || '';
		const def = schema[fieldName];
		if (!def) return 'text';
		if (def.type === 'tags') return 'tags';
		return 'text';
	}

	const filteredRows = $derived.by(() => {
		if (!filterText) return rows;
		const q = filterText.toLowerCase();
		return rows.filter((row) =>
			Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(q))
		);
	});

	const lanes = $derived.by(() => {
		const groups = new Map<string, Record<string, unknown>[]>();
		for (const row of filteredRows) {
			const key = String(row[groupBy] ?? 'Ungrouped') || 'Ungrouped';
			if (!groups.has(key)) groups.set(key, []);
			groups.get(key)!.push(row);
		}
		return groups;
	});

	function handleCardClick(row: Record<string, unknown>) {
		onrowclick?.(row);
	}
</script>

<div class="table-controls">
	<div class="filter-wrap">
		<input
			class="filter-input"
			type="text"
			placeholder="Filter cards..."
			bind:value={filterText}
		/>
		{#if filterText}
			<button class="filter-clear" onclick={() => (filterText = '')}>x</button>
		{/if}
	</div>
	<span class="row-count">{filteredRows.length} cards</span>
</div>

<div class="kanban-board">
	{#each [...lanes] as [laneName, laneRows]}
		<div class="kanban-lane">
			<div class="lane-header">
				<span class="lane-title">{laneName}</span>
				<span class="lane-count">{laneRows.length}</span>
			</div>
			<div class="lane-cards">
				{#each laneRows as row}
					<button
						class="kanban-card"
						onclick={() => handleCardClick(row)}
						type="button"
					>
						{#each displayColumns as col}
							{@const key = colKey(col)}
							{@const value = row[key]}
							{#if value != null && value !== ''}
								<div class="card-field">
									{#if resolveWidget(col) === 'tags'}
										<TagsWidget {value} />
									{:else}
										<TextWidget {value} />
									{/if}
								</div>
							{/if}
						{/each}
					</button>
				{/each}
			</div>
		</div>
	{/each}
</div>

<style>
	.table-controls {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 0;
	}
	.filter-wrap {
		position: relative;
		flex: 1;
		max-width: 320px;
	}
	.filter-input {
		width: 100%;
		padding: 0.4rem 2rem 0.4rem 0.75rem;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-family: var(--font-mono);
		font-size: 0.8rem;
		outline: none;
		transition: border-color var(--transition);
	}
	.filter-input:focus {
		border-color: var(--accent);
	}
	.filter-input::placeholder {
		color: var(--text-muted);
	}
	.filter-clear {
		position: absolute;
		right: 0.4rem;
		top: 50%;
		transform: translateY(-50%);
		background: none;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		font-size: 0.8rem;
		font-family: var(--font-mono);
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		line-height: 1;
	}
	.filter-clear:hover {
		color: var(--text-primary);
		background: var(--bg-tertiary);
	}
	.row-count {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.kanban-board {
		display: flex;
		gap: 1rem;
		overflow-x: auto;
		padding-bottom: 1rem;
		min-height: 0;
		flex: 1;
	}
	.kanban-lane {
		min-width: 260px;
		max-width: 340px;
		flex: 1;
		display: flex;
		flex-direction: column;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}
	.lane-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.6rem 0.75rem;
		border-bottom: 1px solid var(--border);
		background: var(--bg-tertiary);
		border-radius: var(--radius) var(--radius) 0 0;
	}
	.lane-title {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-secondary);
	}
	.lane-count {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		background: var(--accent-dim);
		color: var(--text-primary);
	}
	.lane-cards {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.kanban-card {
		all: unset;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.6rem 0.75rem;
		background: var(--bg-primary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		cursor: pointer;
		transition:
			border-color var(--transition),
			box-shadow var(--transition);
		font-size: 0.82rem;
		color: var(--text-primary);
	}
	.kanban-card:hover {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent-dim);
	}
	.card-field {
		line-height: 1.4;
	}
	.card-field:first-child {
		font-weight: 600;
	}
	.card-field:not(:first-child) {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}
</style>
