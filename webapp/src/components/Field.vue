<script setup lang="ts">
import { useId } from 'vue'
const props = defineProps<{
  label: string
  modelValue: string
  error?: string
  inputmode?: 'text' | 'numeric' | 'tel'
  type?: string
  autocomplete?: string
  maxlength?: number
  format?: (v: string) => string
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const id = useId()

function onInput(e: Event) {
  const el = e.target as HTMLInputElement
  const v = props.format ? props.format(el.value) : el.value
  if (v !== el.value) el.value = v
  emit('update:modelValue', v)
}
</script>

<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <label :for="id" class="text-[15px] font-medium text-ink-2">{{ label }}</label>
    <input
      :id="id"
      :value="modelValue"
      :type="type ?? 'text'"
      :inputmode="inputmode"
      :autocomplete="autocomplete"
      :maxlength="maxlength"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-e` : undefined"
      class="h-[52px] w-full min-w-0 rounded-box border bg-surface px-3.5 text-[17px] tabular-nums outline-none transition-colors focus:border-2 focus:border-accent focus:px-[13px]"
      :class="error ? 'border-2 border-danger px-[13px]' : 'border-line-strong'"
      @input="onInput"
    />
    <span v-if="error" :id="`${id}-e`" class="anim-fade text-[15px] text-danger">{{ error }}</span>
  </div>
</template>
