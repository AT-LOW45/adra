import type { AdrForm } from "@/composables/useCreateAdr";
import axios, { CreateAxiosDefaults } from "axios";

const axiosConfig: CreateAxiosDefaults = {
	baseURL: import.meta.env.VITE_API_ENDPOINT,
};

const api = axios.create(axiosConfig);

// A published record. `source` is the identity key (title slug); `adr_id`/`title`
// come from metadata — the ADR number is no longer part of the key.
export type AdrRecord = { source: string; adr_id: string; title: string };

// One candidate ADR from a retrieval preview. `score` is the best-matching chunk's
// relevance; `dropped_reason` says why a candidate the agent won't see was excluded.
export type SearchCandidate = {
	source: string;
	adr_id: string;
	title: string;
	score: number;
	kept: boolean;
	dropped_reason: "below_threshold" | "over_max_sources" | null;
};

// `retrieval_threshold` is the value the preview was evaluated at — the scores only
// mean anything read against it. `max_sources` is the server's cap on how many ADRs a
// search returns, sent so callers don't keep their own copy of it.
export type SearchPreview = {
	query: string;
	retrieval_threshold: number;
	max_sources: number;
	candidates: SearchCandidate[];
};

// `retrieval_threshold_source` distinguishes a value the team saved from the built-in
// default, so the UI can offer "reset" only when there is something to reset.
export type Settings = {
	retrieval_threshold: number;
	retrieval_threshold_source: "saved" | "default";
	default_retrieval_threshold: number;
};

export const knowledgeBaseService = {
	getAllRecords: () => api.get<{ records: AdrRecord[] }>("/knowledge-base"),
	getRecord: (source: string) => api.get(`knowledge-base/${source}`),
	getRawRecord: (source: string) => api.get(`/knowledge-base/${encodeURIComponent(source)}/raw`),
	deleteRecord: (source: string) => api.delete(`/knowledge-base/${source}`),

	// Create a record from an uploaded file. No `source` is sent — the backend derives it
	// (H1 if the document has one, else the filename plus a fresh ADR id) and 409s rather
	// than overwriting an existing record. Returns the key it settled on.
	indexDocument: (file: File) => {
		const form = new FormData();
		form.append("file", file);
		return api.post<{ source: string }>("/knowledge-base/index-document", form, {
			headers: { "Content-Type": "multipart/form-data" },
		});
	},

	// Next sequential ADR id to pre-fill the create form (e.g. "ADR-004").
	getNextId: () => api.get<{ id: string }>("/knowledge-base/next-id"),

	// Create a new record from markdown. The backend derives the source key from
	// the document's H1 title and returns it, then writes to blob + indexes.
	createDocument: (content: string) => api.post<{ source: string }>("/knowledge-base", { content }),

	// Which ADRs a coding task would retrieve, with every candidate's score and why it
	// was kept or dropped. Goes through the same ranking agents get. Passing a threshold
	// evaluates at that value without saving it, so one can be tried before committing.
	searchPreview: (query: string, retrievalThreshold?: number | null) =>
		api.post<SearchPreview>("/knowledge-base/search-preview", {
			query,
			retrieval_threshold: retrievalThreshold ?? null,
		}),

	// Save an edit to a known record. The backend treats the document's H1 as
	// authoritative, so changing the title renames the record — the returned `source` is
	// the key it now lives under and may differ from the one passed in.
	saveMarkdown: (source: string, content: string) => {
		const blob = new Blob([content], { type: "text/markdown" });
		const file = new File([blob], source, { type: "text/markdown" });
		const form = new FormData();
		form.append("file", file);
		return api.post<{ source: string }>(`/knowledge-base/index-document?source=${encodeURIComponent(source)}`, form, {
			headers: { "Content-Type": "multipart/form-data" },
		});
	},
} as const;

// Drafts — in-progress ADRs stored as the form object (JSON), never indexed.
// Kept separate from knowledgeBaseService, mirroring the backend's dedicated draft service.
export const draftService = {
	listDrafts: () => api.get<{ drafts: { id: string; draft: AdrForm }[] }>("/knowledge-base/drafts"),
	getDraft: (id: string) => api.get<{ id: string; draft: AdrForm }>(`/knowledge-base/drafts/${encodeURIComponent(id)}`),
	saveDraft: (id: string, draft: AdrForm) => api.put(`/knowledge-base/drafts/${encodeURIComponent(id)}`, draft),
	deleteDraft: (id: string) => api.delete(`/knowledge-base/drafts/${encodeURIComponent(id)}`),
} as const;

export type ReviewFinding = { severity: "warning" | "error"; section: string; message: string };

export const reviewService = {
	reviewDocument: (content: string) =>
		api.post<{ findings: ReviewFinding[]; llm_ok: boolean }>("/knowledge-base/adr-review", { content }),
};

// Team-level settings, stored in the blob bucket alongside the ADRs.
export const settingsService = {
	getSettings: () => api.get<Settings>("/settings"),

	// null clears the saved value, falling back to the server's default. Applies
	// immediately — agents get the new threshold on their next search, no restart.
	saveRetrievalThreshold: (retrievalThreshold: number | null) =>
		api.put<Settings>("/settings", { retrieval_threshold: retrievalThreshold }),
} as const;
