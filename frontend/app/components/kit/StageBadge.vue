<script setup lang="ts">
import { computed } from 'vue'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '~/components/ui/tooltip'
import { stageMeta, stageStyle } from '~/composables/usePipelineVocab'

/** A pipeline stage, with its one canonical colour and an explanation. */
const props = defineProps<{ stage?: string | null, showLabel?: boolean }>()

const meta = computed(() => stageMeta(props.stage))
const style = computed(() => stageStyle(props.stage))
</script>

<template>
  <TooltipProvider :delay-duration="150">
    <Tooltip>
      <TooltipTrigger as-child>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2 w-2 shrink-0 rounded-full" :style="style" aria-hidden="true" />
          <span v-if="showLabel !== false" class="text-xs text-muted-foreground">
            {{ meta.label }}
          </span>
        </span>
      </TooltipTrigger>
      <TooltipContent v-if="meta.hint" class="max-w-xs text-xs leading-relaxed">
        <span class="font-medium">{{ meta.label }}</span> — {{ meta.hint }}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
