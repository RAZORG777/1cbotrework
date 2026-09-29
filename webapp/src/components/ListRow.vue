<script setup lang="ts">
import { PhCaretRight } from '@phosphor-icons/vue'
defineProps<{ chevron?: boolean }>()
defineEmits<{ click: [] }>()
</script>

<template>
  <button
    type="button"
    class="press flex min-h-[60px] w-full items-center gap-3.5 px-4 py-3 text-left hover:bg-accent-tint/50 active:bg-accent-tint"
    @click="$emit('click')"
  >
    <slot name="lead" />
    <span class="flex min-w-0 flex-1 flex-col gap-0.5">
      <slot />
    </span>
    <slot name="trail" />
    <PhCaretRight v-if="chevron !== false" :size="22" class="shrink-0 text-muted" aria-hidden="true" />
  </button>
</template>
