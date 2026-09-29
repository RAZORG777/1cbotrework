<script setup lang="ts">
import { computed } from 'vue'
import Avatar from '@/components/Avatar.vue'
import ErrorState from '@/components/ErrorState.vue'
import ListRow from '@/components/ListRow.vue'
import SkeletonRows from '@/components/SkeletonRows.vue'
import StepProgress from '@/components/StepProgress.vue'
import { branchInfo } from '@/lib/branches'
import { formatPrice } from '@/lib/format'
import { groupServices, toItem, type ServiceItem } from '@/lib/services'
import { platform } from '@/platform'
import { back, booking, go } from '@/state/booking'
import { catalog } from '@/state/catalog'
import { useLoader } from './useLoader'

const doctor = computed(() => booking.doctor!)
const loader = useLoader(async () => (await catalog.services(doctor.value.id)).map(toItem))
loader.load()

const grouped = computed(() => groupServices(loader.data.value ?? []))
const groups = computed(() => [
  { title: 'Первичный приём', items: grouped.value.primary },
  { title: 'Повторный приём', items: grouped.value.repeat },
])

function pick(s: ServiceItem) {
  platform().haptic('select')
  booking.service = s
  go('time')
}
</script>

<template>
  <div class="flex flex-col gap-5 px-4 pb-6 pt-5">
    <StepProgress :step="2" label="Услуга" />

    <div class="flex items-center gap-3.5">
      <Avatar :name="doctor.full_name" :photo="doctor.photo_url" />
      <div class="flex min-w-0 flex-1 flex-col gap-0.5">
        <span class="text-[17px] font-semibold leading-tight">{{ doctor.full_name }}</span>
        <span class="text-[15px] text-muted">{{ doctor.specialty_name || 'Врач-офтальмолог' }} · {{ branchInfo(booking.branch).name }}</span>
      </div>
    </div>

    <h1 class="m-0 text-2xl font-bold tracking-[-0.01em]">Выбор услуги</h1>

    <SkeletonRows v-if="loader.loading.value" :rows="4" />
    <ErrorState v-else-if="loader.error.value" @retry="loader.load()" />
    <div v-else-if="!grouped.primary.length && !grouped.repeat.length" class="anim-fade flex flex-col items-center gap-3 py-6 text-center">
      <p class="m-0 text-base text-muted">У этого врача нет услуг для онлайн-записи.</p>
      <button type="button" class="h-11 text-[17px] font-semibold text-accent" @click="back()">Выбрать другого врача</button>
    </div>
    <template v-else>
      <section v-for="g in groups" v-show="g.items.length" :key="g.title" class="anim-fade flex flex-col gap-2.5">
        <h2 class="m-0 text-base font-semibold text-ink-2">{{ g.title }}</h2>
        <ul class="m-0 list-none overflow-hidden rounded-box border border-line bg-surface p-0">
          <li v-for="s in g.items" :key="s.id" class="border-b border-divider last:border-b-0">
            <ListRow :chevron="false" @click="pick(s)">
              <span class="text-[17px] leading-snug">{{ s.displayName }}</span>
              <template #trail>
                <span v-if="formatPrice(s.price)" class="whitespace-nowrap text-base font-semibold tabular-nums">{{ formatPrice(s.price) }}</span>
              </template>
            </ListRow>
          </li>
        </ul>
      </section>
      <p class="m-0 text-[15px] leading-snug text-muted">Итоговую стоимость врач уточнит на приёме, если понадобятся дополнительные исследования.</p>
    </template>
  </div>
</template>
