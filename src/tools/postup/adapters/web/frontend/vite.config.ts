import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': 'http://127.0.0.1:8000'
		}
	},
	test: {
		// The logic layer (derive, payload, done) is framework-free and runs in
		// node; svelte component tests would need a DOM env added per-file.
		environment: 'node',
		include: ['src/**/*.{test,spec}.{js,ts}'],
		coverage: {
			provider: 'v8',
			include: ['src/lib/**/*.js'],
			reporter: ['text', 'text-summary']
		}
	}
});
