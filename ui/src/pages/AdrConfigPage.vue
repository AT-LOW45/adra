<template>
	<div class="p-4">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-semibold mb-1">ADR Format</h1>
				<p class="text-slate-500 mb-4">
					The sections your team's ADRs have. The Create ADR form follows this order, and the quality
					review checks ADRs against it.
				</p>
			</div>
			<Tag
				v-if="format"
				:value="format.source === 'saved' ? 'Saved' : 'Default'"
				:severity="format.source === 'saved' ? 'info' : 'secondary'"
				class="shrink-0 mt-1"
			/>
		</div>

		<Message v-if="loadError" severity="error" :closable="false">{{ loadError }}</Message>

		<div v-else class="rounded-md p-5 bg-white shadow-sm">
			<Message severity="info" :closable="false" class="mb-4">
				Changes apply to new ADRs and to reviews. ADRs already in the knowledge base aren't changed.
			</Message>

			<div v-if="loading" class="text-slate-500">Loading…</div>

			<template v-else>
				<!-- Column headings, shown once rather than repeated on every row. -->
				<div class="hidden md:grid grid-cols-[2rem_minmax(0,14rem)_minmax(0,1fr)_6rem_7rem] gap-3 px-3 pb-2 text-sm font-medium text-slate-500">
					<span />
					<span>Section title</span>
					<span>What it's for</span>
					<span>Required</span>
					<span />
				</div>

				<ol class="list-none p-0 m-0 flex flex-col gap-2">
					<li
						v-for="(section, i) in sections"
						:key="section.key"
						class="grid grid-cols-1 md:grid-cols-[2rem_minmax(0,14rem)_minmax(0,1fr)_6rem_7rem] gap-3 items-start rounded-lg border border-slate-200 p-3"
					>
						<span class="hidden md:block text-slate-400 font-mono text-sm pt-2.5 text-right">{{ i + 1 }}</span>

						<div class="flex flex-col gap-1">
							<label :for="`section-title-${section.key}`" class="md:sr-only text-sm text-slate-600">Section title</label>
							<InputText
								:id="`section-title-${section.key}`"
								v-model="section.title"
								placeholder="e.g. Decision"
								maxlength="100"
								:invalid="!!rowErrors[i]"
								fluid
							/>
							<small v-if="rowErrors[i]" class="text-red-600">{{ rowErrors[i] }}</small>
						</div>

						<div class="flex flex-col gap-1">
							<label :for="`section-purpose-${section.key}`" class="md:sr-only text-sm text-slate-600">What it's for</label>
							<Textarea
								:id="`section-purpose-${section.key}`"
								v-model="section.purpose"
								placeholder="Optional. Without it, the review judges the section by its title."
								maxlength="500"
								rows="1"
								auto-resize
								fluid
							/>
						</div>

						<div class="flex items-center gap-2 md:pt-2">
							<ToggleSwitch v-model="section.required" :input-id="`section-required-${section.key}`" />
							<label :for="`section-required-${section.key}`" class="md:sr-only text-sm text-slate-600">Required</label>
						</div>

						<div class="flex items-center gap-1 md:justify-end">
							<Button
								icon="pi pi-arrow-up"
								severity="secondary"
								text
								rounded
								size="small"
								:disabled="i === 0"
								:aria-label="`Move ${section.title || 'section'} up`"
								@click="move(i, -1)"
							/>
							<Button
								icon="pi pi-arrow-down"
								severity="secondary"
								text
								rounded
								size="small"
								:disabled="i === sections.length - 1"
								:aria-label="`Move ${section.title || 'section'} down`"
								@click="move(i, 1)"
							/>
							<Button
								icon="pi pi-trash"
								severity="danger"
								text
								rounded
								size="small"
								:disabled="sections.length === 1"
								:aria-label="`Remove ${section.title || 'section'}`"
								@click="remove(i)"
							/>
						</div>
					</li>
				</ol>

				<Button label="Add section" icon="pi pi-plus" severity="secondary" outlined class="mt-3" @click="add" />

				<p class="text-sm text-slate-500 mt-4">
					A required section that's missing or empty is reported as an error when an ADR is reviewed.
				</p>

				<div class="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100">
					<Button label="Save" :loading="saving" :disabled="!isDirty || hasErrors" @click="onSave" />
					<Button
						label="Discard changes"
						severity="secondary"
						text
						:disabled="!isDirty"
						@click="discard"
					/>
					<Button
						label="Reset to default"
						severity="secondary"
						text
						class="ml-auto"
						:loading="resetting"
						:disabled="format?.source !== 'saved'"
						@click="resetDialogVisible = true"
					/>
				</div>
			</template>
		</div>

		<Dialog
			v-model:visible="resetDialogVisible"
			header="Reset to the default format?"
			modal
			:style="{ width: '460px' }"
		>
			<p class="text-slate-600">
				Your saved format is replaced by the default sections:
				<strong>{{ defaultTitles }}</strong>. Existing ADRs aren't changed.
			</p>
			<template #footer>
				<Button label="Cancel" severity="secondary" text @click="resetDialogVisible = false" />
				<Button label="Reset" severity="danger" :loading="resetting" @click="onReset" />
			</template>
		</Dialog>

		<Dialog v-model:visible="leaveDialogVisible" header="Unsaved changes" modal :closable="false" :style="{ width: '460px' }">
			<p class="text-slate-600">Leaving this page will discard your changes to the ADR format.</p>
			<template #footer>
				<Button label="Stay" severity="secondary" text @click="cancelLeave" />
				<Button label="Leave without saving" severity="danger" @click="confirmLeave" />
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { settingsService, type AdrFormat, type AdrSection } from "@/api-service";
import axios from "axios";
import { Button, Dialog, InputText, Message, Tag, Textarea, ToggleSwitch, useToast } from "primevue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";

// A row being edited. `key` keeps each row's inputs attached to it while rows move.
type EditableSection = AdrSection & { key: number };

const toast = useToast();
const router = useRouter();

const format = ref<AdrFormat | null>(null);
const sections = ref<EditableSection[]>([]);
const loading = ref(true);
const loadError = ref("");
const saving = ref(false);
const resetting = ref(false);
const resetDialogVisible = ref(false);

let nextKey = 0;
const toEditable = (list: AdrSection[]): EditableSection[] =>
	list.map((s) => ({ title: s.title, purpose: s.purpose, required: s.required, key: nextKey++ }));

// What gets sent, and what dirtiness compares: the server trims, so trimming here keeps
// a trailing space from counting as an unsaved change.
const toPayload = (list: AdrSection[]): AdrSection[] =>
	list.map((s) => ({ title: s.title.trim(), purpose: s.purpose.trim(), required: s.required }));

const isDirty = computed(
	() => !!format.value && JSON.stringify(toPayload(sections.value)) !== JSON.stringify(toPayload(format.value.sections)),
);

// The same rules the server enforces, shown per row so the problem is visible before
// saving. Titles are compared ignoring case because the review matches headings that way.
const rowErrors = computed<(string | null)[]>(() => {
	const counts = new Map<string, number>();
	for (const s of sections.value) {
		const t = s.title.trim().toLowerCase();
		if (t) counts.set(t, (counts.get(t) ?? 0) + 1);
	}
	return sections.value.map((s) => {
		const t = s.title.trim();
		if (!t) return "A title is required.";
		if ((counts.get(t.toLowerCase()) ?? 0) > 1) return "Another section has this title.";
		return null;
	});
});
const hasErrors = computed(() => rowErrors.value.some(Boolean));

const defaultTitles = computed(() => (format.value?.default_sections ?? []).map((s) => s.title).join(", "));

const apply = (data: AdrFormat) => {
	format.value = data;
	sections.value = toEditable(data.sections);
};

const message = (err: unknown, fallback: string) =>
	axios.isAxiosError(err) ? (err.response?.data?.detail ?? err.message) : fallback;

onMounted(async () => {
	try {
		const { data } = await settingsService.getAdrFormat();
		apply(data);
	} catch (err) {
		loadError.value = message(err, "Could not load the ADR format.");
	} finally {
		loading.value = false;
	}
});

const add = () => {
	sections.value.push({ title: "", purpose: "", required: false, key: nextKey++ });
};

const remove = (index: number) => {
	sections.value.splice(index, 1);
};

const move = (index: number, offset: -1 | 1) => {
	const target = index + offset;
	if (target < 0 || target >= sections.value.length) return;
	const list = sections.value;
	[list[index], list[target]] = [list[target], list[index]];
};

const discard = () => {
	if (format.value) sections.value = toEditable(format.value.sections);
};

const onSave = async () => {
	if (hasErrors.value) return;
	saving.value = true;
	try {
		const { data } = await settingsService.saveAdrFormat(toPayload(sections.value));
		apply(data);
		toast.add({ severity: "success", summary: "ADR format saved", life: 3000 });
	} catch (err) {
		toast.add({ severity: "error", summary: "Couldn't save the ADR format", detail: message(err, ""), life: 5000 });
	} finally {
		saving.value = false;
	}
};

const onReset = async () => {
	resetting.value = true;
	try {
		const { data } = await settingsService.saveAdrFormat(null);
		apply(data);
		resetDialogVisible.value = false;
		toast.add({ severity: "success", summary: "ADR format reset to the default", life: 3000 });
	} catch (err) {
		toast.add({ severity: "error", summary: "Couldn't reset the ADR format", detail: message(err, ""), life: 5000 });
	} finally {
		resetting.value = false;
	}
};

// Unsaved changes: the browser's own prompt on refresh or tab close, and a dialog for
// navigation inside the app.
const handleBeforeUnload = (event: BeforeUnloadEvent) => {
	if (isDirty.value) {
		event.preventDefault();
		event.returnValue = "";
	}
};
window.addEventListener("beforeunload", handleBeforeUnload);
onBeforeUnmount(() => window.removeEventListener("beforeunload", handleBeforeUnload));

const leaveDialogVisible = ref(false);
const pendingRoute = ref<string | null>(null);
let bypassLeaveGuard = false;

onBeforeRouteLeave((to) => {
	if (bypassLeaveGuard || !isDirty.value) return true;
	pendingRoute.value = to.fullPath;
	leaveDialogVisible.value = true;
	return false;
});

const cancelLeave = () => {
	leaveDialogVisible.value = false;
	pendingRoute.value = null;
};

const confirmLeave = () => {
	leaveDialogVisible.value = false;
	const target = pendingRoute.value;
	pendingRoute.value = null;
	bypassLeaveGuard = true;
	if (target) router.push(target);
};
</script>
