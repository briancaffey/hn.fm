<script setup lang="ts">
import { cn } from '~/lib/utils'

interface TabsProps {
  defaultValue?: string
  value?: string
  orientation?: 'horizontal' | 'vertical'
  class?: string
}

const props = withDefaults(defineProps<TabsProps>(), {
  orientation: 'horizontal',
  class: ''
})

const activeTab = ref(props.value || props.defaultValue)

const updateActiveTab = (value: string) => {
  activeTab.value = value
}

provide('activeTab', activeTab)
provide('updateActiveTab', updateActiveTab)
</script>

<template>
  <div
    :class="cn(
      'w-full',
      props.orientation === 'vertical' ? 'flex flex-row' : 'flex flex-col',
      props.class
    )"
  >
    <slot />
  </div>
</template>
