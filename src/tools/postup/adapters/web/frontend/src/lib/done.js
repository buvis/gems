// Shared checked-state for todos, keyed by stable todo id.
//
// Ported from the brief-portfolio SPA's `lib/done.js`. Per PRD 00065 the
// localStorage key moves from the skill's `brief-portfolio-done` to a
// postup-namespaced key so the two never collide in a browser that has run
// both. Behaviour is otherwise a parity port: one shared bucket, pruned to the
// current payload's ids so the set cannot grow forever.
const KEY = 'postup-portfolio-done';

let storageBlocked = false;

export const isStorageBlocked = () => storageBlocked;

/**
 * Read the persisted done-set from localStorage.
 * @returns {Set<string>} the set of done todo ids (empty when unset/blocked).
 */
export const loadDone = () => {
	try {
		return new Set(JSON.parse(localStorage.getItem(KEY) ?? '[]'));
	} catch {
		storageBlocked = true;
		return new Set();
	}
};

/**
 * Persist the done-set to localStorage.
 * @param {Set<string>} s the set of done todo ids.
 */
export const saveDone = (s) => {
	try {
		localStorage.setItem(KEY, JSON.stringify([...s]));
	} catch {
		storageBlocked = true;
	}
};

/**
 * Drop ids that no longer exist in the payload so the set can't grow forever.
 * @param {Set<string>} validIds ids present in the current payload.
 * @returns {Set<string>} the pruned done-set (also persisted when it changed).
 */
export function pruneDone(validIds) {
	const done = loadDone();
	const kept = new Set([...done].filter((id) => validIds.has(id)));
	if (kept.size !== done.size) saveDone(kept);
	return kept;
}
