const BASE = '/api';

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
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ field, value, target })
	});
	if (!res.ok) throw new Error(`Patch failed: ${res.statusText}`);
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
): Promise<Record<string, unknown>> {
	const res = await fetch(`${BASE}/actions/${encodeURIComponent(name)}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ file_path: filePath, args, row })
	});
	if (!res.ok) throw new Error(`Action failed: ${res.statusText}`);
	return res.json();
}

export async function openFile(filePath: string): Promise<void> {
	const res = await fetch(`${BASE}/open`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ path: filePath })
	});
	if (!res.ok) throw new Error(`Open failed: ${res.statusText}`);
}
