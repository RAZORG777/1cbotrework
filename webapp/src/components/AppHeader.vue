<script setup lang="ts">
import { PhCaretLeft } from '@phosphor-icons/vue'
defineProps<{ canBack: boolean }>()
defineEmits<{ back: [] }>()
</script>

<template>
  <!-- Своя шапка с «Назад», если мессенджер не даёт свою кнопку. -->
  <header class="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-chrome px-2 pt-[env(safe-area-inset-top)]">
    <button
      v-if="canBack"
      type="button"
      class="press flex h-11 items-center gap-0.5 rounded-[10px] px-2 text-[17px] text-accent"
      @click="$emit('back')"
    >
      <PhCaretLeft :size="22" weight="bold" aria-hidden="true" />Назад
    </button>
    <span v-else class="w-11" />
    <span class="text-[17px] font-semibold">Ясно Вижу</span>
    <span class="w-11" />
  </header>
</template>
