<script setup lang="ts">
import { ref } from 'vue'
import { initials } from '@/lib/format'
defineProps<{ name: string; photo?: string; size?: number }>()
const failed = ref(false)
</script>

<template>
  <span
    class="flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent-tint font-semibold text-accent"
    :style="{ width: `${size ?? 52}px`, height: `${size ?? 52}px`, fontSize: `${Math.round((size ?? 52) * 0.34)}px` }"
    aria-hidden="true"
  >
    <img
      v-if="photo && !failed"
      :src="photo"
      alt=""
      loading="lazy"
      referrerpolicy="no-referrer"
      class="h-full w-full object-cover"
      @error="failed = true"
    />
    <template v-else>{{ initials(name) }}</template>
  </span>
</template>
