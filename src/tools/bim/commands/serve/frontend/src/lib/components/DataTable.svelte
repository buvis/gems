<script lang="ts">
	import type { Column, PropertyDef } from '$lib/api';
	import TextWidget from './widgets/TextWidget.svelte';
	import DateWidget from './widgets/DateWidget.svelte';
	import CheckboxWidget from './widgets/CheckboxWidget.svelte';
	import SelectWidget from './widgets/SelectWidget.svelte';
	import LinkWidget from './widgets/LinkWidget.svelte';
	import TagsWidget from './widgets/TagsWidget.svelte';

	interface Props {
		rows: Record<string, unknown>[];
		columns: Column[];
		schema?: Record<string, PropertyDef>;
		onpatch: (filePath: string, field: string, value: unknown) => Promise<void>;
		onrowclick?: (row: Record<string, unknown>) => void;
	}
	let { rows, columns, schema = {}, onpatch, onrowclick }: Props = $props();

	let sortField = $state<string | null>(null);
	let sortAsc = $state(true);
	let filterText = $state('');

	const displayColumns = $derived(columns.filter((c) => (c.field || c.label) !== 'file_path'));

	function colKey(col: Column): string {
		return col.label || col.field || col.expr || '?';
	}

	function resolveWidget(col: Column): string {
		if (col.widget) return col.widget;
		const fieldName = col.field || '';
		const def = schema[fieldName];
		if (!def) return 'text';
		switch (def.type) {
			case 'bool':
				return 'checkbox';
			case 'date':
				return 'date';
			case 'select':
				return 'select';
			case 'tags':
				return 'tags';
			case 'link':
				return 'link';
			case 'path':
				return 'text';
			default:
				return 'text';
		}
	}

	function resolveOptions(col: Column): string[] {
		if (col.options.length > 0) return col.options;
		const fieldName = col.field || '';
		return schema[fieldName]?.options ?? [];
	}

	function toggleSort(col: Column) {
		const key = colKey(col);
		if (sortField === key) {
			sortAsc = !sortAsc;
		} else {
			sortField = key;
			sortAsc = true;
		}
	}

	const filteredRows = $derived.by(() => {
		let result = rows;
		if (filterText) {
			const q = filterText.toLowerCase();
			result = result.filter((row) =>
				Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(q))
			);
		}
		if (sortField) {
			const field = sortField;
			const asc = sortAsc;
			result = [...result].sort((a, b) => {
				const va = a[field] ?? '';
				const vb = b[field] ?? '';
				if (va < vb) return asc ? -1 : 1;
				if (va > vb) return asc ? 1 : -1;
				return 0;
			});
		}
		return result;
	});

	function flash(el: HTMLElement, ok: boolean) {
		const cls = ok ? 'flash-ok' : 'flash-err';
		el.classList.add(cls);
		setTimeout(() => el.classList.remove(cls), 800);
	}

	async function handleEdit(e: Event, row: Record<string, unknown>, col: Column, value: unknown) {
		const fp = row['file_path'] as string | undefined;
		const field = col.field || col.label || '';
		if (!fp || !field) return;

		const cell = (e.target as HTMLElement).closest('td');
		try {
			await onpatch(fp, field, value);
			if (cell) flash(cell, true);
		} catch {
			if (cell) flash(cell, false);
		}
	}

	function handleRowClick(row: Record<string, unknown>) {
		onrowclick?.(row);
	}
</script>

<div class="table-controls">
	<div class="filter-wrap">
		<input
			class="filter-input"
			type="text"
			placeholder="Filter rows..."
			bind:value={filterText}
		/>
		{#if filterText}
			<button class="filter-clear" onclick={() => (filterText = '')}>x</button>
		{/if}
	</div>
	<span class="row-count">{filteredRows.length} rows</span>
</div>

<div class="table-wrap">
	<table>
		<thead>
			<tr>
				{#each displayColumns as col}
					<th onclick={() => toggleSort(col)} class:sorted={sortField === colKey(col)}>
						{colKey(col).replaceAll('_', ' ')}
						{#if sortField === colKey(col)}
							<span class="sort-arrow">{sortAsc ? '\u2191' : '\u2193'}</span>
						{/if}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each filteredRows as row}
				<tr
					class:clickable={!!onrowclick}
					onclick={() => handleRowClick(row)}
				>
					{#each displayColumns as col}
						{@const key = colKey(col)}
						{@const value = row[key]}
						{@const widget = resolveWidget(col)}
						<td>
							{#if widget === 'link'}
								<LinkWidget {value} filePath={row['file_path'] as string} />
							{:else if widget === 'checkbox' && col.editable}
								<CheckboxWidget
									{value}
									onchange={(v, e) => handleEdit(e, row, col, v)}
								/>
							{:else if widget === 'date' && col.editable}
								<DateWidget
									{value}
									onchange={(v, e) => handleEdit(e, row, col, v)}
								/>
							{:else if widget === 'select' && col.editable}
								<SelectWidget
									{value}
									options={resolveOptions(col)}
									onchange={(v, e) => handleEdit(e, row, col, v)}
								/>
							{:else if widget === 'tags'}
								<TagsWidget {value} />
							{:else if widget === 'checkbox'}
								<CheckboxWidget {value} onchange={() => {}} />
							{:else}
								<TextWidget {value} />
							{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
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
	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	thead {
		background: var(--bg-tertiary);
	}
	th {
		padding: 0.6rem 0.75rem;
		text-align: left;
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-secondary);
		cursor: pointer;
		user-select: none;
		white-space: nowrap;
		border-bottom: 1px solid var(--border);
		position: sticky;
		top: 0;
		z-index: 10;
		background: var(--bg-tertiary);
	}
	th:hover {
		color: var(--text-primary);
	}
	th.sorted {
		color: var(--accent);
	}
	.sort-arrow {
		margin-left: 0.25rem;
	}
	td {
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--border);
		vertical-align: middle;
		transition: box-shadow 0.3s ease;
	}
	:global(td.flash-ok) {
		box-shadow: inset 0 0 0 1px var(--success);
	}
	:global(td.flash-err) {
		box-shadow: inset 0 0 0 1px var(--danger);
	}
	tr:hover td {
		background: var(--bg-secondary);
	}
	tr:last-child td {
		border-bottom: none;
	}
	tr.clickable {
		cursor: pointer;
	}
</style>
