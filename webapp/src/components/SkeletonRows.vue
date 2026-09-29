<script setup lang="ts">
defineProps<{ rows?: number; avatar?: boolean }>()
</script>

<template>
  <div class="overflow-hidden rounded-box border border-line bg-surface" aria-hidden="true">
    <div v-for="i in rows ?? 5" :key="i" class="flex items-center gap-3.5 border-b border-divider px-4 py-3.5 last:border-b-0">
      <div v-if="avatar" class="skeleton h-[52px] w-[52px] shrink-0 rounded-full" />
      <div class="flex flex-1 flex-col gap-2">
        <div class="skeleton h-4 rounded-md" :style="{ width: `${60 + ((i * 13) % 30)}%` }" />
        <div class="skeleton h-3.5 w-2/5 rounded-md" />
      </div>
    </div>
  </div>
</template>
