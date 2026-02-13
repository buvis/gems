<script lang="ts">
	import type { ItemViewSpec, PropertyDef, ActionSpec, ZettelData } from '$lib/api';
	import { fetchZettel, patchZettel } from '$lib/api';
	import PropertyField from './PropertyField.svelte';
	import MarkdownEditor from './MarkdownEditor.svelte';
	import ActionBar from './ActionBar.svelte';

	interface Props {
		row: Record<string, unknown>;
		itemSpec: ItemViewSpec | null;
		schema: Record<string, PropertyDef>;
		actions: ActionSpec[];
		onclose: () => void;
		onrefresh?: () => void;
	}
	let { row, itemSpec, schema, actions, onclose, onrefresh }: Props = $props();

	let zettel = $state<ZettelData | null>(null);
	let loadError = $state<string | null>(null);

	const filePath = $derived(row['file_path'] as string | undefined);

	const spec = $derived(itemSpec ?? defaultItemSpec());

	const title = $derived(resolveTemplate(spec.title, row));
	const subtitle = $derived(spec.subtitle ? resolveTemplate(spec.subtitle, row) : null);

	function defaultItemSpec(): ItemViewSpec {
		return {
			title: '{title}',
			subtitle: null,
			sections: [
				{
					heading: 'Properties',
					fields: Object.keys(schema)
						.filter((k) => k !== 'file_path')
						.map((k) => ({ field: k, editable: false, widget: null })),
					section: null,
					editable: false,
					display: 'auto'
				}
			]
		};
	}

	function resolveTemplate(tpl: string, data: Record<string, unknown>): string {
		return tpl.replace(/\{(\w+)\}/g, (_, key) => String(data[key] ?? ''));
	}

	$effect(() => {
		if (filePath) {
			loadZettel(filePath);
		}
	});

	async function loadZettel(fp: string) {
		loadError = null;
		try {
			zettel = await fetchZettel(fp);
		} catch (e) {
			loadError = String(e);
		}
	}

	async function handleFieldChange(field: string, value: unknown, target = 'metadata') {
		if (!filePath) return;
		await patchZettel(filePath, field, value, target);
		await loadZettel(filePath);
		onrefresh?.();
	}

	async function handleSectionSave(heading: string, body: string) {
		if (!filePath) return;
		await patchZettel(filePath, heading, body, 'section');
		await loadZettel(filePath);
		onrefresh?.();
	}

	function getFieldValue(field: string): unknown {
		if (!zettel) return row[field];
		return zettel.metadata[field] ?? zettel.reference[field] ?? row[field];
	}

	function getSectionBody(sectionHeading: string): string {
		if (!zettel) return '';
		const match = zettel.sections.find((s) => s.heading === sectionHeading);
		return match?.body ?? '';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="panel-overlay" role="presentation" onclick={onclose}></div>
<aside class="item-panel">
	<header class="panel-header">
		<div class="panel-titles">
			<h2 class="panel-title">{title}</h2>
			{#if subtitle}
				<p class="panel-subtitle">{subtitle}</p>
			{/if}
		</div>
		<button class="close-btn" onclick={onclose}>x</button>
	</header>

	{#if loadError}
		<div class="panel-error">{loadError}</div>
	{/if}

	<ActionBar
		{actions}
		scope="item"
		filePath={filePath ?? ''}
		{row}
		onactiondone={() => { if (filePath) loadZettel(filePath); onrefresh?.(); }}
	/>

	<div class="panel-body">
		{#each spec.sections as section}
			<div class="section">
				<h3 class="section-heading">{section.heading}</h3>
				{#if section.fields}
					{#each section.fields as f}
						<PropertyField
							field={f.field}
							value={getFieldValue(f.field)}
							{schema}
							editable={f.editable}
							widget={f.widget}
							filePath={filePath}
							onchange={handleFieldChange}
						/>
					{/each}
				{:else if section.section}
					<MarkdownEditor
						content={getSectionBody(section.section)}
						editable={section.editable}
						onsave={(body) => handleSectionSave(section.section!, body)}
					/>
				{/if}
			</div>
		{/each}

		{#if zettel && spec.sections.length === 0}
			{#each zettel.sections as sec}
				<div class="section">
					<h3 class="section-heading">{sec.heading}</h3>
					<MarkdownEditor content={sec.body} />
				</div>
			{/each}
		{/if}
	</div>
</aside>

<style>
	.panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 90;
	}
	.item-panel {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(560px, 85vw);
		background: var(--bg-primary);
		border-left: 1px solid var(--border);
		z-index: 100;
		display: flex;
		flex-direction: column;
		animation: slide-in 200ms ease-out;
	}
	@keyframes slide-in {
		from {
			transform: translateX(100%);
		}
		to {
			transform: translateX(0);
		}
	}
	.panel-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		padding: 1.25rem 1.5rem;
		border-bottom: 1px solid var(--border);
		flex-shrink: 0;
	}
	.panel-titles {
		min-width: 0;
	}
	.panel-title {
		font-family: var(--font-sans);
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.panel-subtitle {
		font-size: 0.8rem;
		color: var(--text-secondary);
		margin-top: 0.15rem;
	}
	.close-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 1.1rem;
		font-family: var(--font-mono);
		cursor: pointer;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
		line-height: 1;
		flex-shrink: 0;
	}
	.close-btn:hover {
		color: var(--text-primary);
		background: var(--bg-tertiary);
	}
	.panel-error {
		padding: 0.5rem 1.5rem;
		color: var(--danger);
		font-size: 0.8rem;
		font-family: var(--font-mono);
	}
	.panel-body {
		flex: 1;
		overflow-y: auto;
		padding: 1rem 1.5rem;
	}
	.section {
		margin-bottom: 1.5rem;
	}
	.section-heading {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--accent);
		margin-bottom: 0.5rem;
		padding-bottom: 0.35rem;
		border-bottom: 1px solid var(--border);
	}
</style>
