<script setup lang="ts">
import { PhWarningCircle } from '@phosphor-icons/vue'
import { CLINIC_PHONE, CLINIC_PHONE_HREF, GENERAL_MESSAGE } from '@/lib/errors'
defineProps<{ message?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div role="alert" class="anim-fade flex flex-col items-center gap-3.5 px-2 py-6 text-center">
    <span class="flex h-14 w-14 items-center justify-center rounded-full bg-danger-tint text-danger" aria-hidden="true">
      <PhWarningCircle :size="28" />
    </span>
    <p class="m-0 max-w-[300px] text-base leading-snug text-ink-2">{{ message ?? GENERAL_MESSAGE }}</p>
    <button type="button" class="press h-12 rounded-box border border-accent px-6 text-[17px] font-semibold text-accent" @click="$emit('retry')">
      Повторить
    </button>
    <a :href="CLINIC_PHONE_HREF" class="flex h-11 items-center text-base font-semibold no-underline tabular-nums">{{ CLINIC_PHONE }}</a>
  </div>
</template>
