<script lang="ts">
	import type { ActionSpec } from '$lib/api';
	import { execAction } from '$lib/api';
	import ConfirmDialog from './ConfirmDialog.svelte';

	interface Props {
		actions: ActionSpec[];
		scope: string;
		filePath?: string;
		row?: Record<string, unknown>;
		onactiondone?: () => void;
	}
	let { actions, scope, filePath = '', row = {}, onactiondone }: Props = $props();

	let pendingAction = $state<ActionSpec | null>(null);
	let feedback = $state<{ ok: boolean; msg: string } | null>(null);

	const filtered = $derived(
		actions.filter((a) => a.scope === scope || a.scope === 'both')
	);

	function resolveTemplate(tpl: string, data: Record<string, unknown>): string {
		return tpl.replace(/\{(\w+)\}/g, (_, key) => String(data[key] ?? ''));
	}

	async function runAction(action: ActionSpec) {
		if (action.confirm) {
			pendingAction = action;
			return;
		}
		await doExec(action);
	}

	async function doExec(action: ActionSpec) {
		pendingAction = null;
		try {
			await execAction(action.handler, filePath, action.args, row);
			feedback = { ok: true, msg: `${action.label}: done` };
			onactiondone?.();
		} catch (e) {
			feedback = { ok: false, msg: `${action.label}: ${e}` };
		}
		setTimeout(() => (feedback = null), 3000);
	}
</script>

{#if filtered.length > 0}
	<div class="action-bar">
		{#each filtered as action}
			<button class="action-btn" onclick={() => runAction(action)}>
				{action.label}
			</button>
		{/each}
		{#if feedback}
			<span class="feedback" class:ok={feedback.ok} class:err={!feedback.ok}>
				{feedback.msg}
			</span>
		{/if}
	</div>
{/if}

{#if pendingAction}
	<ConfirmDialog
		message={resolveTemplate(pendingAction.confirm ?? '', row)}
		onconfirm={() => doExec(pendingAction!)}
		oncancel={() => (pendingAction = null)}
	/>
{/if}

<style>
	.action-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0;
	}
	.action-btn {
		padding: 0.35rem 0.8rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-size: 0.8rem;
		font-family: var(--font-mono);
		cursor: pointer;
		transition: all var(--transition);
	}
	.action-btn:hover {
		background: var(--accent-dim);
		border-color: var(--accent);
	}
	.feedback {
		font-size: 0.75rem;
		font-family: var(--font-mono);
		padding: 0.2rem 0.5rem;
		border-radius: var(--radius);
	}
	.feedback.ok {
		color: var(--success);
	}
	.feedback.err {
		color: var(--danger);
	}
</style>
