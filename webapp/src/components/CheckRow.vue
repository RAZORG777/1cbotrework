<script setup lang="ts">
import { PhCheck } from '@phosphor-icons/vue'
import { useId } from 'vue'
const model = defineModel<boolean>({ required: true })
defineProps<{ error?: string }>()
const id = useId()
</script>

<template>
  <label :for="id" class="flex min-h-11 cursor-pointer items-start gap-3 py-1 text-base leading-snug">
    <input
      :id="id"
      v-model="model"
      type="checkbox"
      class="peer sr-only"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-e` : undefined"
    />
    <span
      class="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px] border-2 transition-colors peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--c-focus)]"
      :class="model ? 'border-accent bg-accent text-on-accent' : error ? 'border-danger bg-surface' : 'border-[#7f9491] bg-surface'"
      aria-hidden="true"
    >
      <PhCheck v-if="model" :size="16" weight="bold" />
    </span>
    <span class="flex flex-col gap-1">
      <span><slot /></span>
      <span v-if="error" :id="`${id}-e`" class="anim-fade text-[15px] text-danger">{{ error }}</span>
    </span>
  </label>
</template>
