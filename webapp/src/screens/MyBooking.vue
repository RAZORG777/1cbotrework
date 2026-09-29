<script setup lang="ts">
import { PhArrowsClockwise, PhCheck } from '@phosphor-icons/vue'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import Banner from '@/components/Banner.vue'
import SendingDots from '@/components/SendingDots.vue'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import { branchInfo } from '@/lib/branches'
import { CLINIC_PHONE, CLINIC_PHONE_HREF, classify, GENERAL_MESSAGE } from '@/lib/errors'
import { shortDate } from '@/lib/format'
import { toItem } from '@/lib/services'
import { platform } from '@/platform'
import { booking, go, resetDraft, root } from '@/state/booking'
import { onAccessError, refreshActive } from '@/state/session'

type Phase = 'view' | 'ask' | 'sending' | 'done'
const phase = ref<Phase>('view')
const error = ref('')
const loading = ref(!booking.active)
const cancelled = ref<typeof booking.active>(null)

const a = computed(() => (phase.value === 'done' ? cancelled.value : booking.active))
const branch = computed(() => branchInfo(a.value?.branch ?? ''))

refreshActive()
  .catch((e) => {
    const kind = classify(e)
    if (kind === 'access' || kind === 'expired') onAccessError(kind)
  })
  .finally(() => (loading.value = false))

function reschedule() {
  const act = booking.active
  if (!act) return
  platform().haptic('select')
  resetDraft()
  booking.mode = 'reschedule'
  booking.branch = branchInfo(act.branch).id
  if (act.doctor_id && act.service_id) {
    booking.doctor = { id: act.doctor_id, full_name: act.doctor_name }
    booking.service = toItem({ id: act.service_id, name: act.service_name })
    go('time')
  } else {
    booking.path = 'doctor'
    go('choose')
  }
}

function ask() {
  platform().haptic('select')
  error.value = ''
  phase.value = 'ask'
}

async function confirmCancel() {
  if (phase.value !== 'ask') return
  phase.value = 'sending'
  error.value = ''
  const snapshot = booking.active
  try {
    await api.cancel()
    platform().haptic('success')
    cancelled.value = snapshot
    booking.active = null
    phase.value = 'done'
  } catch (e) {
    platform().haptic('error')
    const kind = classify(e)
    if (kind === 'access' || kind === 'expired') return onAccessError(kind)
    if (kind === 'not_found') {
      await refreshActive().catch(() => false)
      phase.value = 'view'
      return
    }
    error.value = GENERAL_MESSAGE
    phase.value = 'ask'
  }
}

function bookAgain() {
  resetDraft()
  root('home')
}
</script>

<template>
  <div class="flex min-h-full flex-col gap-5 px-4 pb-6 pt-6">
    <h1 class="m-0 text-[27px] font-bold tracking-[-0.01em]">Моя запись</h1>

    <div v-if="loading" class="overflow-hidden rounded-box border border-line bg-surface" aria-hidden="true">
      <div class="skeleton h-[98px]" />
      <div class="flex flex-col gap-3 p-4">
        <div class="skeleton h-4 w-3/4 rounded-md" />
        <div class="skeleton h-4 w-1/2 rounded-md" />
        <div class="skeleton h-4 w-2/3 rounded-md" />
      </div>
    </div>

    <div v-else-if="!a" class="anim-fade flex flex-col items-center gap-3.5 py-8 text-center">
      <p class="m-0 text-[19px] font-semibold">Активной записи нет</p>
      <p class="m-0 max-w-[300px] text-base text-muted">Прошедшие и отменённые визиты здесь не показываются.</p>
      <button type="button" class="press h-[52px] w-full rounded-box bg-accent text-[17px] font-semibold text-on-accent" @click="bookAgain">Записаться</button>
    </div>

    <template v-else>
      <div class="anim-fade overflow-hidden rounded-box border border-line bg-surface transition-opacity duration-300" :class="{ 'opacity-55': phase === 'done' }">
        <div class="flex flex-col gap-2.5 px-4 py-[18px] transition-colors duration-300" :class="phase === 'done' ? 'bg-pill' : 'bg-accent-tint'">
          <div class="flex items-baseline justify-between gap-3">
            <span class="text-[44px] font-bold leading-none tracking-[-0.02em] tabular-nums">{{ a.time }}</span>
            <span class="text-[17px] font-semibold">{{ shortDate(a.date) }}</span>
          </div>
          <span
            v-if="a.confirmed && phase !== 'done'"
            class="flex h-[30px] items-center gap-1.5 self-start rounded-full bg-surface pl-2 pr-3 text-sm font-semibold text-accent"
          >
            <PhCheck :size="16" weight="bold" aria-hidden="true" />Вы подтвердили визит
          </span>
        </div>
        <dl class="m-0 flex flex-col px-4 py-1">
          <div class="flex flex-col gap-0.5 border-b border-divider py-3">
            <dt class="text-sm text-muted">Врач</dt>
            <dd class="m-0 text-[17px] font-medium">{{ a.doctor_name }}</dd>
          </div>
          <div v-if="a.service_name" class="flex flex-col gap-0.5 border-b border-divider py-3">
            <dt class="text-sm text-muted">Услуга</dt>
            <dd class="m-0 text-[17px] font-medium">{{ a.service_name }}</dd>
          </div>
          <div class="flex flex-col gap-0.5 py-3">
            <dt class="text-sm text-muted">Филиал</dt>
            <dd class="m-0 text-[17px] font-medium">{{ branch.name }}, {{ branch.address }}</dd>
            <dd class="m-0">
              <a :href="branch.phoneHref" class="inline-flex min-h-11 items-center text-base font-medium no-underline tabular-nums">{{ branch.phone }}</a>
            </dd>
          </div>
        </dl>
      </div>

      <span v-if="phase === 'done'" class="anim-fade flex h-8 items-center self-start rounded-full border border-line bg-pill px-3 text-[15px] font-semibold text-ink-2" role="status">
        Запись отменена
      </span>

      <div class="flex-1" />

      <div v-if="phase === 'view'" class="anim-fade flex flex-col gap-2">
        <button type="button" class="press flex h-[52px] items-center justify-center gap-2.5 rounded-box border border-accent text-[17px] font-semibold text-accent" @click="reschedule">
          <PhArrowsClockwise :size="22" aria-hidden="true" />Перенести на другое время
        </button>
        <button type="button" class="press h-12 rounded-box text-[17px] font-semibold text-danger" @click="ask">Отменить запись</button>
      </div>

      <section
        v-else-if="phase === 'ask' || phase === 'sending'"
        aria-labelledby="cancel-q"
        class="anim-rise flex flex-col gap-3.5 rounded-box border border-danger-line bg-danger-tint px-4 py-[18px]"
      >
        <h2 id="cancel-q" class="m-0 text-[19px] font-semibold leading-snug">Отменить запись на {{ shortDate(a.date) }}, {{ a.time }}?</h2>
        <p class="m-0 text-base leading-snug text-danger-soft">Время освободится для другого пациента. Записаться снова можно в любой момент.</p>
        <Banner v-if="error" tone="danger" title="Не удалось отменить">
          {{ error }} <a :href="CLINIC_PHONE_HREF" class="font-semibold no-underline">{{ CLINIC_PHONE }}</a>
        </Banner>
        <div class="flex flex-col gap-2">
          <button
            type="button"
            class="press flex h-[52px] items-center justify-center rounded-box bg-danger-fill text-[17px] font-semibold text-on-danger"
            :aria-busy="phase === 'sending' ? 'true' : undefined"
            :disabled="phase === 'sending'"
            @click="confirmCancel"
          >
            <SendingDots v-if="phase === 'sending'" />
            <span v-else>Да, отменить</span>
            <span v-if="phase === 'sending'" class="sr-only">Отменяем запись</span>
          </button>
          <button
            type="button"
            class="press h-[52px] rounded-box border border-line-strong bg-surface text-[17px] font-semibold"
            :disabled="phase === 'sending'"
            @click="phase = 'view'"
          >
            Оставить запись
          </button>
        </div>
      </section>

      <div v-else class="flex flex-col gap-3">
        <p class="anim-rise m-0 text-base leading-snug text-ink-2">Время освободилось. Записаться снова можно в любой момент.</p>
        <button type="button" class="press anim-rise delay-2 h-[52px] rounded-box bg-accent text-[17px] font-semibold text-on-accent" @click="bookAgain">Записаться снова</button>
      </div>
    </template>

    <div class="mt-3 border-t border-line pt-4">
      <ThemeSwitch />
    </div>
  </div>
</template>
