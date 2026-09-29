<script setup lang="ts">
import { PhBell } from '@phosphor-icons/vue'
import { computed } from 'vue'
import { branchInfo } from '@/lib/branches'
import { longDate, shortDate } from '@/lib/format'
import { platform } from '@/platform'
import { booking, resetDraft, root } from '@/state/booking'
import { useMainButton } from '@/state/ui'

const r = computed(() => booking.result!)
const branch = computed(() => branchInfo(r.value.branch))

function openMy() {
  resetDraft()
  root('my')
}

useMainButton(computed(() => ({ text: 'Готово', enabled: true, loading: false })), () => platform().close())
</script>

<template>
  <div class="success flex min-h-full flex-col gap-6 px-4 pb-6 pt-8">
    <div class="flex flex-col items-start gap-4">
      <span class="anim-pop flex h-16 w-16 items-center justify-center rounded-full bg-accent text-on-accent" aria-hidden="true">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path class="anim-draw" d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      </span>
      <h1 class="anim-rise delay-1 m-0 text-[30px] font-bold leading-[1.1] tracking-[-0.015em]">
        {{ r.rescheduled ? 'Запись перенесена' : 'Вы записаны' }}
      </h1>
      <p class="anim-rise delay-2 m-0 text-lg text-ink-2">Ждём вас {{ longDate(r.date) }}</p>
    </div>

    <div class="anim-rise delay-3 overflow-hidden rounded-box border border-line bg-surface">
      <div class="flex items-baseline justify-between gap-3 bg-accent-tint px-4 py-[18px]">
        <span class="text-[44px] font-bold leading-none tracking-[-0.02em] tabular-nums">{{ r.time }}</span>
        <span class="text-[17px] font-semibold">{{ shortDate(r.date) }}</span>
      </div>
      <dl class="m-0 flex flex-col px-4 py-1">
        <div class="flex flex-col gap-0.5 border-b border-divider py-3">
          <dt class="text-sm text-muted">Врач</dt>
          <dd class="m-0 text-[17px] font-medium">{{ r.doctorName }}</dd>
        </div>
        <div class="flex flex-col gap-0.5 border-b border-divider py-3">
          <dt class="text-sm text-muted">Услуга</dt>
          <dd class="m-0 text-[17px] font-medium">{{ r.serviceName }}</dd>
        </div>
        <div class="flex flex-col gap-0.5 py-3" :class="{ 'border-b border-divider': r.patientName }">
          <dt class="text-sm text-muted">Филиал</dt>
          <dd class="m-0 text-[17px] font-medium">{{ branch.name }}, {{ branch.address }}</dd>
          <dd class="m-0"><a :href="branch.phoneHref" class="inline-flex min-h-11 items-center text-base font-medium no-underline tabular-nums">{{ branch.phone }}</a></dd>
        </div>
        <div v-if="r.patientName" class="flex flex-col gap-0.5 py-3">
          <dt class="text-sm text-muted">Пациент</dt>
          <dd class="m-0 text-[17px] font-medium">{{ r.patientName }}</dd>
        </div>
      </dl>
    </div>

    <div class="anim-rise delay-4 flex items-start gap-3">
      <PhBell :size="24" class="shrink-0 text-accent" aria-hidden="true" />
      <p class="m-0 text-base leading-snug text-ink-2">Напомним в этом чате накануне и за 2 часа. Подтвердить или отменить визит можно прямо в сообщении.</p>
    </div>

    <div class="flex-1" />
    <button type="button" class="anim-rise delay-5 flex h-12 items-center justify-center text-[17px] font-semibold text-accent" @click="openMy">
      Открыть «Мою запись»
    </button>
  </div>
</template>
