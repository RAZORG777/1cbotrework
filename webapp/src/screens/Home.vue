<script setup lang="ts">
import { PhMapPin } from '@phosphor-icons/vue'
import logo from '@/assets/logo.png'
import StepProgress from '@/components/StepProgress.vue'
import { BRANCHES, type BranchInfo } from '@/lib/branches'
import { CLINIC_PHONE, CLINIC_PHONE_HREF } from '@/lib/errors'
import { platform } from '@/platform'
import { booking, go } from '@/state/booking'

function pick(b: BranchInfo) {
  platform().haptic('select')
  if (booking.branch !== b.id) {
    booking.doctor = null
    booking.service = null
  }
  booking.branch = b.id
  go('choose')
}
</script>

<template>
  <div class="flex min-h-full flex-col gap-7 px-4 pb-6 pt-6">
    <div class="flex items-center gap-4">
      <img :src="logo" alt="Ясно Вижу, офтальмологическая клиника" width="76" height="76" class="h-16 w-16 shrink-0 rounded-full bg-[#fbfcfc] min-[360px]:h-[76px] min-[360px]:w-[76px]" />
      <div class="flex min-w-0 flex-col gap-1.5">
        <h1 class="m-0 text-2xl min-[360px]:text-[27px] font-bold leading-[1.15] tracking-[-0.01em]">Запись к&nbsp;офтальмологу</h1>
        <p class="m-0 text-base text-muted">Врача, услугу и время подберём дальше</p>
      </div>
    </div>

    <StepProgress :step="1" label="Филиал" />

    <section class="flex flex-col gap-3" aria-labelledby="branches-title">
      <h2 id="branches-title" class="m-0 text-xl font-semibold">Где вам удобнее?</h2>
      <button
        v-for="(b, i) in BRANCHES"
        :key="b.id"
        type="button"
        class="press anim-rise flex items-center gap-3.5 rounded-box border border-line bg-surface px-4 py-[18px] text-left hover:border-line-strong"
        :class="`delay-${i + 1}`"
        @click="pick(b)"
      >
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-tint text-accent" aria-hidden="true">
          <PhMapPin :size="22" />
        </span>
        <span class="flex min-w-0 flex-1 flex-col gap-1">
          <span class="text-[19px] font-semibold">{{ b.name }}</span>
          <span class="text-[15px] text-muted">{{ b.address }}</span>
          <span class="text-[15px] tabular-nums text-muted">{{ b.phone }}</span>
        </span>
      </button>
    </section>

    <div class="flex-1" />
    <p class="m-0 text-center text-[15px] text-muted">
      Вопросы по записи:
      <a :href="CLINIC_PHONE_HREF" class="inline-flex min-h-11 items-center font-semibold no-underline tabular-nums">{{ CLINIC_PHONE }}</a>
    </p>
  </div>
</template>
