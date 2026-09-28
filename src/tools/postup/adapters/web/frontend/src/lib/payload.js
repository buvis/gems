// The single payload seam (PRD 00065). Views NEVER read files or URLs
// themselves — they call loadPayload() and bind to what it returns.
//
// Two modes behind one function:
//   - dev  (import.meta.env.DEV): load the committed fixtures directly, so the
//     app runs with no server. `epics.json` is optional — absent means the
//     deterministic (not-enriched) subset, mirroring the CLI degradation story.
//   - prod: fetch the contracts from the (future) 00067 serve endpoints under
//     /api. 00067 owns those routes; until it exists, prod fetch simply fails
//     soft into the needs-collect state.
//
// The shape returned matches the Python `PortfolioData` contract (data.json)
// plus optional `epics` (epics.json), `prev` (data-prev.json), and `history`
// (parsed history.jsonl lines), so the shared JS/Python derive-parity fixture
// is the same payload on both sides.

/**
 * @typedef {object} Payload
 * @property {import('./derive.js').Repo[]} repos - collected repositories
 * @property {object[]} skipped - repos dropped before collection
 * @property {object} external - portfolio-external PRs
 * @property {number} since_days - the commit window in days
 * @property {string} generated_at - ISO-8601 collection timestamp
 * @property {object|null} epics - parsed epics.json, or null when not enriched
 * @property {object|null} prev - the previous data.json snapshot, or null
 * @property {object[]} history - parsed history.jsonl lines (may be empty)
 */

/**
 * @typedef {object} PayloadState
 * @property {boolean} needsCollect - true when no data.json was reachable
 * @property {boolean} enriched - true when epics.json was present
 * @property {Payload|null} payload - the loaded payload, or null when needsCollect
 * @property {string|null} error - a soft-fail message, or null
 */

const EMPTY = Object.freeze({ needsCollect: true, enriched: false, payload: null, error: null });

/**
 * Parse the newline-delimited history.jsonl body into structured line objects.
 * Never throws: a blank body yields []; a torn/garbage line is skipped rather
 * than failing the whole load (mirrors the collector's `_load_history`
 * tolerance). Only the most recent `cap` lines are kept.
 * @param {string|null} text raw history.jsonl content.
 * @param {number} [cap] max (most recent) lines to keep.
 * @returns {object[]}
 */
export function parseHistory(text, cap = 60) {
	if (typeof text !== 'string' || !text.trim()) return [];
	const out = [];
	for (const line of text.split('\n')) {
		const s = line.trim();
		if (!s) continue;
		try {
			out.push(JSON.parse(s));
		} catch {
			// torn tail or corrupt line — skip it, keep the rest
		}
	}
	return out.length > cap ? out.slice(out.length - cap) : out;
}

/**
 * Normalise a raw data.json + optional epics/prev/history into a PayloadState.
 * @param {object|null} data parsed data.json (Python PortfolioData shape).
 * @param {object|null} epics parsed epics.json, or null.
 * @param {object|null} prev parsed data-prev.json, or null.
 * @param {object[]} [history] parsed history.jsonl lines, or [].
 * @returns {PayloadState}
 */
export function toState(data, epics = null, prev = null, history = []) {
	if (!data || !Array.isArray(data.repos)) {
		return { ...EMPTY };
	}
	return {
		needsCollect: false,
		enriched: epics != null,
		payload: {
			repos: data.repos,
			skipped: data.skipped ?? [],
			external: data.external ?? null,
			since_days: data.since_days ?? 60,
			generated_at: data.generated_at ?? '',
			epics: epics ?? null,
			prev: prev ?? null,
			history: Array.isArray(history) ? history : []
		},
		error: null
	};
}

/**
 * Load the portfolio payload for the current runtime mode.
 *
 * Never throws: an unreachable or malformed source degrades into the
 * needs-collect state so a view can render the "run postup collect first" cue
 * instead of crashing. A missing epics.json degrades to not-enriched.
 *
 * @param {{ dev?: boolean, fetchImpl?: typeof fetch }} [opts] test seams —
 *   `dev` forces the mode, `fetchImpl` injects a fetch for prod-mode tests.
 * @returns {Promise<PayloadState>}
 */
export async function loadPayload(opts = {}) {
	const dev = opts.dev ?? (typeof import.meta !== 'undefined' && import.meta.env?.DEV);
	if (dev) return loadFixtures();
	return loadFromApi(opts.fetchImpl ?? globalThis.fetch);
}

/**
 * Dev mode: load the committed fixtures. Import failures (missing/broken
 * fixture) degrade to needs-collect.
 * @returns {Promise<PayloadState>}
 */
async function loadFixtures() {
	try {
		const data = (await import('../fixtures/data.json')).default;
		let epics = null;
		try {
			epics = (await import('../fixtures/epics.json')).default;
		} catch {
			epics = null; // enrichment absent — deterministic subset
		}
		let prev = null;
		try {
			prev = (await import('../fixtures/data-prev.json')).default;
		} catch {
			prev = null; // first run — no rotated snapshot yet
		}
		let history = [];
		try {
			const raw = (await import('../fixtures/history.jsonl?raw')).default;
			history = parseHistory(raw);
		} catch {
			history = []; // no history yet — sparkline simply won't render
		}
		return toState(data, epics, prev, history);
	} catch {
		return { ...EMPTY };
	}
}

/**
 * Prod mode: fetch the contracts from the 00067 serve endpoints. Any failure
 * (endpoint absent until 00067 ships, network error, bad JSON) degrades to
 * needs-collect; a missing epics endpoint degrades to not-enriched.
 * @param {typeof fetch} fetchImpl the fetch to use.
 * @returns {Promise<PayloadState>}
 */
async function loadFromApi(fetchImpl) {
	if (typeof fetchImpl !== 'function') return { ...EMPTY };
	let data;
	try {
		const res = await fetchImpl('/api/data');
		if (!res.ok) return { ...EMPTY };
		data = await res.json();
	} catch {
		return { ...EMPTY };
	}
	let epics = null;
	try {
		const res = await fetchImpl('/api/epics');
		if (res.ok) epics = await res.json();
	} catch {
		epics = null;
	}
	let prev = null;
	try {
		const res = await fetchImpl('/api/data-prev');
		if (res.ok) prev = await res.json();
	} catch {
		prev = null;
	}
	let history = [];
	try {
		const res = await fetchImpl('/api/history');
		if (res.ok) history = parseHistory(await res.text());
	} catch {
		history = [];
	}
	return toState(data, epics, prev, history);
}
