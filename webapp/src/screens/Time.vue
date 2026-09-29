<script setup lang="ts">
import { PhCalendarBlank, PhCaretLeft, PhCaretRight } from '@phosphor-icons/vue'
import { computed, ref, watch } from 'vue'
import { api } from '@/api/client'
import Banner from '@/components/Banner.vue'
import ErrorState from '@/components/ErrorState.vue'
import EyeLoader from '@/components/EyeLoader.vue'
import StepProgress from '@/components/StepProgress.vue'
import { CLINIC_PHONE, CLINIC_PHONE_HREF, classify, GENERAL_MESSAGE } from '@/lib/errors'
import { dayNum, monthsLabel, shortDate, shortName, weekdayShort } from '@/lib/format'
import {
  buildDays,
  firstPageWithSlots,
  groupByPart,
  hasAnySlots,
  nextFreeAfter,
  pageCount,
  PAGE_SIZE,
  pageOf,
  startEnd,
} from '@/lib/schedule'
import { platform } from '@/platform'
import { back, backTo, booking, go, root, slotKey } from '@/state/booking'
import { onAccessError, refreshActive } from '@/state/session'
import { useMainButton } from '@/state/ui'
import { useLoader } from './useLoader'

const doctor = computed(() => booking.doctor!)
const service = computed(() => booking.service!)
const rescheduling = computed(() => booking.mode === 'reschedule')

const today = new Date()
const loader = useLoader(async () => {
  const { start, end } = startEnd(today)
  const r = await api.schedule(doctor.value.id, booking.branch, start, end)
  return buildDays(r.schedule, today, new Date())
})

const days = computed(() => loader.data.value ?? [])
const page = ref(0)
const visible = computed(() => pageOf(days.value, page.value))
const pages = computed(() => pageCount(days.value))
const selectedDay = computed(() => days.value.find((d) => d.date === booking.date) ?? null)
const taken = (date: string, time: string) => booking.takenSlots.includes(slotKey(date, time))
const groups = computed(() => (selectedDay.value ? groupByPart(selectedDay.value.slots) : []))
const pageEmpty = computed(() => visible.value.every((d) => d.slots.length === 0))
const nearest = computed(() => (pageEmpty.value ? nextFreeAfter(days.value, page.value) : null))
const justTaken = ref('')

function selectFirstOnPage() {
  const first = visible.value.find((d) => d.slots.some((s) => !taken(d.date, s)))
  if (first && !visible.value.some((d) => d.date === booking.date)) booking.date = first.date
}

watch(
  () => loader.data.value,
  (v) => {
    if (!v) return
    const keep = v.findIndex((d) => d.date === booking.date && d.slots.length)
    page.value = keep >= 0 ? Math.floor(keep / PAGE_SIZE) : firstPageWithSlots(v)
    if (keep < 0) {
      booking.date = ''
      booking.time = ''
    }
    selectFirstOnPage()
  },
)
loader.load()

// «Время заняли» с шага «Пациент»: кольцо у занятого слота один раз.
if (booking.slotTakenNotice) justTaken.value = booking.slotTakenNotice

function turn(delta: number) {
  const next = Math.min(Math.max(page.value + delta, 0), pages.value - 1)
  if (next === page.value) return
  platform().haptic('select')
  page.value = next
  booking.date = ''
  booking.time = ''
  selectFirstOnPage()
}

function pickDate(date: string) {
  platform().haptic('select')
  if (booking.date !== date) booking.time = ''
  booking.date = date
}

function pickTime(time: string) {
  platform().haptic('select')
  booking.time = time
  booking.slotTakenNotice = ''
  sendError.value = ''
}

function jumpTo(date: string) {
  const idx = days.value.findIndex((d) => d.date === date)
  if (idx < 0) return
  page.value = Math.floor(idx / PAGE_SIZE)
  pickDate(date)
}

function otherDoctor() {
  if (booking.stack.includes('choose')) backTo('choose')
  else {
    booking.path = 'doctor'
    go('choose')
  }
}

function change() {
  if (rescheduling.value && !booking.stack.includes('choose')) {
    booking.path = 'doctor'
    go('choose')
  } else back()
}

// --- Главная кнопка: «Далее» или «Перенести на …» ---
const sending = ref(false)
const sendError = ref('')
const chosen = computed(() => !!booking.date && !!booking.time && !taken(booking.date, booking.time))

const mainState = computed(() => {
  if (loader.loading.value || loader.error.value || !hasAnySlots(days.value)) return null
  if (!chosen.value) return { text: 'Выберите время', enabled: false, loading: false }
  const when = `${shortDate(booking.date)}, ${booking.time}`
  return { text: rescheduling.value ? `Перенести на ${when}` : `Далее · ${when}`, enabled: true, loading: sending.value }
})

async function onMain() {
  if (!chosen.value || sending.value) return
  if (!rescheduling.value) {
    go('patient')
    return
  }
  const active = booking.active!
  sending.value = true
  sendError.value = ''
  try {
    const r = await api.reschedule({
      branch: booking.branch,
      doctor_id: doctor.value.id,
      doctor_name: doctor.value.full_name,
      service_id: service.value.id,
      service_name: service.value.name,
      date: booking.date,
      time: booking.time,
      send_notifications: true,
      pd_consent: false,
      old_appointment_id: active.appointment_id,
    })
    platform().haptic('success')
    booking.result = {
      date: booking.date,
      time: booking.time,
      doctorName: doctor.value.full_name,
      serviceName: service.value.displayName,
      branch: booking.branch,
      patientName: '',
      rescheduled: true,
    }
    booking.active = { ...active, appointment_id: r.appointment_id || active.appointment_id }
    root('success')
  } catch (e) {
    platform().haptic('error')
    const kind = classify(e)
    if (kind === 'slot_taken') {
      booking.takenSlots.push(slotKey(booking.date, booking.time))
      booking.slotTakenNotice = booking.time
      justTaken.value = booking.time
      booking.time = ''
    } else if (kind === 'access' || kind === 'expired') onAccessError(kind)
    else if (kind === 'not_found') {
      const has = await refreshActive().catch(() => false)
      root(has ? 'my' : 'home', 'back')
    } else sendError.value = GENERAL_MESSAGE
  } finally {
    sending.value = false
  }
}

useMainButton(mainState, onMain)
</script>

<template>
  <div class="flex flex-col gap-5 px-4 pb-6 pt-5">
    <Banner v-if="booking.slotTakenNotice" tone="danger" :title="`Время ${booking.slotTakenNotice} только что заняли`">
      {{ rescheduling ? 'Выберите другое время.' : 'Выберите другое, данные пациента сохранятся.' }}
    </Banner>
    <Banner v-if="sendError" tone="danger" title="Не удалось перенести запись">
      {{ sendError }} <a :href="CLINIC_PHONE_HREF" class="font-semibold no-underline">{{ CLINIC_PHONE }}</a>
    </Banner>

    <StepProgress v-if="!rescheduling" :step="3" label="Дата и время" />
    <h1 v-else class="m-0 text-2xl font-bold tracking-[-0.01em]">Перенос записи</h1>

    <div class="flex items-center gap-3 border-b border-line pb-4">
      <div class="flex min-w-0 flex-1 flex-col gap-0.5">
        <span class="text-[17px] font-semibold">{{ shortName(doctor.full_name) }}</span>
        <span class="text-[15px] leading-snug text-muted">{{ service.displayName }}</span>
      </div>
      <button type="button" class="flex h-11 shrink-0 items-center px-1 text-base font-medium text-accent" @click="change">Изменить</button>
    </div>

    <template v-if="loader.loading.value">
      <EyeLoader text="Ищем свободное время…" />
      <div class="grid grid-cols-6 gap-1 min-[360px]:gap-1.5" aria-hidden="true">
        <div v-for="i in 6" :key="i" class="skeleton h-[68px] rounded-chip" />
      </div>
      <div class="skeleton h-4 w-16 rounded-lg" aria-hidden="true" />
      <div class="grid grid-cols-4 gap-2" aria-hidden="true">
        <div v-for="i in 7" :key="i" class="skeleton h-12 rounded-chip" />
      </div>
    </template>

    <ErrorState v-else-if="loader.error.value" @retry="loader.load()" />

    <div v-else-if="!hasAnySlots(days)" class="anim-fade flex flex-col items-center gap-3.5 px-2 pt-6 text-center">
      <span class="flex h-14 w-14 items-center justify-center rounded-full bg-accent-tint text-accent" aria-hidden="true">
        <PhCalendarBlank :size="28" />
      </span>
      <h2 class="m-0 text-[21px] font-semibold leading-snug">В ближайший месяц мест нет</h2>
      <p class="m-0 max-w-[300px] text-base leading-snug text-muted">Выберите другого врача или позвоните, администратор подскажет ближайшую дату.</p>
      <button type="button" class="press h-[52px] w-full rounded-box border border-accent text-[17px] font-semibold text-accent" @click="otherDoctor">Выбрать другого врача</button>
      <a :href="CLINIC_PHONE_HREF" class="flex h-11 items-center text-[17px] font-semibold no-underline tabular-nums">{{ CLINIC_PHONE }}</a>
    </div>

    <template v-else>
      <div class="flex items-center justify-between">
        <h2 class="m-0 text-xl font-semibold">{{ monthsLabel(visible.map((d) => d.date)) }}</h2>
        <div class="flex gap-1">
          <button
            type="button"
            aria-label="Раньше"
            class="press flex h-11 w-11 items-center justify-center rounded-chip border"
            :class="page === 0 ? 'border-line text-faint' : 'border-line-strong bg-surface'"
            :disabled="page === 0"
            @click="turn(-1)"
          >
            <PhCaretLeft :size="20" weight="bold" />
          </button>
          <button
            type="button"
            aria-label="Позже"
            class="press flex h-11 w-11 items-center justify-center rounded-chip border"
            :class="page >= pages - 1 ? 'border-line text-faint' : 'border-line-strong bg-surface'"
            :disabled="page >= pages - 1"
            @click="turn(1)"
          >
            <PhCaretRight :size="20" weight="bold" />
          </button>
        </div>
      </div>

      <div class="grid grid-cols-6 gap-1 min-[360px]:gap-1.5">
        <button
          v-for="d in visible"
          :key="d.date"
          type="button"
          class="press flex h-[68px] flex-col items-center justify-center gap-1 rounded-chip border"
          :class="
            !d.slots.length
              ? 'border-dashed border-track text-faint'
              : d.date === booking.date
                ? 'border-accent bg-accent text-on-accent'
                : 'border-line-strong bg-surface'
          "
          :disabled="!d.slots.length"
          :aria-pressed="d.date === booking.date"
          :aria-label="`${shortDate(d.date)}${d.slots.length ? '' : ', мест нет'}`"
          @click="pickDate(d.date)"
        >
          <span class="text-sm" :class="d.date === booking.date ? 'text-accent-soft' : d.slots.length ? 'text-muted' : ''">{{ weekdayShort(d.date) }}</span>
          <span class="text-xl tabular-nums" :class="d.slots.length ? 'font-semibold' : 'font-medium'">{{ dayNum(d.date) }}</span>
        </button>
      </div>

      <div v-if="pageEmpty" class="anim-fade flex flex-col items-center gap-3.5 px-2 pt-4 text-center">
        <h2 class="m-0 text-[21px] font-semibold leading-snug">На этой неделе мест нет</h2>
        <p class="m-0 max-w-[300px] text-base leading-snug text-muted">У врача есть свободное время позже. Можно выбрать ближайшую дату или другого специалиста.</p>
        <button
          v-if="nearest"
          type="button"
          class="press h-[52px] w-full rounded-box border border-accent bg-surface text-[17px] font-semibold text-accent"
          @click="jumpTo(nearest.date)"
        >
          Ближайшее: {{ shortDate(nearest.date) }}
        </button>
        <button type="button" class="h-12 text-[17px] font-medium text-accent" @click="otherDoctor">Выбрать другого врача</button>
      </div>

      <template v-else-if="selectedDay">
        <section v-for="(g, gi) in groups" :key="`${booking.date}-${g.part}`" class="anim-rise flex flex-col gap-2.5" :class="`delay-${gi + 1}`">
          <h3 class="m-0 text-base font-semibold text-ink-2">{{ g.label }}</h3>
          <div class="grid grid-cols-4 gap-2">
            <button
              v-for="t in g.slots"
              :key="t"
              type="button"
              class="press h-12 rounded-chip border text-lg tabular-nums"
              :class="[
                taken(booking.date, t)
                  ? 'border-dashed border-taken-line text-faint line-through'
                  : t === booking.time
                    ? 'border-accent bg-accent font-semibold text-on-accent'
                    : 'border-line-strong bg-surface font-medium',
                taken(booking.date, t) && t === justTaken ? 'anim-ring' : '',
              ]"
              :disabled="taken(booking.date, t)"
              :aria-pressed="t === booking.time"
              :aria-label="taken(booking.date, t) ? `${t}, занято` : t"
              @click="pickTime(t)"
            >
              {{ t }}
            </button>
          </div>
        </section>
      </template>
      <p v-else class="m-0 text-base text-muted">Выберите день.</p>
    </template>
  </div>
</template>
