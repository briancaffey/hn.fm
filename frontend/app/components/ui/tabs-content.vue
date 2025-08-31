<script setup lang="ts">
import { cn } from '~/lib/utils'

interface TabsContentProps {
  value: string
  class?: string
}

const props = withDefaults(defineProps<TabsContentProps>(), {
  class: ''
})

const activeTab = inject('activeTab', ref(''))

const isActive = computed(() => activeTab.value === props.value)
</script>

<template>
  <div
    v-if="isActive"
    :class="cn(
      'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
      props.class
    )"
  >
    <slot />
  </div>
</template>
