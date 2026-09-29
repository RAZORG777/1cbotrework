<script setup lang="ts">
import { PhChatCircleDots } from '@phosphor-icons/vue'
import { CLINIC_PHONE, CLINIC_PHONE_HREF } from '@/lib/errors'
import { booking } from '@/state/booking'
</script>

<template>
  <div class="flex min-h-full flex-col items-center justify-center gap-4 px-6 py-10 text-center">
    <span class="flex h-16 w-16 items-center justify-center rounded-full bg-accent-tint text-accent" aria-hidden="true">
      <PhChatCircleDots :size="32" />
    </span>
    <h1 class="m-0 text-2xl font-bold leading-tight">
      {{ booking.accessKind === 'expired' ? 'Сессия устарела' : 'Откройте запись через бота клиники' }}
    </h1>
    <p class="m-0 max-w-[320px] text-base leading-snug text-muted">
      {{
        booking.accessKind === 'expired'
          ? 'Закройте форму и откройте её из бота заново: так мы защищаем ваши данные.'
          : 'Форма работает только внутри Telegram или MAX: нажмите кнопку записи в чате с ботом «Ясно Вижу».'
      }}
    </p>
    <a :href="CLINIC_PHONE_HREF" class="flex h-11 items-center text-[17px] font-semibold no-underline tabular-nums">{{ CLINIC_PHONE }}</a>
  </div>
</template>
