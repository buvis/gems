import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	server: {
		proxy: {
			'/api': 'http://127.0.0.1:8000'
		}
	},
	test: {
		// The logic layer (derive, payload, done) is framework-free and runs in
		// node. PRD 00066 adds per-view Svelte component tests, which mount real
		// components and so need a DOM — each of those files opts into jsdom with a
		// `// @vitest-environment jsdom` docblock at its top. Everything else stays
		// in the fast node env, preserving the 00065 default.
		environment: 'node',
		include: ['src/**/*.{test,spec}.{js,ts}'],
		coverage: {
			provider: 'v8',
			include: ['src/lib/**/*.js'],
			reporter: ['text', 'text-summary']
		}
	}
});
