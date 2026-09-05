<script setup lang="ts">
import { computed } from 'vue'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '~/components/ui/tooltip'
import { statusClasses, statusMeta } from '~/composables/usePipelineVocab'

/**
 * A pipeline state, coloured from tokens and explaining itself on hover.
 *
 * Status colours used to be written inline as palette classes — `bg-green-100
 * text-green-800` and friends — and 84% of them had no dark-mode variant, so
 * in dark mode a chip was a pale block with near-black text.
 */
const props = withDefaults(
  defineProps<{ status?: string | null, dot?: boolean, label?: string }>(),
  { dot: false, status: null, label: undefined },
)

const meta = computed(() => statusMeta(props.status))
const classes = computed(() => statusClasses(props.status))
</script>

<template>
  <TooltipProvider :delay-duration="150">
    <Tooltip>
      <TooltipTrigger as-child>
        <span
          class="inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[11px] font-medium leading-none"
          :class="classes"
        >
          <span
            v-if="dot"
            class="h-1.5 w-1.5 rounded-full bg-current"
            :class="meta.tone === 'running' ? 'animate-pulse' : ''"
            aria-hidden="true"
          />
          {{ label ?? meta.label }}
        </span>
      </TooltipTrigger>
      <TooltipContent class="max-w-xs text-xs leading-relaxed">
        {{ meta.hint }}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
