<template>
	<div class="flex h-screen w-full">
		<Sidebar />
		<!-- transition-[margin-left], not transition-all: only the margin animates when the
		     sidebar collapses, and transition-all makes Safari promote this to its own
		     compositing layer, which then paints above body-appended overlays such as the
		     Create ADR menu however high their z-index. -->
		<main
			class="flex-1 overflow-y-auto bg-slate-100 transition-[margin-left] duration-300"
			:class="collapsed ? 'ml-16' : 'ml-64'"
		>
			<div class="p-5 w-full">
				<router-view />
			</div>
		</main>
	</div>
</template>

<script setup lang="ts">
import Sidebar from "./Sidebar.vue";
import { useSidebar } from "@/composables/useSidebar";

const { collapsed } = useSidebar();
</script>
