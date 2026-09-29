<script setup lang="ts" generic="T extends string">
const model = defineModel<T>({ required: true })
defineProps<{ options: { value: T; label: string }[]; label: string }>()
</script>

<template>
  <div role="tablist" :aria-label="label" class="grid grid-cols-2 gap-1 rounded-box bg-segment p-1">
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      role="tab"
      :aria-selected="model === o.value"
      class="press h-11 rounded-[11px] text-base"
      :class="model === o.value ? 'bg-surface font-semibold text-ink shadow-[0_1px_2px_rgb(15_46_42/0.12)] ring-1 ring-line-strong' : 'font-medium text-ink-2'"
      @click="model = o.value"
    >
      {{ o.label }}
    </button>
  </div>
</template>
