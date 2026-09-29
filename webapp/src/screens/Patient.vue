<script setup lang="ts">
import { PhPlus } from '@phosphor-icons/vue'
import { computed, nextTick, ref } from 'vue'
import { api } from '@/api/client'
import Banner from '@/components/Banner.vue'
import CheckRow from '@/components/CheckRow.vue'
import Field from '@/components/Field.vue'
import StepProgress from '@/components/StepProgress.vue'
import { branchInfo } from '@/lib/branches'
import { CLINIC_PHONE, CLINIC_PHONE_HREF, classify, GENERAL_MESSAGE } from '@/lib/errors'
import { shortDate, shortName } from '@/lib/format'
import { cleanPatient, formatBirthDate, formatPhone, MESSAGES, pluralFields, validatePatient } from '@/lib/patient'
import { platform } from '@/platform'
import { backTo, booking, emptyPatient, root, slotKey } from '@/state/booking'
import { patientByKey, patients, savePatient } from '@/state/patients'
import { onAccessError, refreshActive } from '@/state/session'
import { useMainButton } from '@/state/ui'

const NEW = 'new'
const sending = ref(false)
const generalError = ref('')
const showSummary = ref(false)
const formRef = ref<HTMLElement | null>(null)

const chips = computed(() => {
  const list = patients.list.map((p) => ({ key: p.key, label: p.label }))
  if (!list.some((c) => c.key === 'me')) list.unshift({ key: 'me', label: 'Я' })
  return list
})

function choose(key: string) {
  platform().haptic('select')
  booking.profileKey = key
  booking.errors = {}
  showSummary.value = false
  const saved = key === NEW ? undefined : patientByKey(key)
  booking.patient = saved
    ? { last_name: saved.last_name, first_name: saved.first_name, middle_name: saved.middle_name, birth_date: saved.birth_date, phone: formatPhone(saved.phone) }
    : emptyPatient()
}

// Первый заход на шаг: подставить «Я», если сохранён.
if (!booking.patient.first_name && !booking.patient.last_name && patientByKey(booking.profileKey)) choose(booking.profileKey)

const errorCount = computed(() => Object.keys(booking.errors).length)

function clearError(k: keyof typeof booking.errors) {
  if (booking.errors[k]) {
    const next = { ...booking.errors }
    delete next[k]
    booking.errors = next
  }
}

async function focusFirstError() {
  await nextTick()
  const el = formRef.value?.querySelector<HTMLElement>('[aria-invalid="true"]')
  el?.focus({ preventScroll: false })
}

async function submit() {
  if (sending.value) return
  generalError.value = ''
  booking.errors = validatePatient(booking.patient, booking.consent)
  showSummary.value = errorCount.value > 0
  if (errorCount.value) {
    platform().haptic('error')
    await focusFirstError()
    return
  }
  const doctor = booking.doctor!
  const service = booking.service!
  const patient = cleanPatient(booking.patient)
  sending.value = true
  try {
    await api.book({
      branch: booking.branch,
      doctor_id: doctor.id,
      doctor_name: doctor.full_name,
      service_id: service.id,
      service_name: service.name,
      date: booking.date,
      time: booking.time,
      patient,
      send_notifications: booking.notify,
      pd_consent: booking.consent,
    })
    platform().haptic('success')
    if (booking.remember) {
      const key = booking.profileKey === NEW ? null : booking.profileKey
      booking.profileKey = await savePatient(key, { ...patient, phone: booking.patient.phone }).catch(() => booking.profileKey)
    }
    booking.result = {
      date: booking.date,
      time: booking.time,
      doctorName: doctor.full_name,
      serviceName: service.displayName,
      branch: booking.branch,
      patientName: [patient.last_name, patient.first_name, patient.middle_name].filter(Boolean).join(' '),
      rescheduled: false,
    }
    refreshActive().catch(() => undefined)
    root('success')
  } catch (e) {
    platform().haptic('error')
    const kind = classify(e)
    const code = (e as { code?: string }).code
    if (kind === 'slot_taken') {
      booking.takenSlots.push(slotKey(booking.date, booking.time))
      booking.slotTakenNotice = booking.time
      booking.time = ''
      backTo('time')
    } else if (kind === 'second_booking') {
      await refreshActive().catch(() => false)
      root(booking.active ? 'my' : 'home')
    } else if (kind === 'field') {
      booking.errors = { ...booking.errors, [code === 'BAD_PHONE' ? 'phone' : 'birth_date']: (e as Error).message }
      showSummary.value = true
      await focusFirstError()
    } else if (kind === 'consent') {
      booking.errors = { ...booking.errors, consent: MESSAGES.consent }
      showSummary.value = true
    } else if (kind === 'access' || kind === 'expired') onAccessError(kind)
    else generalError.value = GENERAL_MESSAGE
  } finally {
    sending.value = false
  }
}

const mainState = computed(() => ({ text: 'Записаться', enabled: true, loading: sending.value }))
useMainButton(mainState, submit)

const branchName = computed(() => branchInfo(booking.branch).name)
</script>

<template>
  <div class="flex flex-col gap-5 px-4 pb-6 pt-5">
    <StepProgress :step="4" label="Пациент" />

    <div class="flex flex-col gap-0.5 rounded-box bg-accent-tint px-4 py-3.5">
      <span class="text-lg font-semibold first-letter:uppercase">{{ shortDate(booking.date) }} · {{ booking.time }}</span>
      <span class="text-[15px] text-ink-2">{{ shortName(booking.doctor!.full_name) }} · {{ branchName }}</span>
      <span class="text-[15px] text-ink-2">{{ booking.service!.displayName }}</span>
    </div>

    <h1 class="m-0 text-2xl font-bold tracking-[-0.01em]">Кто пойдёт на приём</h1>

    <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Пациент">
      <button
        v-for="c in chips"
        :key="c.key"
        type="button"
        role="radio"
        :aria-checked="booking.profileKey === c.key"
        class="press h-11 rounded-full border px-[18px] text-base"
        :class="booking.profileKey === c.key ? 'border-accent bg-accent font-semibold text-on-accent' : 'border-line-strong bg-surface font-medium'"
        @click="choose(c.key)"
      >
        {{ c.label }}
      </button>
      <button
        type="button"
        role="radio"
        :aria-checked="booking.profileKey === NEW"
        class="press flex h-11 items-center gap-1.5 rounded-full border px-4 text-base font-medium"
        :class="booking.profileKey === NEW ? 'border-accent bg-accent text-on-accent' : 'border-dashed border-[#9fb2ae] text-accent'"
        @click="choose(NEW)"
      >
        <PhPlus :size="18" weight="bold" aria-hidden="true" />Другой человек
      </button>
    </div>

    <Banner v-if="generalError" tone="danger" title="Не удалось записаться">
      {{ generalError }} <a :href="CLINIC_PHONE_HREF" class="font-semibold no-underline">{{ CLINIC_PHONE }}</a>
    </Banner>
    <Banner v-else-if="showSummary && errorCount" tone="danger" :title="`Проверьте ${pluralFields(errorCount)} ниже`" />

    <form ref="formRef" class="flex flex-col gap-4" novalidate @submit.prevent="submit">
      <Field v-model="booking.patient.last_name" label="Фамилия" autocomplete="family-name" :maxlength="100" :error="booking.errors.last_name" @update:model-value="clearError('last_name')" />
      <Field v-model="booking.patient.first_name" label="Имя" autocomplete="given-name" :maxlength="100" :error="booking.errors.first_name" @update:model-value="clearError('first_name')" />
      <Field v-model="booking.patient.middle_name" label="Отчество, если есть" autocomplete="additional-name" :maxlength="100" :error="booking.errors.middle_name" @update:model-value="clearError('middle_name')" />
      <div class="grid grid-cols-1 gap-4 min-[360px]:grid-cols-2 min-[360px]:gap-3">
        <Field
          v-model="booking.patient.birth_date"
          label="Дата рождения"
          inputmode="numeric"
          autocomplete="bday"
          :maxlength="10"
          :format="formatBirthDate"
          :error="booking.errors.birth_date"
          @update:model-value="clearError('birth_date')"
        />
        <Field
          v-model="booking.patient.phone"
          label="Телефон"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          :maxlength="18"
          :format="formatPhone"
          :error="booking.errors.phone"
          @update:model-value="clearError('phone')"
        />
      </div>
      <CheckRow v-model="booking.remember">Запомнить данные на этом устройстве для следующих записей</CheckRow>
      <CheckRow v-model="booking.notify">Напоминать о визите в этом чате</CheckRow>
      <CheckRow v-model="booking.consent" :error="booking.errors.consent" @update:model-value="clearError('consent')">
        Согласен на обработку персональных данных
        <template v-if="booking.pdPolicyUrl">
          по
          <a :href="booking.pdPolicyUrl" @click.prevent.stop="platform().openLink(booking.pdPolicyUrl)">условиям клиники</a>
        </template>
      </CheckRow>
      <button type="submit" class="sr-only" tabindex="-1">Записаться</button>
    </form>
  </div>
</template>
