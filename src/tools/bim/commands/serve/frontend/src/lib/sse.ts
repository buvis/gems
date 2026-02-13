type SSECallback = (data: { type: string; files: string[] }) => void;

let source: EventSource | null = null;
let listeners: SSECallback[] = [];

export function connectSSE(): void {
	if (source) return;
	source = new EventSource('/api/events');

	source.onmessage = (event) => {
		try {
			const data = JSON.parse(event.data);
			for (const cb of listeners) cb(data);
		} catch {
			// ignore parse errors
		}
	};

	source.onerror = () => {
		source?.close();
		source = null;
		setTimeout(connectSSE, 3000);
	};
}

export function onFileChange(cb: SSECallback): () => void {
	listeners.push(cb);
	return () => {
		listeners = listeners.filter((l) => l !== cb);
	};
}

export function disconnectSSE(): void {
	source?.close();
	source = null;
	listeners = [];
}
