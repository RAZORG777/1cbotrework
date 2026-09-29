<script setup lang="ts">
defineProps<{ step: number; label: string }>()
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex justify-between text-[15px] text-muted">
      <span>Шаг {{ step }} из 4</span>
      <span class="font-semibold text-ink">{{ label }}</span>
    </div>
    <div
      class="grid grid-cols-4 gap-1.5"
      role="progressbar"
      :aria-valuenow="step"
      aria-valuemin="1"
      aria-valuemax="4"
      :aria-label="`Шаг ${step} из 4`"
    >
      <div v-for="i in 4" :key="i" class="h-1 overflow-hidden rounded-sm bg-track">
        <div v-if="i < step" class="h-full bg-accent" />
        <div v-else-if="i === step" class="anim-fill h-full bg-accent" />
      </div>
    </div>
  </div>
</template>
