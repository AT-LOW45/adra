<template>
	<div class="p-4">
		<h1 class="text-2xl font-semibold mb-1">Search Tuning</h1>
		<p class="text-slate-500 mb-4">
			See which ADRs a coding task retrieves, and adjust how strict the match has to be.
		</p>

		<!-- Test search -->
		<div class="rounded-md p-5 bg-white shadow-sm">
			<label for="task" class="block font-medium mb-2">Test a coding task</label>
			<div class="flex gap-2">
				<InputText
					id="task"
					v-model="query"
					class="flex-1"
					placeholder="add an endpoint to list zones"
					@keyup.enter="onSearch"
				/>
				<Button label="Search" :loading="searching" :disabled="!query.trim()" @click="onSearch" />
			</div>
			<small class="text-slate-500">
				Phrase it the way you would ask an agent. This runs the same retrieval the agent gets.
			</small>

			<Message v-if="searchError" severity="error" class="mt-3" :closable="false">{{ searchError }}</Message>

			<div v-if="preview" class="mt-5">
				<Message v-if="!keptCandidates.length" severity="warn" :closable="false" class="mb-3">
					No ADR clears the threshold, so the agent is told none applies and writes code following the
					existing codebase.
				</Message>

				<DataTable :value="preview.candidates" row-hover>
					<template #empty>
						<span class="text-slate-500">Nothing indexed to match against.</span>
					</template>

					<Column header="ADR">
						<template #body="{ data }">
							<div class="font-medium">{{ data.title }}</div>
							<div class="text-xs text-slate-400">{{ data.source }}</div>
						</template>
					</Column>

					<Column header="Score" style="width: 8rem">
						<template #body="{ data }">
							<span :class="data.score >= draftThreshold ? 'font-semibold' : 'text-slate-500'">
								{{ data.score.toFixed(3) }}
							</span>
						</template>
					</Column>

					<Column header="Outcome" style="width: 16rem">
						<template #body="{ data }">
							<Tag v-if="outcomeOf(data).kept" value="Sent to agent" severity="success" />
							<Tag v-else :value="outcomeOf(data).label" severity="secondary" />
						</template>
					</Column>
				</DataTable>

				<small class="text-slate-500 block mt-2">
					At most {{ preview.max_sources }} ADRs are ever sent, strongest first, even when more clear
					the threshold.
				</small>
			</div>
		</div>

		<!-- Threshold -->
		<div class="rounded-md p-5 bg-white shadow-sm mt-4">
			<div class="flex items-center justify-between mb-1">
				<h2 class="text-lg font-semibold">Relevance threshold</h2>
				<Tag
					:value="settings?.retrieval_threshold_source === 'saved' ? 'Saved' : 'Default'"
					:severity="settings?.retrieval_threshold_source === 'saved' ? 'info' : 'secondary'"
				/>
			</div>
			<p class="text-slate-500 mb-4">
				The minimum score an ADR must reach to be sent. Raise it if unrelated tasks pull in ADRs; lower
				it if relevant ADRs are being missed.
			</p>

			<div class="flex items-center gap-4">
				<Slider v-model="draftThreshold" :min="0" :max="1" :step="0.01" class="flex-1" />
				<InputNumber
					v-model="draftThreshold"
					:min="0"
					:max="1"
					:step="0.01"
					:min-fraction-digits="2"
					:max-fraction-digits="2"
					show-buttons
					class="w-36"
				/>
			</div>

			<div v-if="validationErrors?.properties?.retrievalThreshold" class="text-red-600 text-sm mt-2">
				{{ validationErrors.properties.retrievalThreshold.errors[0] }}
			</div>

			<!-- Only shown once there are scores to compare against, since the effect of a change
			     is meaningless without them. -->
			<Message v-if="preview && isDirty" severity="info" class="mt-3" :closable="false">
				At {{ draftThreshold.toFixed(2) }} this task would send
				<strong>{{ keptCandidates.length }}</strong>
				{{ keptCandidates.length === 1 ? "ADR" : "ADRs" }} instead of
				<strong>{{ serverKeptCount }}</strong
				>. Not saved yet.
			</Message>

			<div class="flex items-center gap-2 mt-4">
				<Button label="Save" :loading="saving" :disabled="!isDirty" @click="onSave" />
				<Button
					label="Reset to default"
					severity="secondary"
					text
					:loading="resetting"
					:disabled="settings?.retrieval_threshold_source !== 'saved'"
					@click="onReset"
				/>
				<span v-if="settings" class="text-sm text-slate-500 ml-auto">
					Default is {{ settings.default_retrieval_threshold.toFixed(2) }}
				</span>
			</div>

			<Message v-if="settingsError" severity="error" class="mt-3" :closable="false">
				{{ settingsError }}
			</Message>
		</div>
	</div>
</template>

<script setup lang="ts">
import { knowledgeBaseService, settingsService, type SearchCandidate, type SearchPreview, type Settings } from "@/api-service";
import { retrievalThresholdSchema } from "@/schemas/settingsSchema";
import useZodValidation from "@/composables/useZodValidation";
import axios from "axios";
import { Button, Column, DataTable, InputNumber, InputText, Message, Slider, Tag, useToast } from "primevue";
import { computed, onMounted, ref } from "vue";

const toast = useToast();
const { validate, validationErrors } = useZodValidation(retrievalThresholdSchema);

const query = ref("");
const preview = ref<SearchPreview | null>(null);
const searching = ref(false);
const searchError = ref("");

const settings = ref<Settings | null>(null);
const draftThreshold = ref(0);
const saving = ref(false);
const resetting = ref(false);
const settingsError = ref("");

const isDirty = computed(() => !!settings.value && draftThreshold.value !== settings.value.retrieval_threshold);

// The server's cap, taken from the preview response rather than hardcoded, so changing
// it in chroma_helper.py doesn't leave this page quietly reporting the old number.
const maxSources = computed(() => preview.value?.max_sources ?? 0);

/**
 * Re-evaluate a candidate against the slider's current value.
 *
 * The server decides what agents actually get; this only re-reads scores the server
 * already returned, so moving the slider answers immediately instead of making a round
 * trip per step. It repeats the server's rule — at or above the threshold, strongest
 * first, up to the cap — so it has to stay in step with `rank_sources`. Saving re-runs
 * the search, so anything that drifted is corrected then.
 */
const recomputed = computed(() => {
	if (!preview.value) return new Map<string, { kept: boolean; label: string }>();
	let keptCount = 0;
	return new Map(
		preview.value.candidates.map((c) => {
			if (c.score < draftThreshold.value) return [c.source, { kept: false, label: "Below threshold" }];
			if (keptCount >= maxSources.value) return [c.source, { kept: false, label: `Over the ${maxSources.value}-ADR cap` }];
			keptCount += 1;
			return [c.source, { kept: true, label: "Sent to agent" }];
		})
	);
});

const outcomeOf = (candidate: SearchCandidate) =>
	recomputed.value.get(candidate.source) ?? { kept: candidate.kept, label: "Dropped" };

const keptCandidates = computed(() => (preview.value?.candidates ?? []).filter((c) => outcomeOf(c).kept));

// What the server reported before any slider movement, so the "instead of N" comparison
// is against reality rather than the previous slider position.
const serverKeptCount = computed(() => (preview.value?.candidates ?? []).filter((c) => c.kept).length);

const message = (err: unknown, fallback: string) =>
	axios.isAxiosError(err) ? (err.response?.data?.detail ?? err.message) : fallback;

const loadSettings = async () => {
	try {
		const { data } = await settingsService.getSettings();
		settings.value = data;
		draftThreshold.value = data.retrieval_threshold;
	} catch (err) {
		settingsError.value = message(err, "Could not load settings.");
	}
};

const onSearch = async () => {
	if (!query.value.trim()) return;
	searching.value = true;
	searchError.value = "";
	try {
		// Evaluated at the slider's value, not the saved one, so an unsaved threshold is
		// tested against fresh scores rather than only re-read from a stale response.
		const { data } = await knowledgeBaseService.searchPreview(query.value, draftThreshold.value);
		preview.value = data;
	} catch (err) {
		preview.value = null;
		searchError.value = message(err, "Search failed.");
	} finally {
		searching.value = false;
	}
};

const persist = async (value: number | null, busy: typeof saving) => {
	busy.value = true;
	settingsError.value = "";
	try {
		const { data } = await settingsService.saveRetrievalThreshold(value);
		settings.value = data;
		draftThreshold.value = data.retrieval_threshold;
		toast.add({
			severity: "success",
			summary: "Threshold updated",
			detail: `Agents now receive ADRs scoring ${data.retrieval_threshold.toFixed(2)} or above.`,
			life: 3000,
		});
		if (query.value.trim()) await onSearch();
	} catch (err) {
		settingsError.value = message(err, "Could not save the threshold.");
	} finally {
		busy.value = false;
	}
};

const onSave = async () => {
	if (!validate({ retrievalThreshold: draftThreshold.value })) return;
	await persist(draftThreshold.value, saving);
};

// null clears the saved value rather than writing the default as a saved one, so the
// team follows the default if it later changes.
const onReset = () => persist(null, resetting);

onMounted(loadSettings);
</script>
