<script setup lang="ts">
import { Icon } from '#components'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '~/components/ui/tooltip'

/**
 * The "what am I looking at" affordance.
 *
 * Every non-obvious label, column and metric gets one. The rule: if a reader
 * who has never seen the pipeline could not say what a thing means and why it
 * matters, it needs a hint.
 */
withDefaults(defineProps<{ text: string, side?: 'top' | 'right' | 'bottom' | 'left' }>(), { side: 'top' })
</script>

<template>
  <TooltipProvider :delay-duration="150">
    <Tooltip>
      <TooltipTrigger as-child>
        <button
          type="button"
          class="inline-flex align-middle text-muted-foreground/70 transition-colors hover:text-foreground"
          :aria-label="text"
        >
          <Icon name="lucide:info" class="h-3 w-3" />
        </button>
      </TooltipTrigger>
      <TooltipContent :side="side" class="max-w-xs text-xs leading-relaxed">
        {{ text }}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
