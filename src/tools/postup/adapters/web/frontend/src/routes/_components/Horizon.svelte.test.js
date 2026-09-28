// @vitest-environment jsdom
// Horizon strip component test (PRD 00066 Phase 2 — attention presentation).
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Horizon from './Horizon.svelte';

const day = (d) => new Date(Date.now() - d * 86400000).toISOString().slice(0, 10);

describe('Horizon strip', () => {
	it('ranks burning repos highest-first with score, name and top reason', () => {
		const repos = [
			{ owner: 'a', name: 'calm', brush_last_run: day(1) },
			{ owner: 'b', name: 'fire', brush_last_run: day(1), ci: [{ workflow: 'test', conclusion: 'failure', date: null }] }
		];
		const { container } = render(Horizon, { props: { repos } });
		const rows = [...container.querySelectorAll('.hrow')];
		expect(rows).toHaveLength(1); // calm repo drops out
		expect(rows[0].textContent).toMatch(/b\/fire/);
		expect(rows[0].textContent).toMatch(/failing workflow/);
	});

	it('shows a calm empty-state when nothing needs attention', () => {
		const { getByText } = render(Horizon, {
			props: { repos: [{ owner: 'a', name: 'calm', brush_last_run: day(1) }] }
		});
		expect(getByText(/Nothing on the horizon\. All quiet\./)).toBeTruthy();
	});
});
