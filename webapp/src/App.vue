<script setup lang="ts">
import { computed, nextTick, onMounted, watch, type Component } from 'vue'
import { api } from '@/api/client'
import AppHeader from '@/components/AppHeader.vue'
import EyeLoader from '@/components/EyeLoader.vue'
import MainAction from '@/components/MainAction.vue'
import { classify } from '@/lib/errors'
import { platform } from '@/platform'
import Access from '@/screens/Access.vue'
import Choose from '@/screens/Choose.vue'
import DoctorServices from '@/screens/DoctorServices.vue'
import Home from '@/screens/Home.vue'
import MyBooking from '@/screens/MyBooking.vue'
import Patient from '@/screens/Patient.vue'
import ServiceDoctors from '@/screens/ServiceDoctors.vue'
import Success from '@/screens/Success.vue'
import Time from '@/screens/Time.vue'
import { back, booking, root, top, type Screen } from '@/state/booking'
import { loadPatients } from '@/state/patients'
import { onAccessError, refreshActive } from '@/state/session'
import { effectiveScheme, loadThemePref, themePref } from '@/state/theme'
import { mainButton } from '@/state/ui'

const SCREENS: Record<Exclude<Screen, 'loading'>, Component> = {
  access: Access,
  home: Home,
  choose: Choose,
  doctorServices: DoctorServices,
  serviceDoctors: ServiceDoctors,
  time: Time,
  patient: Patient,
  success: Success,
  my: MyBooking,
}

const p = platform()
const screen = computed(() => top())
const current = computed(() => (screen.value === 'loading' ? null : SCREENS[screen.value]))
const canBack = computed(() => booking.stack.length > 1 && !['success', 'access'].includes(screen.value))

// --- Тема: как в мессенджере (FR-014) или выбранная пациентом ---
function applyTheme() {
  const scheme = effectiveScheme()
  document.documentElement.dataset.theme = scheme
  const css = getComputedStyle(document.documentElement)
  const v = (n: string) => css.getPropertyValue(n).trim()
  p.applyShell({
    bg: v('--c-bg'),
    chrome: v('--c-chrome'),
    accent: v('--c-accent'),
    onAccent: v('--c-on-accent'),
    disabledBg: v('--c-disabled-bg'),
    disabledInk: v('--c-disabled-ink'),
  })
  // Цвет нативной главной кнопки зависит от темы — переставить.
  const mb = mainButton.value
  if (mb) p.setMainButton(mb.state, mb.onClick)
}
applyTheme()
p.onColorSchemeChange(() => themePref.value === 'auto' && applyTheme())
watch(themePref, applyTheme)
loadThemePref().catch(() => undefined)

// --- Кнопки мессенджера ---
watch(mainButton, (mb) => p.setMainButton(mb ? mb.state : null, mb ? mb.onClick : null), { immediate: true })
watch(canBack, (v) => p.setBackButton(v, v ? back : null), { immediate: true })

// Новый экран — наверх страницы.
watch(screen, async () => {
  await nextTick()
  window.scrollTo({ top: 0 })
})

onMounted(async () => {
  p.ready()
  if (!p.initData) return onAccessError('access')
  api.config().then((c) => (booking.pdPolicyUrl = c.pd_policy_url || '')).catch(() => undefined)
  loadPatients().catch(() => undefined)
  try {
    const has = await refreshActive()
    root(has ? 'my' : 'home')
  } catch (e) {
    const kind = classify(e)
    if (kind === 'access' || kind === 'expired') onAccessError(kind)
    else root('home') // запись всё равно доступна; активную запись сервер проверит при отправке
  }
})
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <AppHeader v-if="!p.nativeBackButton" :can-back="canBack" @back="back" />
    <main class="relative flex-1 overflow-x-clip">
      <div v-if="screen === 'loading'" class="px-4 pt-10">
        <EyeLoader text="Открываем запись…" />
      </div>
      <Transition v-else :name="`step-${booking.dir}`">
        <component :is="current" :key="`${screen}-${booking.stack.length}`" class="min-h-full" />
      </Transition>
    </main>
    <MainAction v-if="!p.nativeMainButton" />
  </div>
</template>
