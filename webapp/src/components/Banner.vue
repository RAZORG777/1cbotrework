<script setup lang="ts">
import { PhCheck, PhWarningCircle } from '@phosphor-icons/vue'
defineProps<{ tone: 'danger' | 'success'; title: string }>()
</script>

<template>
  <div
    :role="tone === 'danger' ? 'alert' : 'status'"
    class="anim-drop flex items-start gap-3 rounded-box border px-4 py-3.5"
    :class="tone === 'danger' ? 'border-danger-line bg-danger-tint' : 'border-accent-tint-line bg-accent-tint'"
  >
    <PhWarningCircle v-if="tone === 'danger'" :size="24" class="shrink-0 text-danger" aria-hidden="true" />
    <span v-else class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent" aria-hidden="true">
      <PhCheck :size="18" weight="bold" />
    </span>
    <div class="flex flex-col gap-1">
      <span class="text-[17px] font-semibold" :class="tone === 'danger' ? 'text-danger-ink' : 'text-ink'">{{ title }}</span>
      <span v-if="$slots.default" class="text-base leading-snug" :class="tone === 'danger' ? 'text-danger-soft' : 'text-ink-2'"><slot /></span>
    </div>
  </div>
</template>
