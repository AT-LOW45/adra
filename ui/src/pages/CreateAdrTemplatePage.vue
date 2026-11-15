<template>
	<div class="flex flex-col gap-5 text-base">
		<!-- Page header -->
		<div class="flex items-end justify-between gap-4">
			<div class="flex flex-col gap-1">
				<h1 class="text-xl font-medium text-slate-700 dark:text-surface-100">Create ADR</h1>
				<p class="text-slate-500 dark:text-surface-400">Fill in the decision record — the preview on the right updates as you type.</p>
			</div>
			<div class="flex flex-col items-end gap-1 shrink-0">
				<div class="flex items-center gap-2">
					<span class="font-mono text-sm text-slate-400">{{ form.id || "Assigning ID…" }}</span>
					<Tag v-if="form.status" :value="form.status" :severity="statusSeverity" />
				</div>
				<!-- The server assigns the real id on create, so this one can shift if another
				     ADR lands first (or if this page/draft has been open a while). -->
				<div class="flex items-center gap-2">
					<Icon icon="material-symbols:info" />
					<span v-if="form.id" class="text-sm text-slate-400 dark:text-surface-400">
						Temporary — the final ID is assigned when you create the ADR.
					</span>
				</div>
			</div>
		</div>

		<div v-if="formatLoading" class="rounded-xl border border-slate-200 dark:border-surface-700 p-10 text-center text-slate-500">
			Loading the ADR format…
		</div>

		<!-- No fallback to built-in defaults: creating an ADR needs the backend anyway, and
		     guessing the format would produce ADRs in the wrong shape. -->
		<div
			v-else-if="formatError"
			class="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/30 p-6 flex flex-col items-start gap-3"
		>
			<p class="text-rose-700 dark:text-rose-300">{{ formatError }}</p>
			<Button label="Retry" icon="pi pi-refresh" severity="secondary" @click="retryFormat" />
		</div>

		<div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
			<!-- LEFT: form -->
			<div class="flex flex-col gap-7">
				<FormField label="Title" required :error-message="validationErrors?.properties?.title?.errors">
					<InputText v-model="form.title" placeholder="e.g. API authentication strategy" fluid />
				</FormField>

				<!-- One field per section, in format order. The three titles below keep their
				     own widgets; everything else, a team's own sections included, gets an editor. -->
				<div v-for="(section, i) in format" :key="section.title" :id="'adr-field-section-' + i">
					<FormField
						v-if="keyOf(section) === STATUS_KEY"
						:label="section.title"
						:required="section.required"
						:tip="tipFor(section)"
						:error-message="errorsFor(section)"
					>
						<Select v-model="form.status" :options="statusOptions" placeholder="Select status" fluid />
					</FormField>

					<div v-else-if="keyOf(section) === DECISION_KEY" class="flex flex-col gap-4">
						<FormField
							:label="section.title"
							:required="section.required"
							:tip="tipFor(section, 'Supports code blocks — use the </> button for fenced code.')"
							:error-message="errorsFor(section)"
						>
							<MdEditor
								v-model="form.sections[keyOf(section)]"
								:theme="isDark ? 'dark' : 'light'"
								:preview="false"
								:toolbars="mdToolbars"
								:footers="[]"
								language="en-US"
								placeholder="State the decision clearly. What was chosen and why?"
								style="height: 220px"
							/>
						</FormField>

						<FormField label="Alternatives considered">
							<div class="flex gap-2">
								<InputText
									v-model="alternativeInput"
									placeholder="Add an alternative..."
									class="flex-1"
									@keydown.enter.prevent="addAlternative"
								/>
								<Button icon="pi pi-plus" severity="secondary" aria-label="Add alternative" @click="addAlternative" />
							</div>
							<div v-if="form.alternatives.length" class="flex flex-wrap gap-1.5 mt-2">
								<Chip v-for="(alt, j) in form.alternatives" :key="j" :label="alt" removable @remove="form.alternatives.splice(j, 1)" />
							</div>
						</FormField>

						<FormField label="Related ADRs" :tip="{ message: 'Existing records in the knowledge base that this decision relates to.' }">
							<MultiSelect
								v-model="form.relatedAdrs"
								:options="relatedAdrChoices"
								:loading="loadingRelatedAdrs"
								placeholder="Select related ADRs"
								display="chip"
								filter
								:show-toggle-all="false"
								empty-message="No other ADRs yet"
								empty-filter-message="No match"
								fluid
							/>
						</FormField>
					</div>

					<div v-else-if="keyOf(section) === CONSEQUENCES_KEY" class="flex flex-col gap-4">
						<FormField
							:label="section.title"
							:required="section.required"
							:tip="tipFor(section)"
							:error-message="errorsFor(section)"
						>
							<Textarea
								v-model="form.positiveConsequences"
								placeholder="What improves as a result of this decision?"
								:auto-resize="true"
								rows="3"
								fluid
							/>
						</FormField>
						<FormField label="Trade-offs">
							<Textarea
								v-model="form.negativeConsequences"
								placeholder="What gets harder, slower, or more complex?"
								:auto-resize="true"
								rows="3"
								fluid
							/>
						</FormField>
					</div>

					<FormField
						v-else
						:label="section.title"
						:required="section.required"
						:tip="tipFor(section)"
						:error-message="errorsFor(section)"
					>
						<MdEditor
							v-model="form.sections[keyOf(section)]"
							:theme="isDark ? 'dark' : 'light'"
							:preview="false"
							:toolbars="mdToolbars"
							:footers="[]"
							language="en-US"
							:placeholder="`Write the ${section.title.toLowerCase()} section...`"
							style="height: 200px"
						/>
					</FormField>
				</div>

				<!-- Custom sections -->
				<section class="flex flex-col gap-4">
					<h2 class="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-slate-400">
						<i class="pi pi-plus-circle text-xs" />
						Custom sections
					</h2>

					<div
						v-for="(section, i) in form.customSections"
						:key="i"
						:id="'adr-field-custom-' + i"
						class="flex flex-col gap-3 rounded-xl border border-slate-200 dark:border-surface-700 p-4 bg-white"
					>
						<div class="flex items-center gap-2">
							<InputText v-model="section.heading" placeholder="Section heading — e.g. Exception Classes" class="flex-1" />
							<SelectButton
								v-model="section.format"
								:options="formatOptions"
								option-label="label"
								option-value="value"
								:allow-empty="false"
								size="small"
							/>
							<Button icon="pi pi-trash" severity="danger" text aria-label="Remove section" @click="removeCustomSection(i)" />
						</div>

						<Textarea
							v-if="section.format === 'plain'"
							v-model="section.body"
							placeholder="Section content..."
							:auto-resize="true"
							rows="3"
							fluid
						/>
						<MdEditor
							v-else
							v-model="section.body"
							:theme="isDark ? 'dark' : 'light'"
							:preview="false"
							:toolbars="mdToolbars"
							:footers="[]"
							language="en-US"
							placeholder="Section content — supports code blocks via the </> button..."
							style="height: 260px"
						/>
					</div>

					<Button label="Add section" icon="pi pi-plus" severity="secondary" outlined class="self-start" @click="addCustomSection" />
				</section>
			</div>

			<!-- RIGHT: live preview (sticky) -->
			<div class="lg:sticky lg:top-5">
				<div
					class="rounded-xl border border-slate-200 dark:border-surface-700 bg-white dark:bg-surface-900 overflow-hidden flex flex-col max-h-[calc(100vh-5.5rem)]"
				>
					<div
						class="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 dark:border-surface-700 bg-slate-50 dark:bg-surface-800 shrink-0"
					>
						<i class="pi pi-eye text-slate-400 text-sm" />
						<span class="text-sm font-medium text-slate-500 dark:text-surface-300">Live preview</span>
						<span class="ml-auto text-xs text-slate-400">{{ form.id || "adr" }}.md</span>
					</div>
					<MdPreview
						:model-value="markdown"
						:theme="isDark ? 'dark' : 'light'"
						language="en-US"
						class="flex-1 min-h-0 overflow-y-auto px-5"
					/>
				</div>
			</div>
		</div>

		<!-- Actions (sticky so they're reachable without scrolling to the bottom) -->
		<div
			v-if="!formatLoading && !formatError"
			class="sticky bottom-0 z-10 -mx-5 flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-100/95 px-5 py-3 backdrop-blur dark:border-surface-800 dark:bg-surface-900/95"
		>
			<Button label="Save draft" severity="secondary" icon="pi pi-save" :loading="savingDraft" :disabled="submitting" @click="saveDraft" />
			<Button label="Create ADR" icon="pi pi-check" icon-pos="right" :loading="submitting" :disabled="!form.id" @click="submitAdr" />
		</div>
	</div>

	<!-- Unsaved-changes warning shown when navigating away with unsaved progress -->
	<Dialog v-model:visible="showLeaveDialog" header="Unsaved changes" :modal="true" :closable="false" :style="{ width: '460px' }">
		<p class="text-slate-600 dark:text-surface-300">
			Leaving this page will discard your unsaved progress. Would you like to save it as a draft first?
		</p>
		<template #footer>
			<div class="flex w-full items-center justify-between">
				<Button label="Leave without saving" severity="danger" text @click="discardAndLeave" />
				<div class="flex gap-2">
					<Button label="Cancel" severity="secondary" text @click="cancelLeave" />
					<Button label="Save as draft" icon="pi pi-save" :loading="savingDraft" @click="saveDraftAndLeave" />
				</div>
			</div>
		</template>
	</Dialog>

	<ReviewFindingsDialog
		v-model:visible="showReviewDialog"
		:findings="navigableFindings"
		:loading="checking"
		:error="hasReviewError"
		:degraded="reviewDegraded"
		@submit-anyway="submitAnyway"
			@navigate="onNavigateToFinding"
	/>
</template>

<script setup lang="ts">
import type { AdrSection, ReviewFinding } from "@/api-service";
import { computed } from "vue";
import ReviewFindingsDialog from "@/components/dialog/ReviewFindingsDialog.vue";
import FormField from "@/components/form/FormField.vue";
import { useCreateAdr } from "@/composables/useCreateAdr";
import { Icon } from '@iconify/vue';
import { MdEditor, MdPreview } from "md-editor-v3";
import { Button, Chip, Dialog, InputText, MultiSelect, Select, SelectButton, Tag, Textarea } from "primevue";

const {
	form,
	format,
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
	statusSeverity,
	markdown,
	isDark,
	statusOptions,
	formatOptions,
	mdToolbars,
	relatedAdrChoices,
	loadingRelatedAdrs,
	addAlternative,
	addCustomSection,
	removeCustomSection,
	saveDraft,
	submitAdr,
	showLeaveDialog,
	cancelLeave,
	discardAndLeave,
	saveDraftAndLeave,
	reviewFindings,
	reviewDegraded,
	showReviewDialog,
	checking,
	hasReviewError,
	submitAnyway,
} = useCreateAdr();

// Map a review finding's section to the form field it came from, so a finding in the
// dialog can jump to (and highlight) the offending field. Format sections match by
// title, ignoring case, the way the review itself matches headings; custom sections
// match by heading. Document-level findings (word count, unclosed fence) have no
// single field, so they aren't navigable.
const keyOf = (section: AdrSection): string => sectionKey(section.title);

const errorsFor = (section: AdrSection): string[] | undefined =>
	(validationErrors.value?.properties as Record<string, { errors: string[] } | undefined> | undefined)?.[
		fieldKey(keyOf(section))
	]?.errors;

const tipFor = (section: AdrSection, fallback?: string) => {
	const message = section.purpose?.trim() || fallback;
	return message ? { message } : undefined;
};

const sectionAnchorId = (section: string): string | null => {
	const wanted = section.trim().toLowerCase();
	const idx = format.value.findIndex((s) => keyOf(s) === wanted);
	if (idx !== -1) return `adr-field-section-${idx}`;
	const custom = form.value.customSections.findIndex((s) => s.heading.trim().toLowerCase() === wanted);
	return custom !== -1 ? `adr-field-custom-${custom}` : null;
};

// Decorate findings with `navigable` so the dialog makes the mappable ones clickable.
const navigableFindings = computed(() =>
	reviewFindings.value.map((f) => ({ ...f, navigable: sectionAnchorId(f.section) !== null })),
);

const onNavigateToFinding = (finding: ReviewFinding): void => {
	const id = sectionAnchorId(finding.section);
	if (!id) return;
	const el = document.getElementById(id);
	if (!el) return;
	showReviewDialog.value = false;
	el.scrollIntoView({ behavior: "smooth", block: "center" });
	el.querySelector<HTMLElement>('input, textarea, [contenteditable="true"], .cm-editor')?.focus();
	el.classList.add("finding-highlight");
	window.setTimeout(() => el.classList.remove("finding-highlight"), 1600);
};
</script>

<style>
.finding-highlight {
	animation: finding-pulse 1.6s ease-out;
	border-radius: 0.5rem;
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
