<template>
	<div class="p-4">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-semibold mb-1">Search Tuning</h1>
				<p class="text-slate-500 mb-4">
					See which ADRs a coding task retrieves, and adjust how strict the match has to be.
				</p>
			</div>
			<Button
				label="How to read this"
				icon="pi pi-question-circle"
				severity="secondary"
				text
				@click="helpVisible = true"
			/>
		</div>

		<div class="rounded-md p-5 bg-white shadow-sm">
			<Tabs value="single">
				<TabList>
					<Tab value="single">Test a task</Tab>
					<Tab value="calibrate">Find the right cutoff</Tab>
				</TabList>
				<TabPanels class="!px-0">

				<TabPanel value="single">
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

				<DataTable :value="preview.candidates" row-hover class="cursor-pointer" @row-click="openRecord">
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
					the threshold. Click a row to open that ADR in a new tab.
				</small>
			</div>
				</TabPanel>

				<TabPanel value="calibrate">
					<p class="text-slate-500 mb-4">
						List tasks your ADRs should cover, and tasks they shouldn't. The cutoff belongs between
						the two — above everything that should match, below everything that shouldn't.
					</p>

					<div class="grid md:grid-cols-2 gap-4">
						<div>
							<label for="genuine" class="block font-medium mb-2">Should match your ADRs</label>
							<Textarea
								id="genuine"
								v-model="genuineText"
								rows="6"
								class="w-full"
								placeholder="add an endpoint to list zones&#10;protect a route with JWT&#10;fetch orders by customer"
							/>
						</div>
						<div>
							<label for="unrelated" class="block font-medium mb-2">Should match nothing</label>
							<Textarea
								id="unrelated"
								v-model="unrelatedText"
								rows="6"
								class="w-full"
								placeholder="parse a CSV line&#10;reverse a string&#10;sort a list of dicts by a key"
							/>
						</div>
					</div>
					<small class="text-slate-500 block mt-2">
						One task per line. The right-hand ones must be real coding tasks, not off-topic text —
						an agent never asks for a cookie recipe, but it does ask for a CSV parser, and
						off-topic text scores so low it suggests a cutoff that lets real tasks through.
					</small>

					<Button
						label="Suggest a cutoff"
						class="mt-4"
						:loading="calibrating"
						:disabled="!genuineLines.length || !unrelatedLines.length"
						@click="onCalibrate"
					/>

					<Message v-if="calibrateError" severity="error" class="mt-3" :closable="false">
						{{ calibrateError }}
					</Message>

					<div v-if="calibration" class="mt-5">
						<div class="grid md:grid-cols-2 gap-4">
							<div v-for="group in calibrationGroups" :key="group.label">
								<h3 class="font-medium mb-2">{{ group.label }}</h3>
								<ul class="list-none p-0 m-0 text-sm">
									<li
										v-for="row in group.rows"
										:key="row.query"
										class="flex gap-3 py-1 border-b border-slate-100 last:border-0"
									>
										<span class="tabular-nums w-14 shrink-0" :class="group.scoreClass(row.score)">
											{{ row.score === null ? "—" : row.score.toFixed(3) }}
										</span>
										<span class="text-slate-600">{{ row.query }}</span>
									</li>
								</ul>
							</div>
						</div>

						<!-- A missing suggestion is the finding, not an error: the two sets overlap and
						     no cutoff separates them, which points at the ADRs rather than the number. -->
						<Message
							v-if="calibration.suggested_threshold === null"
							severity="warn"
							class="mt-4"
							:closable="false"
						>
							These overlap — something that should match scores at or below something that
							shouldn't, so no single cutoff separates them. Retrieval can't tell these tasks
							apart. Clearer or more specific ADRs help more than any number here.
						</Message>

						<div v-else class="mt-4 flex items-center gap-3 flex-wrap">
							<span class="text-slate-600">
								Everything that should match is
								<strong>{{ calibration.floor?.toFixed(3) }}</strong> and above; everything that
								shouldn't is <strong>{{ calibration.ceiling?.toFixed(3) }}</strong> and below.
							</span>
							<Button
								:label="`Use ${calibration.suggested_threshold.toFixed(2)}`"
								size="small"
								@click="useSuggestion"
							/>
						</div>
					</div>
				</TabPanel>

				</TabPanels>
			</Tabs>
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

			<!-- max-w-xl: a 0-1 slider gains nothing from spanning a wide screen, and the
			     longer the track the coarser each pixel of drag is. min-w-0 lets the slider
			     shrink instead of pushing the number input past the card edge. -->
			<div class="flex items-center gap-4 max-w-xl">
				<Slider v-model="draftThreshold" :min="0" :max="1" :step="0.01" class="flex-1 min-w-0" />
				<InputNumber
					v-model="draftThreshold"
					:min="0"
					:max="1"
					:step="0.01"
					:min-fraction-digits="2"
					:max-fraction-digits="2"
					show-buttons
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

		<Dialog
			v-model:visible="helpVisible"
			header="How to read this page"
			modal
			dismissable-mask
			:style="{ width: '46rem' }"
			:breakpoints="{ '960px': '90vw' }"
		>
			<div class="flex flex-col gap-5 text-slate-700 leading-relaxed">
				<section>
					<h3 class="font-semibold mb-1">What the scores mean</h3>
					<p>
						Each score is how closely a coding task matches an ADR. It runs 0 to 1, but it is
						<strong>not a percentage</strong> — scores bunch into a narrow band, so an ADR can top
						the list at 0.59 and still be a poor match. Read the <strong>gap</strong> between
						scores rather than any single number: a clear drop after the first result means
						retrieval is confident, while six ADRs within 0.05 of each other means it isn't.
					</p>
				</section>

				<section>
					<h3 class="font-semibold mb-1">Test a task</h3>
					<p class="mb-2">
						Phrase it the way you would ask an agent. Every ADR is listed with its score and what
						would happen to it:
					</p>
					<ul class="list-disc pl-5">
						<li><strong>Sent to agent</strong> — cleared the cutoff and made the top few</li>
						<li><strong>Below threshold</strong> — didn't score highly enough</li>
						<li>
							<strong>Over the cap</strong> — scored highly enough, but stronger ADRs filled every
							slot
						</li>
					</ul>
				</section>

				<section>
					<h3 class="font-semibold mb-1">Find the right cutoff</h3>
					<p>
						List tasks your ADRs cover and tasks they don't, one per line. The cutoff belongs
						between the lowest score on the left and the highest on the right. If they overlap,
						there is no number that works — something that should match scores at or below
						something that shouldn't, and that is a fact about your ADRs rather than a failed
						calculation.
					</p>
					<p class="mt-2">
						The right-hand tasks must be <strong>real coding tasks</strong>. An agent never asks for
						a cookie recipe, but it does ask for a CSV parser; off-topic text scores so low it
						suggests a cutoff that lets genuine junk through.
					</p>
				</section>

				<section>
					<h3 class="font-semibold mb-1">When something scores wrong, fix the ADR</h3>
					<p class="mb-2">This is what the page is really for. Two shapes of problem:</p>
					<p class="mb-2">
						<strong>A task your ADR covers scores low.</strong> The ADR is hard to find. Usually it
						is written in the vocabulary of its <em>solution</em> rather than the <em>problem</em>.
						A real example from the sample ADRs: one about async UI feedback scored 0.636 for
						"show a loading spinner during an async api call" but only 0.550 for "show a loading
						spinner while saving a form" — the same task. It named its own hook and said "async",
						but never "form" or "saving". Adding the words someone would actually type, to its
						Context or Scope, fixes it.
					</p>
					<p>
						<strong>A task no ADR covers scores high.</strong> Something incidental is attracting
						it, often vocabulary inside a code sample. One sample ADR about endpoint layering
						pulls in "sort a list of dicts by a key", because its example happens to contain
						<code>list[dict]</code>.
					</p>
				</section>

				<section>
					<h3 class="font-semibold mb-1">Moving the cutoff is the last resort</h3>
					<p>
						Raising it loses genuine matches; lowering it admits junk. When in doubt leave it lower:
						a spurious ADR is noise the agent can weigh against the task, while a missing one means
						it writes ungrounded code and nobody finds out.
					</p>
				</section>
			</div>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import {
	knowledgeBaseService,
	settingsService,
	type Calibration,
	type SearchCandidate,
	type SearchPreview,
	type Settings,
} from "@/api-service";
import { retrievalThresholdSchema } from "@/schemas/settingsSchema";
import useZodValidation from "@/composables/useZodValidation";
import axios from "axios";
import {
	Button,
	Column,
	DataTable,
	Dialog,
	InputNumber,
	InputText,
	Message,
	Slider,
	Tab,
	TabList,
	TabPanel,
	TabPanels,
	Tabs,
	Tag,
	Textarea,
	useToast,
} from "primevue";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const toast = useToast();
const router = useRouter();
const { validate, validationErrors } = useZodValidation(retrievalThresholdSchema);

const query = ref("");
const preview = ref<SearchPreview | null>(null);
const searching = ref(false);
const searchError = ref("");

const helpVisible = ref(false);

const genuineText = ref("");
const unrelatedText = ref("");
const calibration = ref<Calibration | null>(null);
const calibrating = ref(false);
const calibrateError = ref("");

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

// One task per line, blanks dropped, so trailing newlines and spacing while typing
// don't become empty queries the server has to reject.
const toLines = (text: string) =>
	text
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean);

const genuineLines = computed(() => toLines(genuineText.value));
const unrelatedLines = computed(() => toLines(unrelatedText.value));

// Each side is coloured by whether it landed where it should: a "should match" below the
// floor, or a "shouldn't" above the ceiling, is the one dragging the gap shut.
const calibrationGroups = computed(() => {
	const c = calibration.value;
	if (!c) return [];
	return [
		{
			label: "Should match your ADRs",
			rows: c.genuine,
			scoreClass: (score: number | null) =>
				score !== null && c.floor !== null && score <= c.floor ? "text-amber-600 font-semibold" : "text-slate-700",
		},
		{
			label: "Should match nothing",
			rows: c.unrelated,
			scoreClass: (score: number | null) =>
				score !== null && c.ceiling !== null && score >= c.ceiling ? "text-amber-600 font-semibold" : "text-slate-700",
		},
	];
});

// A new tab rather than navigation: the task and its scores are the reason for opening
// the ADR, and coming back would mean re-running the search to see them again.
const openRecord = (event: { data: SearchCandidate }) => {
	const { href } = router.resolve({ name: "KnowledgeBaseRecord", params: { id: event.data.source } });
	window.open(href, "_blank", "noopener");
};

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

const onCalibrate = async () => {
	calibrating.value = true;
	calibrateError.value = "";
	try {
		const { data } = await settingsService.calibrate(genuineLines.value, unrelatedLines.value);
		calibration.value = data;
	} catch (err) {
		calibration.value = null;
		calibrateError.value = message(err, "Could not work out a cutoff.");
	} finally {
		calibrating.value = false;
	}
};

// Loads the suggestion into the slider without saving it, so it is reviewed against the
// threshold card's controls rather than applied the moment it is calculated.
const useSuggestion = () => {
	if (calibration.value?.suggested_threshold !== null && calibration.value) {
		draftThreshold.value = calibration.value.suggested_threshold;
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
