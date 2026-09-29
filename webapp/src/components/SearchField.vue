<script setup lang="ts">
import { PhMagnifyingGlass, PhX } from '@phosphor-icons/vue'
const model = defineModel<string>({ required: true })
defineProps<{ label: string; placeholder: string }>()
</script>

<template>
  <div class="flex h-[52px] items-center gap-2.5 rounded-box border border-line-strong bg-surface pl-3.5 pr-1 focus-within:border-2 focus-within:border-accent focus-within:pl-[13px]">
    <PhMagnifyingGlass :size="22" class="shrink-0 text-muted" aria-hidden="true" />
    <input
      v-model="model"
      type="search"
      :aria-label="label"
      :placeholder="placeholder"
      enterkeyhint="search"
      autocomplete="off"
      class="min-w-0 flex-1 bg-transparent text-[17px] outline-none placeholder:text-muted"
    />
    <button
      v-if="model"
      type="button"
      aria-label="Очистить поиск"
      class="flex h-11 w-11 items-center justify-center text-muted"
      @click="model = ''"
    >
      <PhX :size="20" />
    </button>
  </div>
</template>
