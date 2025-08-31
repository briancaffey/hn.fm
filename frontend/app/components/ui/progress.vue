<script setup lang="ts">
import { cn } from '~/lib/utils'

interface Props {
  value?: number
  max?: number
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  value: 0,
  max: 100,
  class: ''
})

const percentage = computed(() => {
  return Math.min(100, Math.max(0, (props.value / props.max) * 100))
})
</script>

<template>
  <div
    :class="cn(
      'relative h-2 w-full overflow-hidden rounded-full bg-secondary',
      props.class
    )"
  >
    <div
      class="h-full w-full flex-1 bg-primary transition-all duration-300 ease-in-out"
      :style="{ transform: `translateX(-${100 - percentage}%)` }"
    />
  </div>
</template>
