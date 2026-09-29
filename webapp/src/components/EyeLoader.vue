<script setup lang="ts">
defineProps<{ text: string }>()
</script>

<template>
  <div class="flex items-center gap-3.5">
    <span class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent-tint text-accent" aria-hidden="true">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        <g class="eye-lid">
          <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
          <circle class="eye-pupil" cx="12" cy="12" r="3" />
        </g>
      </svg>
    </span>
    <p role="status" class="m-0 text-[17px] text-ink-2">{{ text }}</p>
  </div>
</template>
