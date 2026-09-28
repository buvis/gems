// The repo drill-down is a client-side SPA route: its data comes from the
// payload loaded in the layout at runtime, and its param is any repo slug in
// that payload, so there is nothing to prerender at build time. adapter-static
// serves it via the index.html fallback (svelte.config.js), exactly like the
// SPA it replaced.
export const prerender = false;
