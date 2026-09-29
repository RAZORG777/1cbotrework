<script setup lang="ts">
import { computed } from 'vue'
import Avatar from '@/components/Avatar.vue'
import ListRow from '@/components/ListRow.vue'
import StepProgress from '@/components/StepProgress.vue'
import type { Doctor } from '@/api/types'
import { formatPrice } from '@/lib/format'
import { platform } from '@/platform'
import { back, booking, go } from '@/state/booking'

const service = computed(() => booking.service!)
const doctors = computed(() => service.value.doctors ?? [])

function pick(d: Doctor) {
  platform().haptic('select')
  booking.doctor = d
  go('time')
}
</script>

<template>
  <div class="flex flex-col gap-5 px-4 pb-6 pt-5">
    <StepProgress :step="2" label="Врач" />

    <div class="flex items-center justify-between gap-3">
      <div class="flex min-w-0 flex-col gap-0.5">
        <span class="text-[15px] text-muted">Услуга</span>
        <span class="text-[17px] font-semibold leading-snug">{{ service.displayName }}</span>
        <span v-if="formatPrice(service.price)" class="text-[15px] tabular-nums text-muted">{{ formatPrice(service.price) }}</span>
      </div>
      <button type="button" class="flex h-11 shrink-0 items-center px-1 text-base font-medium text-accent" @click="back()">Изменить</button>
    </div>

    <h1 class="m-0 text-2xl font-bold tracking-[-0.01em]">Кто примет?</h1>

    <p v-if="!doctors.length" class="m-0 py-6 text-center text-base text-muted">Нет врачей, которые оказывают эту услугу онлайн.</p>
    <ul v-else class="anim-fade m-0 list-none overflow-hidden rounded-box border border-line bg-surface p-0">
      <li v-for="d in doctors" :key="d.id" class="border-b border-divider last:border-b-0">
        <ListRow @click="pick(d)">
          <template #lead><Avatar :name="d.full_name" :photo="d.photo_url" /></template>
          <span class="text-[17px] font-semibold leading-tight">{{ d.full_name }}</span>
          <span v-if="d.description || d.specialty_name" class="text-[15px] leading-snug text-muted">{{ d.description || d.specialty_name }}</span>
        </ListRow>
      </li>
    </ul>
  </div>
</template>
