<script setup lang="ts">
import { cn } from '~/lib/utils'

interface TabsTriggerProps {
  value: string
  disabled?: boolean
  class?: string
}

const props = withDefaults(defineProps<TabsTriggerProps>(), {
  disabled: false,
  class: ''
})

const activeTab = inject('activeTab', ref(''))
const updateActiveTab = inject('updateActiveTab', () => {})

const isActive = computed(() => activeTab.value === props.value)

const handleClick = () => {
  if (!props.disabled) {
    updateActiveTab(props.value)
  }
}
</script>

<template>
  <button
    :class="cn(
      'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
      isActive
        ? 'bg-background text-foreground shadow-sm'
        : 'hover:bg-background/50',
      props.class
    )"
    :disabled="disabled"
    @click="handleClick"
  >
    <slot />
  </button>
</template>
