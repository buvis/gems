<script lang="ts">
	import type { PropertyDef } from '$lib/api';
	import TextWidget from './widgets/TextWidget.svelte';
	import DateWidget from './widgets/DateWidget.svelte';
	import CheckboxWidget from './widgets/CheckboxWidget.svelte';
	import SelectWidget from './widgets/SelectWidget.svelte';
	import LinkWidget from './widgets/LinkWidget.svelte';
	import TagsWidget from './widgets/TagsWidget.svelte';

	interface Props {
		field: string;
		value: unknown;
		schema: Record<string, PropertyDef>;
		editable?: boolean;
		widget?: string | null;
		filePath?: string;
		onchange?: (field: string, value: unknown, target?: string) => void;
	}
	let { field, value, schema, editable = false, widget = null, filePath, onchange }: Props =
		$props();

	const def = $derived(schema[field]);
	const resolvedType = $derived(widget || def?.type || 'text');
	const label = $derived(def?.label || field.replaceAll('_', ' '));

	function handleChange(v: unknown, _e: Event) {
		onchange?.(field, v);
	}

	function handleTagsChange(v: string[], e: Event) {
		onchange?.(field, v);
	}
</script>

<div class="prop-field">
	<span class="prop-label">{label}</span>
	<div class="prop-value">
		{#if resolvedType === 'bool' && editable}
			<CheckboxWidget {value} onchange={handleChange} />
		{:else if resolvedType === 'bool'}
			<CheckboxWidget {value} onchange={() => {}} />
		{:else if resolvedType === 'date' && editable}
			<DateWidget {value} onchange={handleChange} />
		{:else if resolvedType === 'select' && editable}
			<SelectWidget {value} options={def?.options ?? []} onchange={handleChange} />
		{:else if resolvedType === 'tags'}
			<TagsWidget {value} {editable} onchange={handleTagsChange} />
		{:else if resolvedType === 'link'}
			<LinkWidget {value} {filePath} />
		{:else if resolvedType === 'path'}
			<span class="path-value">{String(value ?? '')}</span>
		{:else}
			<TextWidget {value} />
		{/if}
	</div>
</div>

<style>
	.prop-field {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--border);
	}
	.prop-label {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		min-width: 100px;
		flex-shrink: 0;
	}
	.prop-value {
		flex: 1;
		min-width: 0;
	}
	.path-value {
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--text-secondary);
		word-break: break-all;
	}
</style>
