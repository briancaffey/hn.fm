/**
 * The one place that knows how to size a video frame.
 *
 * A segment is rendered 16:9, 1:1 or 9:16, and a player sized for one crops
 * the others. This existed as three near-identical copies — GenerationsTable,
 * the item gallery, the compare page — differing only in a max-width constant,
 * and a fourth player (SegmentCard) that had no copy at all and so hard-cropped
 * every portrait video it showed. One definition, so the next player added gets
 * it right by default.
 *
 * Pair the returned style with `object-contain` on the <video>. `object-cover`
 * crops, and it keeps cropping in fullscreen — the browser makes the element
 * fullscreen and the element's own object-fit still applies, so a cropped
 * player stays cropped on a 27" display.
 */

const RATIOS: Record<string, string> = {
  '16:9': '16 / 9',
  '1:1': '1 / 1',
  '9:16': '9 / 16',
}

export interface VideoFrameOptions {
  /** Cap the width of a portrait video, which is otherwise absurdly tall. */
  portraitMaxWidth?: string
  landscapeMaxWidth?: string
  /**
   * Fix the height instead and let aspect ratio pick the width. Use in lists,
   * where rows of different orientations should still be the same height.
   */
  height?: string
}

export function videoFrameStyle(
  format?: string | null,
  options: VideoFrameOptions = {},
) {
  const {
    portraitMaxWidth = '240px',
    landscapeMaxWidth = '100%',
    height,
  } = options

  // Unknown formats fall back to 16:9 rather than to `undefined`, which
  // silently drops the aspect-ratio rule and collapses the frame.
  const aspectRatio = RATIOS[format || '16:9'] || RATIOS['16:9']

  if (height) return { aspectRatio, height }

  return {
    aspectRatio,
    maxWidth: format === '9:16' ? portraitMaxWidth : landscapeMaxWidth,
  }
}
