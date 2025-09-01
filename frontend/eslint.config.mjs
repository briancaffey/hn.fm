// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  // Your custom configs here
  {
    ignores: [
      // Ignore shadcn-ui components (third-party)
      'app/components/ui/**',
      // Ignore build outputs
      '.nuxt/**',
      'dist/**',
      '.output/**',
      // Ignore other generated files
      '*.log'
    ]
  }
)
