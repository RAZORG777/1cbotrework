<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Avatar from '@/components/Avatar.vue'
import ErrorState from '@/components/ErrorState.vue'
import ListRow from '@/components/ListRow.vue'
import SearchField from '@/components/SearchField.vue'
import Segmented from '@/components/Segmented.vue'
import SkeletonRows from '@/components/SkeletonRows.vue'
import StepProgress from '@/components/StepProgress.vue'
import type { Doctor } from '@/api/types'
import { branchInfo } from '@/lib/branches'
import { formatPrice } from '@/lib/format'
import { groupServices, matches, type ServiceItem } from '@/lib/services'
import { platform } from '@/platform'
import { back, booking, go, root } from '@/state/booking'
import { catalog } from '@/state/catalog'
import { useLoader } from './useLoader'

const query = ref('')
const branch = computed(() => branchInfo(booking.branch))

const doctors = useLoader(() => catalog.doctors(booking.branch))
const services = useLoader(() => catalog.branchServices(booking.branch))

watch(
  () => booking.path,
  (p) => {
    query.value = ''
    if (p === 'doctor') doctors.load()
    else services.load()
  },
  { immediate: true },
)

const shownDoctors = computed(() => (doctors.data.value ?? []).filter((d) => matches(d.full_name, query.value)))
const shownServices = computed(() =>
  groupServices((services.data.value ?? []).filter((s) => matches(s.displayName, query.value))),
)

function pickDoctor(d: Doctor) {
  platform().haptic('select')
  booking.doctor = d
  booking.service = null
  go('doctorServices')
}

function pickService(s: ServiceItem) {
  platform().haptic('select')
  booking.service = s
  booking.doctor = null
  go('serviceDoctors')
}

function changeBranch() {
  if (booking.stack.includes('home')) back()
  else root('home', 'back')
}

const groups = computed(() => [
  { title: 'Первичный приём', items: shownServices.value.primary },
  { title: 'Повторный приём', items: shownServices.value.repeat },
])
</script>

<template>
  <div class="flex flex-col gap-5 px-4 pb-6 pt-5">
    <StepProgress :step="2" label="Врач или услуга" />

    <div class="flex items-center justify-between gap-3">
      <div class="flex flex-col gap-0.5">
        <span class="text-[15px] text-muted">Филиал</span>
        <span class="text-[17px] font-semibold">{{ branch.name }}</span>
      </div>
      <button type="button" class="flex h-11 items-center px-1 text-base font-medium text-accent" @click="changeBranch">Изменить</button>
    </div>

    <Segmented
      v-model="booking.path"
      label="Способ записи"
      :options="[
        { value: 'doctor', label: 'Врачи' },
        { value: 'service', label: 'Услуги' },
      ]"
    />

    <SearchField
      v-model="query"
      :label="booking.path === 'doctor' ? 'Поиск врача по фамилии' : 'Поиск услуги'"
      :placeholder="booking.path === 'doctor' ? 'Фамилия врача' : 'Название услуги'"
    />

    <template v-if="booking.path === 'doctor'">
      <SkeletonRows v-if="doctors.loading.value" :rows="5" avatar />
      <ErrorState v-else-if="doctors.error.value" @retry="doctors.load()" />
      <p v-else-if="!shownDoctors.length" class="anim-fade m-0 py-6 text-center text-base text-muted">
        {{ query ? 'Врач не найден. Проверьте фамилию.' : 'В этом филиале сейчас нет врачей для онлайн-записи.' }}
      </p>
      <ul v-else class="anim-fade m-0 list-none overflow-hidden rounded-box border border-line bg-surface p-0">
        <li v-for="d in shownDoctors" :key="d.id" class="border-b border-divider last:border-b-0">
          <ListRow @click="pickDoctor(d)">
            <template #lead><Avatar :name="d.full_name" :photo="d.photo_url" /></template>
            <span class="text-[17px] font-semibold leading-tight">{{ d.full_name }}</span>
            <span v-if="d.description || d.specialty_name" class="text-[15px] leading-snug text-muted">{{ d.description || d.specialty_name }}</span>
            <span v-if="d.experience" class="text-[15px] text-muted">Стаж {{ d.experience }}</span>
          </ListRow>
        </li>
      </ul>
    </template>

    <template v-else>
      <SkeletonRows v-if="services.loading.value" :rows="6" />
      <ErrorState v-else-if="services.error.value" @retry="services.load()" />
      <p v-else-if="!shownServices.primary.length && !shownServices.repeat.length" class="anim-fade m-0 py-6 text-center text-base text-muted">
        {{ query ? 'Услуга не найдена.' : 'В этом филиале нет услуг для онлайн-записи.' }}
      </p>
      <template v-else>
        <section v-for="g in groups" v-show="g.items.length" :key="g.title" class="anim-fade flex flex-col gap-2.5">
          <h2 class="m-0 text-base font-semibold text-ink-2">{{ g.title }}</h2>
          <ul class="m-0 list-none overflow-hidden rounded-box border border-line bg-surface p-0">
            <li v-for="s in g.items" :key="s.id" class="border-b border-divider last:border-b-0">
              <ListRow @click="pickService(s)">
                <span class="text-[17px] leading-snug">{{ s.displayName }}</span>
                <template #trail>
                  <span v-if="formatPrice(s.price)" class="whitespace-nowrap text-base font-semibold tabular-nums">{{ formatPrice(s.price) }}</span>
                </template>
              </ListRow>
            </li>
          </ul>
        </section>
      </template>
    </template>
  </div>
</template>
