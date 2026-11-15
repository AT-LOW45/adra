import { type AdrSection, draftService, knowledgeBaseService, ReviewFinding, reviewService, settingsService } from "@/api-service";
import useZodValidation from "@/composables/useZodValidation";
import ROUTES from "@/router/routes";
import { z } from "zod/v4";
import axios from "axios";
import type { ToolbarNames } from "md-editor-v3";
import { useToast } from "primevue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";

export type SectionFormat = "plain" | "rich";

export interface CustomSection {
	heading: string;
	body: string;
	format: SectionFormat;
}

export interface AdrForm {
	/** Absent on drafts saved before the format became configurable. */
	version?: 2;
	id: string;
	/** The "# " heading. Always required, and not a section. */
	title: string;
	/** Section body, keyed by sectionKey(title). Status and Consequences use their own fields. */
	sections: Record<string, string>;
	status: string;
	alternatives: string[];
	/** Source keys of existing records, picked from the knowledge base. */
	relatedAdrs: string[];
	customSections: CustomSection[];
	positiveConsequences: string;
	negativeConsequences: string;
}

/**
 * Section bodies are keyed by the lowercased, trimmed title, matching how the review
 * compares an ADR's headings to the format. Renaming a section therefore orphans its
 * body, which resumeIntoFormat turns into a custom section rather than dropping.
 */
export const sectionKey = (title: string): string => title.trim().toLowerCase();

/**
 * Three titles keep purpose-built widgets when the format includes them; everything
 * else, a team's own sections included, gets a generic markdown editor.
 */
export const STATUS_KEY = "status";
export const DECISION_KEY = "decision";
export const CONSEQUENCES_KEY = "consequences";

/** Validation keys are prefixed so a section titled "Title" can't shadow the heading field. */
export const fieldKey = (key: string): string => `s:${key}`;

/** Fields that were their own property before the format became configurable. */
const LEGACY_SECTION_FIELDS = ["scope", "context", "decision", "implementation", "notes"] as const;

const statusOptions: string[] = ["Proposed", "Accepted", "Deprecated", "Superseded"];

const formatOptions: { label: string; value: SectionFormat }[] = [
	{ label: "Plain text", value: "plain" },
	{ label: "Rich text", value: "rich" },
];

const statusSeverityMap: Record<string, "success" | "info" | "warn" | "secondary"> = {
	Accepted: "success",
	Proposed: "info",
	Deprecated: "warn",
	Superseded: "secondary",
};

// Focused toolbar for the code-capable sections (Decision, Implementation, Notes, rich
// custom sections). The page has its own preview pane, so the editor's is turned off.
const mdToolbars: ToolbarNames[] = [
	"bold",
	"italic",
	"strikeThrough",
	"title",
	"quote",
	"unorderedList",
	"orderedList",
	"-",
	"codeRow",
	"code",
	"link",
	"table",
	"-",
	"revoke",
	"next",
];

function emptyForm(): AdrForm {
	return {
		version: 2,
		id: "",
		title: "",
		sections: {},
		status: "",
		alternatives: [],
		relatedAdrs: [],
		customSections: [],
		positiveConsequences: "",
		negativeConsequences: "",
	};
}

/**
 * Bring a saved draft up to the current format without losing text.
 *
 * Pre-version drafts kept each section in its own property; those move into `sections`.
 * Then any body whose section is no longer in the format — because the draft predates a
 * rename, or the format changed under it — becomes a custom section headed by its old
 * title, so nothing a user typed disappears.
 */
function resumeIntoFormat(raw: AdrForm, format: AdrSection[]): AdrForm {
	const draft = normalizeRelatedAdrs({ ...emptyForm(), ...raw });
	const sections: Record<string, string> = { ...(draft.sections ?? {}) };

	if (raw.version !== 2) {
		for (const field of LEGACY_SECTION_FIELDS) {
			const body = (raw as unknown as Record<string, unknown>)[field];
			if (typeof body === "string" && body.trim()) sections[field] = body;
		}
	}

	const known = new Set(format.map((section) => sectionKey(section.title)));
	const kept: Record<string, string> = {};
	const orphaned: CustomSection[] = [];
	for (const [key, body] of Object.entries(sections)) {
		if (known.has(key)) {
			kept[key] = body;
		} else if (body.trim()) {
			orphaned.push({ heading: key.charAt(0).toUpperCase() + key.slice(1), body, format: "rich" });
		}
	}

	return { ...draft, version: 2, sections: kept, customSections: [...draft.customSections, ...orphaned] };
}

/**
 * Drafts saved before Related ADRs became a picker hold a comma-separated string.
 * Coerce so resuming one doesn't put a string into an array-typed field.
 */
function normalizeRelatedAdrs(draft: AdrForm): AdrForm {
	const related: unknown = draft.relatedAdrs;
	if (Array.isArray(related)) {
		return draft;
	}
	const parsed =
		typeof related === "string"
			? related
					.split(",")
					.map((entry) => entry.trim())
					.filter(Boolean)
			: [];
	return { ...draft, relatedAdrs: parsed };
}

/**
 * All state and behaviour for the Create ADR page. The component is left as pure
 * template + this hook call.
 */
export function useCreateAdr() {
	const router = useRouter();
	const route = useRoute();
	const toast = useToast();

	const form = ref<AdrForm>(emptyForm());
	const alternativeInput = ref<string>("");
	const submitting = ref<boolean>(false);
	const savingDraft = ref<boolean>(false);
	// The draft this session maps to. Null until the first save; set when resuming an existing draft.
	const draftId = ref<string | null>(null);

	// Baseline snapshot of the form (JSON) representing the last persisted/loaded state.
	// The form is "dirty" (has unsaved progress) when it no longer matches this.
	const savedSnapshot = ref<string>("");
	const markPristine = (): void => {
		savedSnapshot.value = JSON.stringify(form.value);
	};
	const isDirty = computed<boolean>(() => JSON.stringify(form.value) !== savedSnapshot.value);

	// Unsaved-changes dialog state (shown when navigating away while dirty).
	const showLeaveDialog = ref<boolean>(false);
	const pendingRoute = ref<string | null>(null);
	const bypassLeaveGuard = ref<boolean>(false); // set for our own post-publish navigation

	// review ADR quality
	const checking = ref(false);
	const reviewFindings = ref<ReviewFinding[]>([]);
	const showReviewDialog = ref(false);
	const hasReviewError = ref(false);
	// The semantic (LLM) pass errored server-side (distinct from the whole call failing).
	const reviewDegraded = ref(false);

	// The format the form is built from. Loaded once on mount: changing it in another tab
	// doesn't reshape an open form, which would move fields out from under the user.
	const format = ref<AdrSection[]>([]);
	const formatLoading = ref(true);
	const formatError = ref("");

	const sectionsInOrder = computed(() => format.value);

	/** Whether a section counts as filled, which differs for the widget-backed ones. */
	const sectionFilled = (key: string): boolean => {
		const f = form.value;
		if (key === STATUS_KEY) return !!f.status;
		if (key === CONSEQUENCES_KEY) return !!(f.positiveConsequences.trim() || f.negativeConsequences.trim());
		return !!(f.sections[key] ?? "").trim();
	};

	// Built from the format rather than a fixed schema, so a team's own required section
	// blocks submission the same way Status always has.
	const schema = computed(() => {
		const shape: Record<string, z.ZodType> = {
			title: z.string().trim().min(1, { message: "Title is required." }),
		};
		for (const section of format.value) {
			const key = sectionKey(section.title);
			shape[fieldKey(key)] = section.required
				? z.literal(true, { message: `${section.title} is required.` })
				: z.boolean();
		}
		return z.object(shape);
	});

	// Validation runs over filled/not-filled flags rather than the raw bodies, because
	// "filled" means something different for Status, Consequences and a plain editor.
	const validationTarget = computed(() => {
		const target: Record<string, unknown> = { title: form.value.title };
		for (const section of format.value) {
			const key = sectionKey(section.title);
			target[fieldKey(key)] = sectionFilled(key);
		}
		return target;
	});

	const { validate, simpleValidate, validationErrors, updateSchema } = useZodValidation(schema.value, {
		errorToast: { summary: "Missing required fields", detail: "Please complete the highlighted fields." },
	});

	// useZodValidation reads its schema once at setup, and the format arrives after that.
	// Without this the form would validate against an empty schema and accept anything.
	watch(schema, (next) => updateSchema(next));

	const statusSeverity = computed(() => statusSeverityMap[form.value.status] ?? "secondary");

	const addAlternative = (): void => {
		const val = alternativeInput.value.trim();
		if (val && !form.value.alternatives.includes(val)) {
			form.value.alternatives.push(val);
		}
		alternativeInput.value = "";
	};

	const addCustomSection = (): void => {
		form.value.customSections.push({ heading: "", body: "", format: "plain" });
	};

	const removeCustomSection = (index: number): void => {
		form.value.customSections.splice(index, 1);
	};

	// Assemble the form into an ADR markdown document, mirroring the docs/adr/ format.
	// Core sections always render (with a muted placeholder when empty) so the document
	// structure is visible; optional sections appear only once filled in.
	// Assembled in format order: required sections always render (with a muted placeholder
	// when empty) so the document's shape is visible, optional ones only once filled.
	// Custom sections come last, after every format section.
	const markdown = computed<string>(() => {
		const f = form.value;
		const lines: string[] = [];

		const title = f.title || "Untitled ADR";
		lines.push(f.id ? `# ${f.id}: ${title}` : `# ${title}`, "");

		for (const section of format.value) {
			const key = sectionKey(section.title);
			const filled = sectionFilled(key);
			if (!filled && !section.required) continue;

			lines.push(`## ${section.title}`);

			if (key === STATUS_KEY) {
				lines.push(f.status || "_Not set_", "");
				continue;
			}
			if (key === CONSEQUENCES_KEY) {
				if (!filled) {
					lines.push("_Not set_", "");
					continue;
				}
				if (f.positiveConsequences.trim()) lines.push("", "### Positive", f.positiveConsequences.trim());
				if (f.negativeConsequences.trim()) lines.push("", "### Trade-offs", f.negativeConsequences.trim());
				lines.push("");
				continue;
			}

			const body = (f.sections[key] ?? "").trim();
			if (key === DECISION_KEY) {
				lines.push(body || "_State the decision clearly._");
				if (f.alternatives.length) {
					lines.push("", "### Alternatives Considered", ...f.alternatives.map((a) => `- ${a}`));
				}
				if (f.relatedAdrs.length) {
					lines.push("", "### Related ADRs", ...f.relatedAdrs.map((source) => `- ${source}`));
				}
				lines.push("");
				continue;
			}

			lines.push(body || "_Not set_", "");
		}

		for (const section of f.customSections) {
			if (!section.heading.trim() && !section.body.trim()) continue;
			lines.push(`## ${section.heading.trim() || "Untitled Section"}`, section.body.trim(), "");
		}

		return lines.join("\n").trimEnd();
	});

	// Track the app's dark mode (PrimeVue toggles a `.app-dark` class) so editors/preview match.
	const hasDarkClass = (): boolean =>
		document.documentElement.classList.contains("app-dark") || document.body.classList.contains("app-dark");

	const isDark = ref<boolean>(hasDarkClass());
	const observer = new MutationObserver(() => {
		isDark.value = hasDarkClass();
	});
	observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
	observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
	onBeforeUnmount(() => observer.disconnect());

	const assignNewId = async (): Promise<void> => {
		try {
			const { data } = await knowledgeBaseService.getNextId();
			form.value.id = data.id;
		} catch (error) {
			console.error("Failed to fetch next ADR id:", error);
			toast.add({ severity: "error", summary: "Couldn't assign an ADR id", detail: "Reload to try again.", life: 4000 });
		}
	};

	// Existing records, for the Related ADRs picker.
	const relatedAdrOptions = ref<string[]>([]);
	const loadingRelatedAdrs = ref<boolean>(false);

	const loadRelatedAdrOptions = async (): Promise<void> => {
		loadingRelatedAdrs.value = true;
		try {
			const { data } = await knowledgeBaseService.getAllRecords();
			relatedAdrOptions.value = data.records.map((record) => record.adr_id).filter(Boolean);
		} catch (error) {
			console.error("Failed to load existing ADRs:", error);
			toast.add({
				severity: "warn",
				summary: "Couldn't load existing ADRs",
				detail: "Related ADRs can't be picked right now.",
				life: 4000,
			});
		} finally {
			loadingRelatedAdrs.value = false;
		}
	};

	// A resumed draft can reference a record that has since been deleted or renamed. Merge
	// those in so the selection stays visible instead of silently vanishing from the chips.
	const relatedAdrChoices = computed<string[]>(() =>
		[...new Set([...relatedAdrOptions.value, ...form.value.relatedAdrs])].sort(),
	);

	// Resume an existing draft when ?draft=<id> is present; otherwise start fresh with
	// a backend-assigned next id. Snapshot the result as the pristine baseline.
	// The format decides which fields exist, so the page can't render without it. A
	// failure shows a retry rather than falling back to built-in defaults: creating an
	// ADR needs the backend anyway, and a silent fallback would produce the wrong shape.
	const loadFormat = async (): Promise<void> => {
		formatLoading.value = true;
		formatError.value = "";
		try {
			const { data } = await settingsService.getAdrFormat();
			format.value = data.sections;
			// Seed every section's key so v-model has somewhere to write. Without this the
			// first keystroke in a never-touched section writes to an undefined property.
			for (const section of data.sections) {
				const key = sectionKey(section.title);
				if (form.value.sections[key] === undefined) form.value.sections[key] = "";
			}
		} catch (error) {
			formatError.value = axios.isAxiosError(error)
				? (error.response?.data?.detail ?? error.message)
				: "Couldn't load the ADR format.";
			throw error;
		} finally {
			formatLoading.value = false;
		}
	};

	const start = async (): Promise<void> => {
		// Independent of the form — let it load alongside rather than gating the page on it.
		void loadRelatedAdrOptions();

		try {
			await loadFormat();
		} catch {
			return; // the page shows the retry; nothing below can run without a format
		}

		const resumeId = typeof route.query.draft === "string" ? route.query.draft : null;
		if (resumeId) {
			try {
				const { data } = await draftService.getDraft(resumeId);
				form.value = resumeIntoFormat(data.draft, format.value);
				for (const section of format.value) {
					const key = sectionKey(section.title);
					if (form.value.sections[key] === undefined) form.value.sections[key] = "";
				}
				draftId.value = resumeId;
				if (!form.value.id) await assignNewId();
			} catch (error) {
				console.error("Failed to load draft:", error);
				toast.add({ severity: "error", summary: "Couldn't load draft", detail: "Starting a new ADR instead.", life: 4000 });
				await assignNewId();
			}
		} else {
			await assignNewId();
		}
		markPristine();
	};

	const retryFormat = (): void => void start();

	onMounted(start);

	// Warn on browser-level navigation (tab close / refresh) while there are unsaved changes.
	const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
		if (isDirty.value) {
			event.preventDefault();
			event.returnValue = "";
		}
	};
	window.addEventListener("beforeunload", handleBeforeUnload);
	onBeforeUnmount(() => window.removeEventListener("beforeunload", handleBeforeUnload));

	// Intercept in-app navigation while dirty and show the unsaved-changes dialog instead.
	onBeforeRouteLeave((to) => {
		if (bypassLeaveGuard.value || !isDirty.value) {
			return true;
		}
		pendingRoute.value = to.fullPath;
		showLeaveDialog.value = true;
		return false;
	});

	const cancelLeave = (): void => {
		showLeaveDialog.value = false;
		pendingRoute.value = null;
	};

	const discardAndLeave = (): void => {
		showLeaveDialog.value = false;
		const target = pendingRoute.value;
		pendingRoute.value = null;
		bypassLeaveGuard.value = true; // allow the blocked navigation to proceed unsaved
		if (target) {
			router.push(target);
		}
	};

	const saveDraftAndLeave = async (): Promise<void> => {
		const ok = await saveDraft();
		if (!ok) {
			return; // save failed — keep the dialog open so they can retry or cancel
		}
		showLeaveDialog.value = false;
		const target = pendingRoute.value;
		pendingRoute.value = null;
		if (target) {
			router.push(target); // form is pristine now, so the guard allows it
		}
	};

	// After the first failed submit, re-validate live so errors clear as fields are fixed.
	watch(form, () => simpleValidate(validationTarget.value), { deep: true });

	const saveDraft = async (): Promise<boolean> => {
		// New drafts get a stable id on first save (independent of the ADR id);
		// saving again overwrites the same draft.
		if (!draftId.value) {
			draftId.value = crypto.randomUUID();
		}
		savingDraft.value = true;
		try {
			await draftService.saveDraft(draftId.value, form.value);
			markPristine();
			toast.add({ severity: "success", summary: "Draft saved", life: 2000 });
			return true;
		} catch (error) {
			console.error("Failed to save draft:", error);
			toast.add({ severity: "error", summary: "Failed to save draft", life: 3000 });
			return false;
		} finally {
			savingDraft.value = false;
		}
	};

	const checkQuality = async () => {
		reviewFindings.value = [];
		hasReviewError.value = false;
		reviewDegraded.value = false;
		checking.value = true;
		try {
			const result = await reviewService.reviewDocument(markdown.value);
			reviewFindings.value = result.data.findings;
			reviewDegraded.value = result.data.llm_ok === false;
			showReviewDialog.value = true;
		} catch (error) {
			console.error(error);
			hasReviewError.value = true;
			showReviewDialog.value = true;
			reviewFindings.value = [];
		} finally {
			checking.value = false;
		}
	};

	const submitAdr = async (): Promise<void> => {
		if (!validate(validationTarget.value)) return;

		submitting.value = true;
		try {
			await checkQuality();
			if (hasReviewError.value || reviewFindings.value.length > 0 || reviewDegraded.value) {
				return;
			}

			const { data } = await knowledgeBaseService.createDocument(markdown.value);

			// Publishing consumes the draft — remove it so it no longer shows in the list.
			// Best-effort: the ADR is already created, so a cleanup failure shouldn't fail the publish.
			if (draftId.value) {
				try {
					await draftService.deleteDraft(draftId.value);
				} catch (error) {
					console.error("Failed to remove draft after publish:", error);
				}
				draftId.value = null;
			}

			toast.add({ severity: "success", summary: "ADR created", detail: data.source, life: 3000 });
			bypassLeaveGuard.value = true; // our own navigation — skip the unsaved-changes guard
			router.push(ROUTES.knowledgeBase);
		} catch (error: any) {
			const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
			toast.add({ severity: "error", summary: "Failed to create ADR", life: 3000, detail: detail });
		} finally {
			submitting.value = false;
		}
	};

	const submitAnyway = async () => {
		submitting.value = true;
		try {
			const { data } = await knowledgeBaseService.createDocument(markdown.value);

			// Publishing consumes the draft — remove it so it no longer shows in the list.
			// Best-effort: the ADR is already created, so a cleanup failure shouldn't fail the publish.
			if (draftId.value) {
				try {
					await draftService.deleteDraft(draftId.value);
				} catch (error) {
					console.error("Failed to remove draft after publish:", error);
				}
				draftId.value = null;
			}

			toast.add({ severity: "success", summary: "ADR created", detail: data.source, life: 3000 });
			bypassLeaveGuard.value = true; // our own navigation — skip the unsaved-changes guard
			router.push(ROUTES.knowledgeBase);
		} catch (error: any) {
			const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
			toast.add({ severity: "error", summary: "Failed to create ADR", life: 3000, detail: detail });
		} finally {
			submitting.value = false;
		}
	};

	return {
		// state
		form,
		format: sectionsInOrder,
		formatLoading,
		formatError,
		retryFormat,
		sectionKey,
		fieldKey,
		STATUS_KEY,
		DECISION_KEY,
		CONSEQUENCES_KEY,
		alternativeInput,
		submitting,
		savingDraft,
		validationErrors,
		// unsaved-changes dialog
		showLeaveDialog,
		cancelLeave,
		discardAndLeave,
		saveDraftAndLeave,
		// derived
		statusSeverity,
		markdown,
		isDark,
		// static UI config
		statusOptions,
		formatOptions,
		mdToolbars,
		relatedAdrChoices,
		loadingRelatedAdrs,
		// actions
		addAlternative,
		addCustomSection,
		removeCustomSection,
		saveDraft,
		submitAdr,

		// adr quality review
		checking,
		reviewFindings,
		showReviewDialog,
		hasReviewError,
		reviewDegraded,
		checkQuality,
		submitAnyway,
	};
}
