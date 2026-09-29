<script setup lang="ts">
import { PhCircleHalf, PhMoon, PhSun } from '@phosphor-icons/vue'
import { platform } from '@/platform'
import { setThemePref, themePref, type ThemePref } from '@/state/theme'

const OPTIONS: { value: ThemePref; label: string; icon: typeof PhSun }[] = [
  { value: 'auto', label: 'Авто', icon: PhCircleHalf },
  { value: 'light', label: 'Светлая', icon: PhSun },
  { value: 'dark', label: 'Тёмная', icon: PhMoon },
]

function pick(v: ThemePref) {
  if (v === themePref.value) return
  platform().haptic('select')
  setThemePref(v)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <span id="theme-label" class="text-[15px] text-muted">Оформление</span>
    <div role="radiogroup" aria-labelledby="theme-label" class="grid grid-cols-3 gap-1 rounded-box bg-segment p-1">
      <button
        v-for="o in OPTIONS"
        :key="o.value"
        type="button"
        role="radio"
        :aria-checked="themePref === o.value"
        class="press flex h-11 items-center justify-center gap-1.5 rounded-[11px] text-[15px]"
        :class="themePref === o.value ? 'bg-surface font-semibold text-ink shadow-[0_1px_2px_rgb(15_46_42/0.12)] ring-1 ring-line-strong' : 'font-medium text-ink-2'"
        @click="pick(o.value)"
      >
        <component :is="o.icon" :size="18" aria-hidden="true" />{{ o.label }}
      </button>
    </div>
  </div>
</template>
