// @vitest-environment jsdom
// Sparkline component test (PRD 00066 Phase 2 — trend presentation).
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Sparkline from './Sparkline.svelte';

describe('Sparkline', () => {
	it('renders a single value as a dot, never an empty/erroring line', () => {
		const { container } = render(Sparkline, { props: { values: [4] } });
		expect(container.querySelector('circle.dot')).toBeTruthy();
		expect(container.querySelector('polyline')).toBeNull();
	});

	it('renders two or more values as a polyline', () => {
		const { container } = render(Sparkline, { props: { values: [1, 3, 2, 5] } });
		const line = container.querySelector('polyline');
		expect(line).toBeTruthy();
		expect(line.getAttribute('points').split(' ')).toHaveLength(4);
	});

	it('renders neither for an empty series', () => {
		const { container } = render(Sparkline, { props: { values: [] } });
		expect(container.querySelector('circle.dot')).toBeNull();
		expect(container.querySelector('polyline')).toBeNull();
	});
});
