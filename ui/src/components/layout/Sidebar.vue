<template>
	<aside
		class="fixed left-0 top-0 h-screen bg-slate-50 overflow-y-auto shadow transition-all duration-300"
		:class="collapsed ? 'w-16' : 'w-64'"
	>
		<div
			class="flex items-center h-[72px] border-b border-slate-200"
			:class="collapsed ? 'justify-center px-2' : 'justify-between px-5'"
		>
			<h1 v-if="!collapsed" class="m-0 text-2xl font-semibold whitespace-nowrap">Adra</h1>
			<button
				class="flex items-center justify-center w-9 h-9 rounded-md text-slate-600 hover:bg-slate-200 transition-colors shrink-0 cursor-pointer"
				:aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
				@click="toggle"
			>
				<Icon :icon="collapsed ? 'mdi:menu' : 'mdi:chevron-left'" width="20" height="20" />
			</button>
		</div>
		<nav class="py-5">
			<ul class="list-none p-0 m-0">
				<li>
					<router-link
						v-tooltip.right="collapsed ? 'Knowledge Base' : ''"
						:to="ROUTES.default"
						class="flex items-center gap-3 py-3 no-underline hover:bg-slate-100 transition-colors duration-300"
						:class="collapsed ? 'justify-center px-0' : 'px-5'"
						active-class="bg-slate-200 text-slate-900 font-semibold"
					>
						<Icon icon="mdi:book-open-variant" width="20" height="20" class="shrink-0" />
						<span v-if="!collapsed" class="whitespace-nowrap">Knowledge Base</span>
					</router-link>
				</li>
			</ul>
		</nav>
	</aside>
</template>

<script setup lang="ts">
import ROUTES from "@/router/routes";
import { Icon } from "@iconify/vue";
import { useSidebar } from "@/composables/useSidebar";

const { collapsed, toggle } = useSidebar();
</script>
