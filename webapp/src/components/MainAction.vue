<script setup lang="ts">
import { mainButton } from '@/state/ui'
import SendingDots from './SendingDots.vue'
</script>

<template>
  <!-- Своя главная кнопка там, где мессенджер её не даёт (MAX, браузер). -->
  <div v-if="mainButton" class="sticky bottom-0 z-10 border-t border-line bg-chrome px-4 pb-[max(20px,env(safe-area-inset-bottom))] pt-3">
    <button
      type="button"
      class="press flex h-[52px] w-full items-center justify-center rounded-box px-4 text-[17px] font-semibold"
      :class="
        !mainButton.state.enabled
          ? 'bg-disabled-bg text-disabled-ink'
          : mainButton.state.tone === 'danger'
            ? 'bg-danger-fill text-on-danger'
            : 'bg-accent text-on-accent'
      "
      :disabled="!mainButton.state.enabled || mainButton.state.loading"
      :aria-busy="mainButton.state.loading ? 'true' : undefined"
      @click="mainButton.onClick()"
    >
      <SendingDots v-if="mainButton.state.loading" />
      <span v-else class="truncate">{{ mainButton.state.text }}</span>
      <span v-if="mainButton.state.loading" class="sr-only">Отправляем</span>
    </button>
  </div>
</template>
