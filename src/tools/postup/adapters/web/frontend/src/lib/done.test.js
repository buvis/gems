// Done-state store tests (PRD 00065 Phase 2).
// Covers: persistence across "reloads" (fresh load from the same storage),
// pruning ids absent from the payload, and graceful degradation when storage
// throws. Uses an in-memory localStorage mock installed on globalThis.
import { describe, it, expect, beforeEach, vi } from 'vitest';

function installStorage(impl) {
	globalThis.localStorage = impl;
}

function memoryStorage() {
	let store = {};
	return {
		getItem: (k) => (k in store ? store[k] : null),
		setItem: (k, v) => {
			store[k] = String(v);
		},
		removeItem: (k) => {
			delete store[k];
		},
		_dump: () => store
	};
}

describe('done-state store', () => {
	let mod;

	beforeEach(async () => {
		vi.resetModules();
		installStorage(memoryStorage());
		mod = await import('./done.js');
	});

	it('persists checked ids across a reload', () => {
		const { loadDone, saveDone } = mod;
		const set = new Set(['a/b:ci:test', 'c/d:local:dirty']);
		saveDone(set);
		expect([...loadDone()].sort()).toEqual(['a/b:ci:test', 'c/d:local:dirty']);
	});

	it('uses a postup-namespaced key, not the skill key', () => {
		const { saveDone } = mod;
		saveDone(new Set(['x']));
		const dump = globalThis.localStorage._dump();
		expect(Object.keys(dump)).toContain('postup-portfolio-done');
		expect(Object.keys(dump)).not.toContain('brief-portfolio-done');
	});

	it('prunes ids absent from the current payload', () => {
		const { saveDone, pruneDone, loadDone } = mod;
		saveDone(new Set(['keep', 'drop-me']));
		const kept = pruneDone(new Set(['keep', 'other']));
		expect([...kept]).toEqual(['keep']);
		expect([...loadDone()]).toEqual(['keep']); // persisted
	});

	it('leaves storage untouched when nothing needs pruning', () => {
		const { saveDone, pruneDone } = mod;
		saveDone(new Set(['keep']));
		const setSpy = vi.spyOn(globalThis.localStorage, 'setItem');
		pruneDone(new Set(['keep', 'more']));
		expect(setSpy).not.toHaveBeenCalled();
	});

	it('degrades to an empty set and flags blocked when storage throws', async () => {
		installStorage({
			getItem: () => {
				throw new Error('blocked');
			},
			setItem: () => {
				throw new Error('blocked');
			}
		});
		vi.resetModules();
		const blocked = await import('./done.js');
		expect([...blocked.loadDone()]).toEqual([]);
		expect(blocked.isStorageBlocked()).toBe(true);
	});
});
