// Shared harness for PRD 00066 per-view component tests.
//
// The routes read their data from the `portfolio` context that `+layout.svelte`
// sets. A page mounted in isolation has no layout, so this helper builds the
// same context shape ({ get state() }) and hands it to Svelte's `mount` via the
// @testing-library/svelte `context` option — so each view test drives a real
// component against a real payload state, exactly as the layout would feed it.
import { render } from '@testing-library/svelte';
import { toState } from '$lib/payload.js';

/**
 * Build the `portfolio` context Map a route expects.
 * @param {import('$lib/payload.js').PayloadState} state
 * @returns {Map<string, { readonly state: any }>}
 */
export function portfolioContext(state) {
	return new Map([['portfolio', { get state() { return state; } }]]);
}

/**
 * Render a route `+page.svelte` with a portfolio context built from raw
 * data/epics/prev/history — the same normalisation the layout runs.
 * @param {any} Component the route page component.
 * @param {{ data?: any, epics?: any, prev?: any, history?: any[] }} payload
 */
export function renderView(Component, { data = null, epics = null, prev = null, history = [] } = {}) {
	const state = toState(data, epics, prev, history);
	return render(Component, { context: portfolioContext(state) });
}

/**
 * Reset the (jsdom-provided) localStorage between tests so done-state does not
 * leak across cases. Call in beforeEach.
 */
export function installMemoryStorage() {
	try {
		globalThis.localStorage?.clear();
	} catch {
		// no storage in this env — done.js degrades gracefully anyway
	}
}
