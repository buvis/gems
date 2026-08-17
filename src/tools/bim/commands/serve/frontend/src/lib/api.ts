const BASE = '/api';
const TOKEN = (window as unknown as { __BUVIS_TOKEN__?: string }).__BUVIS_TOKEN__ ?? '';

export interface ResultEnvelope {
	success: boolean;
	output: string | null;
	error: string | null;
	info: string[];
	warnings: string[];
	metadata: Record<string, unknown>;
}

async function unwrapEnvelope(res: Response, label: string): Promise<ResultEnvelope> {
	let body: unknown;
	try {
		body = await res.json();
	} catch {
		throw new Error(`${label} failed: ${res.status} ${res.statusText}`);
	}
	if (body && typeof body === 'object' && 'success' in body) {
		const envelope = body as ResultEnvelope;
		if (!envelope.success) throw new Error(envelope.error ?? `${label} failed: ${res.statusText}`);
		return envelope;
	}
	if (body && typeof body === 'object' && 'detail' in body) {
		const detail = (body as { detail: unknown }).detail;
		throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
	}
	throw new Error(`${label} failed: ${res.status} ${res.statusText}`);
}

export async function fetchQueries(): Promise<Record<string, string>> {
	const res = await fetch(`${BASE}/queries`);
	const data = await res.json();
	return data.queries;
}

export async function fetchQuerySpec(name: string): Promise<Record<string, unknown>> {
	const res = await fetch(`${BASE}/queries/${encodeURIComponent(name)}`);
	if (!res.ok) throw new Error(`Query not found: ${name}`);
	return res.json();
}

export interface PropertyDef {
	type: string;
	label: string | null;
	options: string[];
}

export interface ItemField {
	field: string;
	editable: boolean;
	widget: string | null;
}

export interface ItemSection {
	heading: string;
	fields: ItemField[] | null;
	section: string | null;
	editable: boolean;
	display: string;
}

export interface ItemViewSpec {
	title: string;
	subtitle: string | null;
	sections: ItemSection[];
}

export interface ActionSpec {
	name: string;
	label: string;
	scope: string;
	handler: string;
	args: Record<string, unknown>;
	confirm: string | null;
}

export interface OutputSpec {
	format: string;
	group_by: string | null;
	limit: number | null;
	sample: number | null;
	file: string | null;
}

export interface ExecResult {
	rows: Record<string, unknown>[];
	columns: Column[];
	dashboard: { title?: string; auto_refresh?: boolean } | null;
	count: number;
	schema: Record<string, PropertyDef>;
	item: ItemViewSpec | null;
	actions: ActionSpec[];
	output: OutputSpec | null;
}

export interface Column {
	field: string | null;
	expr: string | null;
	label: string | null;
	format: string | null;
	widget: string | null;
	editable: boolean;
	options: string[];
}

export interface ZettelData {
	metadata: Record<string, unknown>;
	reference: Record<string, unknown>;
	sections: { heading: string; body: string }[];
	file_path: string;
}

export async function execQuery(name: string): Promise<ExecResult> {
	const res = await fetch(`${BASE}/queries/${encodeURIComponent(name)}/exec`, {
		method: 'POST'
	});
	if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);
	return res.json();
}

export async function execAdhoc(spec: Record<string, unknown>): Promise<ExecResult> {
	const res = await fetch(`${BASE}/queries/_adhoc`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ spec })
	});
	if (!res.ok) throw new Error(`Adhoc query failed: ${res.statusText}`);
	return res.json();
}

export async function patchZettel(
	filePath: string,
	field: string,
	value: unknown,
	target: string = 'metadata'
): Promise<void> {
	const res = await fetch(`${BASE}/zettels/${encodeURIComponent(filePath)}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json', 'X-Buvis-Token': TOKEN },
		body: JSON.stringify({ field, value, target })
	});
	await unwrapEnvelope(res, 'Patch');
}

export async function fetchZettel(filePath: string): Promise<ZettelData> {
	const res = await fetch(`${BASE}/zettels/${encodeURIComponent(filePath)}`);
	if (!res.ok) throw new Error(`Fetch zettel failed: ${res.statusText}`);
	return res.json();
}

export async function execAction(
	name: string,
	filePath: string,
	args: Record<string, unknown>,
	row: Record<string, unknown>
): Promise<ResultEnvelope> {
	const res = await fetch(`${BASE}/actions/${encodeURIComponent(name)}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-Buvis-Token': TOKEN },
		body: JSON.stringify({ file_path: filePath, args, row })
	});
	return unwrapEnvelope(res, 'Action');
}

export async function openFile(filePath: string): Promise<void> {
	const res = await fetch(`${BASE}/open`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-Buvis-Token': TOKEN },
		body: JSON.stringify({ path: filePath })
	});
	await unwrapEnvelope(res, 'Open');
}
