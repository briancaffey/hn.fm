---
description: Rules to follow when working with the frontend
globs: frontend/*
alwaysApply: true
---

Use yarn commands and always make sure to first cd into the frontend directory before running commands with yarn so that they run from the root of the Nuxt project.

When making components, always build with the shadcn-ui components.

Follow Nuxt 4 conventions.

Make use of useAsyncData when making network requests.

When making network requests, always follow this pattern:

```
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

// Fetch services data, for example
const { data: servicesData, pending, refresh } = await useAsyncData<ServicesResponse>('services', () =>
  $fetch(`${apiBase}/api/services/status`)
)
```