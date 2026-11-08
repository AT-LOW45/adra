<template>
	<!-- One sticky header: record nav on top, title + actions below. A single solid card
	     (no seam) so scrolling content never shows through between two stacked bars. -->
	<div class="w-full mx-auto 2xl:max-w-[90%] sticky top-0 z-50 rounded-xl bg-white dark:bg-surface-900 shadow-md">
		<div class="flex items-center p-2">
			<Button
				label="Prev"
				icon="pi pi-arrow-left"
				icon-pos="left"
				severity="secondary"
				size="small"
				@click="goToPrevious"
				:disabled="currentIndex === 0"
			/>
			<Select
				v-model="currentRecord"
				class="ml-auto"
				size="small"
				:options="recordOptions"
				option-label="label"
				option-value="value"
				@change="onRecordSelected"
			/>
			<Button
				label="Next"
				icon="pi pi-arrow-right"
				icon-pos="right"
				severity="secondary"
				class="ml-auto"
				size="small"
				@click="goToNext"
				:disabled="currentIndex === records.length - 1"
			/>
		</div>
		<div v-if="recordData" class="flex items-center justify-between gap-3 border-t border-slate-100 dark:border-surface-800 px-3 py-2">
			<h2 class="truncate text-xl font-bold">{{ recordData.source }}</h2>
			<div class="flex shrink-0 items-center gap-2">
				<Button
					:label="showFullPreview ? 'Hide preview' : 'Show preview'"
					:icon="showFullPreview ? 'pi pi-eye-slash' : 'pi pi-eye'"
					severity="secondary"
					text
					@click="showFullPreview = !showFullPreview"
				/>
				<Button
					label="Test findability"
					icon="pi pi-search"
					severity="secondary"
					text
					@click="openFindability"
				/>
				<Button label="Download" icon="pi pi-download" severity="secondary" outlined @click="onDownload" />
				<Button label="Save" icon="pi pi-save" :loading="saving" @click="onSave" />
			</div>
		</div>
	</div>

	<div class="w-full 2xl:mx-auto 2xl:max-w-[90%] mt-4">
		<div v-if="isLoadingRecord" class="p-4 text-center text-gray-500">Loading record...</div>
		<div v-else-if="recordData" class="bg-white dark:bg-surface-900 rounded-lg shadow-md p-6">
			<div class="flex flex-col lg:flex-row gap-6">
				<!-- Editable section cards -->
				<div class="flex-1 min-w-0">
					<!-- Title & intro (everything before the first "## ") -->
					<section id="adr-preamble" class="mb-4 rounded-xl border border-slate-200 dark:border-surface-700 overflow-hidden">
						<header class="flex items-center justify-between bg-slate-50 dark:bg-surface-800/50 px-4 py-2">
							<span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-surface-400">Title &amp; intro</span>
							<Button :label="isActive('preamble') ? 'Done' : 'Edit'" :icon="isActive('preamble') ? 'pi pi-check' : 'pi pi-pencil'" text size="small" @click="isActive('preamble') ? deactivate() : activate('preamble')" />
						</header>
						<div
							class="p-4 transition-colors"
							:class="isActive('preamble') ? '' : 'cursor-text hover:bg-slate-50 dark:hover:bg-surface-800/40'"
							data-card-content="preamble"
						>
							<MdEditor v-if="isActive('preamble')" v-model="doc.preamble" :preview="false" :theme="isDark ? 'dark' : 'light'" language="en-US" style="height: 220px" />
							<MdPreview v-else :model-value="doc.preamble.trim() || '_No title or intro._'" :theme="isDark ? 'dark' : 'light'" language="en-US" :auto-fold-threshold="100000" />
							<p v-if="isActive('preamble')" class="mt-2 text-xs text-amber-600 dark:text-amber-400">
								Changing the <code># H1</code> title renames this record on save.
							</p>
						</div>
					</section>

					<!-- One card per "## " section -->
					<section
						v-for="(section, index) in doc.sections"
						:key="index"
						:id="sectionAnchorId(section.heading)"
						class="mb-4 rounded-xl border border-slate-200 dark:border-surface-700 overflow-hidden"
					>
						<header class="flex items-center justify-between bg-slate-50 dark:bg-surface-800/50 px-4 py-2">
							<span class="font-semibold text-slate-700 dark:text-surface-100">{{ section.heading || "Untitled section" }}</span>
							<Button
								:label="isActive(index) ? 'Done' : 'Edit'"
								:icon="isActive(index) ? 'pi pi-check' : 'pi pi-pencil'"
								text
								size="small"
								@click="isActive(index) ? deactivate() : activate(index)"
							/>
						</header>
						<div
							class="p-4 transition-colors"
							:class="isActive(index) ? '' : 'cursor-text hover:bg-slate-50 dark:hover:bg-surface-800/40'"
							:data-card-content="index"
						>
							<MdEditor v-if="isActive(index)" v-model="section.body" :preview="false" :theme="isDark ? 'dark' : 'light'" language="en-US" style="height: 300px" />
							<MdPreview v-else :model-value="sectionPreview(section)" :theme="isDark ? 'dark' : 'light'" language="en-US" :auto-fold-threshold="100000" />
						</div>
					</section>

					<p v-if="!doc.sections.length" class="text-sm text-slate-500 dark:text-surface-400">
						No <code>##</code> sections found in this document — edit the title &amp; intro above, or add sections in the raw markdown.
					</p>
				</div>

				<!-- Full-document preview (collapsible, open by default) -->
				<aside v-if="showFullPreview" class="w-full lg:w-[42%] shrink-0">
					<div class="sticky top-[7.5rem] flex flex-col max-h-[calc(100vh-9rem)] rounded-xl border border-slate-200 dark:border-surface-700 overflow-hidden">
						<header class="flex shrink-0 items-center gap-2 bg-slate-50 dark:bg-surface-800/50 px-4 py-2">
							<i class="pi pi-eye text-slate-400 text-sm" />
							<span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-surface-400">Full preview</span>
							<span class="ml-auto text-xs text-slate-400">{{ currentRecord }}.md</span>
						</header>
						<div class="preview-compact flex-1 min-h-0 overflow-y-auto bg-slate-50 dark:bg-surface-800/30">
							<MdPreview :model-value="fullMarkdown" :theme="isDark ? 'dark' : 'light'" language="en-US" class="px-5 py-2" />
						</div>
					</div>
				</aside>
			</div>
		</div>
	</div>

	<ReviewFindingsDialog
		v-model:visible="reviewDialogOpen"
		:findings="navigableFindings"
		:loading="checking"
		:error="hasReviewError"
		:degraded="reviewDegraded"
		@submit-anyway="onSubmitAnyway"
		@navigate="onNavigateToFinding"
	/>

	<Dialog
		v-model:visible="findabilityVisible"
		header="Test findability"
		modal
		dismissable-mask
		:style="{ width: '34rem' }"
		:breakpoints="{ '960px': '90vw' }"
	>
		<p class="text-slate-500 mb-3">
			Type a coding task this ADR should cover, phrased the way someone would ask an agent.
		</p>
		<div class="flex gap-2">
			<InputText
				v-model="findabilityQuery"
				class="flex-1"
				placeholder="show a loading spinner while saving a form"
				@keyup.enter="runFindability"
			/>
			<Button
				label="Test"
				:loading="findabilityLoading"
				:disabled="!findabilityQuery.trim()"
				@click="runFindability"
			/>
		</div>

		<Message v-if="findabilityError" severity="error" class="mt-3" :closable="false">
			{{ findabilityError }}
		</Message>

		<div v-else-if="findabilityResult" class="mt-4">
			<div class="flex items-baseline gap-3">
				<span class="text-3xl font-semibold tabular-nums">{{ findabilityResult.score.toFixed(3) }}</span>
				<Tag
					:value="findabilityResult.kept ? 'Would be sent' : 'Would NOT be sent'"
					:severity="findabilityResult.kept ? 'success' : 'warn'"
				/>
			</div>
			<p class="text-slate-500 mt-2">
				<template v-if="findabilityResult.kept">
					Clears the {{ findabilityResult.threshold.toFixed(2) }} cutoff, so an agent asking this
					would be given this ADR.
				</template>
				<template v-else-if="findabilityResult.reason === 'over_max_sources'">
					Clears the {{ findabilityResult.threshold.toFixed(2) }} cutoff, but other ADRs scored
					higher and filled every slot.
				</template>
				<template v-else>
					Below the {{ findabilityResult.threshold.toFixed(2) }} cutoff, so an agent asking this gets
					nothing from this ADR. If the task is squarely in its scope, the wording is the problem —
					open the Search Tuning page for what to do about it.
				</template>
			</p>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { knowledgeBaseService, ReviewFinding, reviewService } from "@/api-service";
import ReviewFindingsDialog from "@/components/dialog/ReviewFindingsDialog.vue";
import { AdrDocument, AdrSection, joinAdr, sectionAnchorId, splitAdr } from "@/utils/adr-sections";
import { downloadMarkdown } from "@/utils/download-markdown";
import axios from "axios";
import { MdEditor, MdPreview } from "md-editor-v3";
import { Button, Dialog, InputText, Message, Select, Tag, useToast } from "primevue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

const router = useRouter();
const route = useRoute();
const toast = useToast();

const records = ref<any[]>([]);
const currentRecord = ref<string>("");
const recordData = ref<any>(null);

const findabilityVisible = ref(false);
const findabilityQuery = ref("");
const findabilityLoading = ref(false);
const findabilityError = ref("");
const findabilityResult = ref<{
	score: number;
	kept: boolean;
	reason: string | null;
	threshold: number;
} | null>(null);

const openFindability = () => {
	findabilityVisible.value = true;
};

// Asks the same endpoint the tuning page uses and picks this ADR out of the ranking, so
// the verdict here and the one there can't disagree. Unsaved edits aren't included: the
// score comes from what is indexed, which is what an agent would actually be matched on.
const runFindability = async () => {
	const query = findabilityQuery.value.trim();
	if (!query) return;
	findabilityLoading.value = true;
	findabilityError.value = "";
	try {
		const { data } = await knowledgeBaseService.searchPreview(query);
		const mine = data.candidates.find((c) => c.source === recordData.value?.source);
		if (!mine) {
			findabilityResult.value = null;
			findabilityError.value = "This ADR didn't appear among the candidates for that task at all.";
			return;
		}
		findabilityResult.value = {
			score: mine.score,
			kept: mine.kept,
			reason: mine.dropped_reason,
			threshold: data.retrieval_threshold,
		};
	} catch (err) {
		findabilityResult.value = null;
		findabilityError.value = axios.isAxiosError(err)
			? (err.response?.data?.detail ?? err.message)
			: "Could not test this ADR.";
	} finally {
		findabilityLoading.value = false;
	}
};
const isLoadingRecord = ref(false);
const saving = ref(false);

// The ADR split into an editable preamble + section cards. Editing a card mutates only its
// body; joinAdr reassembles the document byte-for-byte for untouched sections.
const doc = ref<AdrDocument>({ preamble: "", sections: [] });
// Single active editor: one section (or the preamble) is editable at a time. Opening
// another card, or clicking outside, commits the current edit and closes it.
const activeCard = ref<number | "preamble" | null>(null);
const showFullPreview = ref(true); // right-hand full-document preview, open by default

const isActive = (key: number | "preamble"): boolean => activeCard.value === key;

const activeCardElement = (): HTMLElement | null => {
	const key = activeCard.value;
	if (key === "preamble") return document.getElementById("adr-preamble");
	if (key === null) return null;
	return document.getElementById(sectionAnchorId(doc.value.sections[key].heading));
};

const focusActiveEditor = async (): Promise<void> => {
	await nextTick();
	activeCardElement()?.querySelector<HTMLElement>('.cm-content, textarea, [contenteditable="true"]')?.focus();
};

const activate = (key: number | "preamble"): void => {
	if (activeCard.value === key) return; // already editing this one — don't steal focus
	activeCard.value = key; // single-active: switching auto-commits and closes the previous card
	focusActiveEditor();
};

const deactivate = (): void => {
	activeCard.value = null;
};

// Which card's editable content a click landed in — or null if it landed on an interactive
// region (code block, link, button) or outside a content area, where it must NOT enter edit.
// The whole code block stays native: copy, fold toggle, horizontal scrollbar, text selection.
const cardKeyFromClick = (event: MouseEvent): number | "preamble" | null => {
	const target = event.target as HTMLElement;
	if (target.closest(".md-editor-code, a, button")) return null;
	const content = target.closest<HTMLElement>("[data-card-content]");
	if (!content) return null;
	const raw = content.dataset.cardContent ?? "";
	return raw === "preamble" ? "preamble" : Number(raw);
};

// Click-to-edit. Listens in the capture phase at the document so it fires before md-editor's
// own handlers (which otherwise swallow the click on rendered content).
const onDocumentClickCapture = (event: MouseEvent): void => {
	const key = cardKeyFromClick(event);
	if (key !== null) activate(key);
};

// A press outside the active card commits its edit and closes it. Uses mousedown (not
// click) so drag-selecting text and releasing outside the card doesn't close it — the
// selection begins with a mousedown inside the card.
const onDocumentMouseDown = (event: MouseEvent): void => {
	if (activeCard.value === null) return;
	const el = activeCardElement();
	if (el && !el.contains(event.target as Node)) activeCard.value = null;
};

onMounted(() => {
	document.addEventListener("click", onDocumentClickCapture, true);
	document.addEventListener("mousedown", onDocumentMouseDown);
});
onBeforeUnmount(() => {
	document.removeEventListener("click", onDocumentClickCapture, true);
	document.removeEventListener("mousedown", onDocumentMouseDown);
});

const checking = ref(false);
const reviewDialogOpen = ref(false);
const reviewFindings = ref<ReviewFinding[]>([]);
const hasReviewError = ref(false);
// The semantic (LLM) pass errored server-side, distinct from the whole call failing.
const reviewDegraded = ref(false);

// Track the app's dark mode (PrimeVue toggles `.app-dark`) so the editor/preview match.
const hasDarkClass = (): boolean =>
	document.documentElement.classList.contains("app-dark") || document.body.classList.contains("app-dark");
const isDark = ref<boolean>(hasDarkClass());
const observer = new MutationObserver(() => (isDark.value = hasDarkClass()));
observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
onBeforeUnmount(() => observer.disconnect());

const recordOptions = computed(() => records.value.map((record) => ({ label: record, value: record })));
const currentIndex = computed(() => records.value.indexOf(currentRecord.value));

const sectionPreview = (section: AdrSection): string => (section.body.trim() ? section.body : "_Empty section._");

// The whole document, reassembled live from the cards, for the right-hand preview.
const fullMarkdown = computed(() => joinAdr(doc.value));

const fetchRecord = async (recordName: string) => {
	if (!recordName) return;
	isLoadingRecord.value = true;
	try {
		const response = await knowledgeBaseService.getRawRecord(recordName);
		recordData.value = response.data;
	} catch (error) {
		console.error("Failed to fetch record:", error);
		recordData.value = null;
	} finally {
		isLoadingRecord.value = false;
	}
};

watch(currentRecord, (newRecord) => {
	if (newRecord) fetchRecord(newRecord);
});

// A freshly-loaded record resets the cards — split its markdown and collapse everything.
watch(recordData, (newData) => {
	doc.value = splitAdr(newData?.content ?? "");
	activeCard.value = null;
});

onMounted(async () => {
	try {
		const response = await knowledgeBaseService.getAllRecords();
		records.value = response.data.records.map((r) => r.source);
		// Initialize to record from route param, or first record if not found
		const recordIdFromRoute = route.params.id as string;
		if (recordIdFromRoute && records.value.includes(recordIdFromRoute)) {
			currentRecord.value = recordIdFromRoute;
		} else if (records.value.length > 0) {
			currentRecord.value = records.value[0];
			onRecordSelected();
		}
	} catch (error) {
		console.error("Failed to fetch records:", error);
	}
});

const goToPrevious = () => {
	const idx = currentIndex.value;
	if (idx > 0) {
		currentRecord.value = records.value[idx - 1];
		onRecordSelected();
	}
};

const goToNext = () => {
	const idx = currentIndex.value;
	if (idx < records.value.length - 1) {
		currentRecord.value = records.value[idx + 1];
		onRecordSelected();
	}
};

const onRecordSelected = () => {
	if (currentRecord.value) router.push(`/knowledge-base/${currentRecord.value}`);
};

// Downloads what's currently in the cards, including unsaved edits.
const onDownload = () => downloadMarkdown(currentRecord.value, joinAdr(doc.value));

// Find the section card a finding points at (by heading, case-insensitive). -1 if none
// (e.g. document-level findings), which keeps them non-navigable in the dialog.
const findSectionIndex = (section: string): number =>
	doc.value.sections.findIndex((s) => s.heading.toLowerCase() === section.toLowerCase());

// Decorate findings with `navigable` so the dialog makes the mappable ones clickable.
const navigableFindings = computed(() =>
	reviewFindings.value.map((f) => ({ ...f, navigable: findSectionIndex(f.section) !== -1 })),
);

const onNavigateToFinding = async (finding: ReviewFinding): Promise<void> => {
	const idx = findSectionIndex(finding.section);
	if (idx === -1) return;
	reviewDialogOpen.value = false;
	// Wait a tick so the finding click isn't seen as an "outside" click that closes the card.
	await nextTick();
	activeCard.value = idx; // open the offending card so it can be fixed in place
	await nextTick();
	const el = document.getElementById(sectionAnchorId(doc.value.sections[idx].heading));
	if (!el) return;
	el.scrollIntoView({ behavior: "smooth", block: "center" });
	el.querySelector<HTMLElement>('.cm-content, textarea, input, [contenteditable="true"]')?.focus();
	el.classList.add("finding-highlight");
	window.setTimeout(() => el.classList.remove("finding-highlight"), 1600);
};

const hasAdrErrors = async () => {
	reviewFindings.value = [];
	hasReviewError.value = false;
	reviewDegraded.value = false;
	checking.value = true;
	try {
		reviewDialogOpen.value = true;
		const result = await reviewService.reviewDocument(joinAdr(doc.value));
		const findings = result.data.findings;
		reviewDegraded.value = result.data.llm_ok === false;
		if (findings.length > 0) {
			reviewFindings.value = findings;
			return true;
		}
		// Degraded with no findings still halts the save so the user sees the banner.
		return reviewDegraded.value;
	} catch (error) {
		hasReviewError.value = true;
		return true;
	} finally {
		checking.value = false;
	}
};

// Saves the reassembled document and follows a rename: editing the H1 moves the record to a
// new source key, so the list entry, selection and route all have to point at the new one.
const save = async () => {
	const previous = currentRecord.value;
	const { data } = await knowledgeBaseService.saveMarkdown(previous, joinAdr(doc.value));

	if (data.source !== previous) {
		const index = records.value.indexOf(previous);
		if (index !== -1) records.value[index] = data.source;
		// Assigning currentRecord refetches via its watcher; `replace` so the back button
		// doesn't return to a key that no longer exists.
		currentRecord.value = data.source;
		router.replace(`/knowledge-base/${encodeURIComponent(data.source)}`);
	} else {
		// The server restamps the ADR id, so what's stored can differ from what was typed.
		// Pull it back so the cards show the canonical version rather than a stale edit.
		await fetchRecord(previous);
	}

	toast.add({ severity: "success", summary: "Record reindexed", detail: data.source, life: 3000 });
};

const onSaveFailed = (error: unknown) => {
	console.error("Failed to reindex record:", error);
	const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
	toast.add({ severity: "error", summary: "Failed to reindex record", detail, life: 4000 });
};

const onSave = async () => {
	saving.value = true;
	try {
		const needsAmendment = await hasAdrErrors();
		if (needsAmendment) return;
		reviewDialogOpen.value = false;
		await save();
	} catch (error) {
		onSaveFailed(error);
	} finally {
		saving.value = false;
	}
};

// User chose "Submit anyway" in the review dialog — save without re-reviewing.
const onSubmitAnyway = async () => {
	try {
		saving.value = true;
		await save();
	} catch (error) {
		onSaveFailed(error);
	} finally {
		saving.value = false;
	}
};
</script>

<style>
.finding-highlight {
	animation: finding-pulse 1.6s ease-out;
	border-radius: 0.75rem;
}
@keyframes finding-pulse {
	0% {
		box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.55);
	}
	100% {
		box-shadow: 0 0 0 8px rgba(59, 130, 246, 0);
	}
}
</style>
