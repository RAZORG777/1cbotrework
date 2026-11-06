<script setup lang="ts">
import { PhInfo } from '@phosphor-icons/vue'
import CheckRow from '@/components/CheckRow.vue'

/** Условия приёма ребёнка до 18 лет (specs/010-child-visit-notice). */
const ack = defineModel<boolean>({ required: true })
defineProps<{ error?: string }>()
defineEmits<{ change: [] }>()
</script>

<template>
  <section
    class="anim-rise flex flex-col gap-3 rounded-box border border-accent-tint-line bg-accent-tint px-4 py-4"
    aria-labelledby="child-notice-title"
  >
    <div class="flex items-center gap-2.5">
      <PhInfo :size="24" class="shrink-0 text-accent" aria-hidden="true" />
      <h2 id="child-notice-title" class="m-0 text-[18px] font-semibold leading-tight">Приём ребёнка до&nbsp;18&nbsp;лет</h2>
    </div>
    <p class="m-0 text-base leading-snug text-ink-2">
      На первичный приём ребёнок должен быть вместе с&nbsp;законным представителем&nbsp;— мамой, папой или опекуном.
    </p>
    <div class="flex flex-col gap-1.5">
      <p class="m-0 text-base font-semibold">Возьмите с&nbsp;собой:</p>
      <ul class="m-0 flex list-disc flex-col gap-1 pl-5 text-base leading-snug text-ink-2 marker:text-accent">
        <li>свидетельство о&nbsp;рождении или паспорт ребёнка;</li>
        <li>СНИЛС ребёнка;</li>
        <li>паспорт законного представителя.</li>
      </ul>
    </div>
    <p class="m-0 text-base font-semibold leading-snug">
      Если ребёнок придёт без законного представителя, клиника откажет в&nbsp;оформлении медицинских документов
      и&nbsp;проведении медицинского обследования!
    </p>
    <CheckRow v-model="ack" :error="error" @update:model-value="$emit('change')">Я ознакомлен(а) с&nbsp;условиями приёма ребёнка</CheckRow>
  </section>
</template>
