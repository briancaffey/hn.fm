/**
 * The one way tables fetch paginated data in this app.
 *
 * Composes usePagination with sort/search/filter state, debounced search,
 * optional URL query sync (shareable table state), and the standard API
 * contract: `{ [itemsKey]: T[], pagination: { total, offset, limit, count } }`.
 *
 * Usage:
 *   const table = usePaginatedFetch<Story>({
 *     endpoint: '/api/stories',
 *     itemsKey: 'items',
 *     defaultSort: 'id',
 *     syncQuery: true,
 *     filters: { has_video: undefined, has_runs: undefined },
 *   })
 *   // table.rows, table.pending, table.page, table.toggleSort('score'), …
 */

export interface PaginatedFetchOptions {
  endpoint: string
  itemsKey?: string
  defaultLimit?: number
  defaultSort?: string
  defaultDir?: 'asc' | 'desc'
  /** Reflect page/sort/search in the route query (shareable/back-button-safe) */
  syncQuery?: boolean
  /** Extra query params, sent when not undefined/null/'' */
  filters?: Record<string, unknown>
  searchDebounceMs?: number
}

export function usePaginatedFetch<T = Record<string, unknown>>(
  options: PaginatedFetchOptions,
) {
  const {
    endpoint,
    itemsKey = 'items',
    defaultLimit = 50,
    defaultSort = '',
    defaultDir = 'desc',
    syncQuery = false,
    searchDebounceMs = 300,
  } = options

  const config = useRuntimeConfig()
  const route = useRoute()
  const router = useRouter()

  const initial = syncQuery ? route.query : {}
  const pagination = usePagination({
    initialPage: initial.page ? Number(initial.page) : 1,
    initialLimit: initial.limit ? Number(initial.limit) : defaultLimit,
  })

  const sort = ref<string>((initial.sort as string) || defaultSort)
  const dir = ref<'asc' | 'desc'>(
    (initial.dir as 'asc' | 'desc') || defaultDir,
  )
  const q = ref<string>((initial.q as string) || '')
  const filters = reactive<Record<string, unknown>>({
    ...(options.filters || {}),
  })

  const rows = ref<T[]>([]) as Ref<T[]>
  const pending = ref(false)
  const error = ref<unknown>(null)

  function buildParams(): Record<string, unknown> {
    const params: Record<string, unknown> = {
      offset: pagination.offset.value,
      limit: pagination.limit.value,
    }
    if (sort.value) {
      params.sort = sort.value
      params.dir = dir.value
    }
    if (q.value) params.q = q.value
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        params[key] = value
      }
    }
    return params
  }

  let requestSeq = 0
  async function fetchPage() {
    const seq = ++requestSeq
    pending.value = true
    error.value = null
    try {
      // The envelope is generic across list endpoints: a data array under a
      // per-endpoint key, plus pagination. `unknown` rather than `any` so the
      // narrowing below stays honest.
      const data = await $fetch<Record<string, unknown>>(
        `${config.public.apiBase}${endpoint}`,
        { params: buildParams() },
      )
      if (seq !== requestSeq) return // a newer request superseded this one
      rows.value = (data?.[itemsKey] as T[]) || []
      pagination.setTotal(data?.pagination?.total ?? rows.value.length)
    } catch (e) {
      if (seq !== requestSeq) return
      error.value = e
      rows.value = []
    } finally {
      if (seq === requestSeq) pending.value = false
    }
  }

  function updateQuery() {
    if (!syncQuery) return
    // Built fresh rather than mutated-and-deleted: a default-valued param
    // should simply be absent from the URL, and constructing the object that
    // way needs neither a dynamic delete nor an `any` cast over route.query
    // (whose values are string | string[] | null).
    const managed = ['page', 'limit', 'sort', 'dir', 'q']
    const wanted: Array<[string, string, string]> = [
      ['page', String(pagination.page.value), '1'],
      ['limit', String(pagination.limit.value), String(defaultLimit)],
      ['sort', sort.value, defaultSort],
      ['dir', dir.value, defaultDir],
      ['q', q.value, ''],
    ]

    const query: Record<string, string> = {}
    // Anything this composable does not own is passed through untouched.
    for (const [k, v] of Object.entries(route.query)) {
      if (!managed.includes(k) && typeof v === 'string') query[k] = v
    }
    for (const [key, value, defaultValue] of wanted) {
      if (value && value !== defaultValue) query[key] = value
    }
    router.replace({ query })
  }

  function toggleSort(key: string) {
    if (sort.value === key) {
      dir.value = dir.value === 'desc' ? 'asc' : 'desc'
    } else {
      sort.value = key
      dir.value = defaultDir
    }
    pagination.firstPage()
  }

  let searchTimer: ReturnType<typeof setTimeout> | undefined
  function setSearch(value: string) {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      q.value = value
      pagination.firstPage()
    }, searchDebounceMs)
  }

  function setFilter(key: string, value: unknown) {
    filters[key] = value
    pagination.firstPage()
  }

  // one watcher drives everything: state change → URL sync → refetch
  watch(
    [
      () => pagination.page.value,
      () => pagination.limit.value,
      sort,
      dir,
      q,
      filters,
    ],
    () => {
      updateQuery()
      fetchPage()
    },
    { deep: true },
  )

  onMounted(fetchPage)

  return {
    // data
    rows,
    pending,
    error,
    // pagination (pass straight to <PaginationBar>)
    page: pagination.page,
    limit: pagination.limit,
    total: pagination.total,
    totalPages: pagination.totalPages,
    hasNextPage: pagination.hasNextPage,
    hasPreviousPage: pagination.hasPreviousPage,
    setPage: pagination.setPage,
    setLimit: pagination.setLimit,
    nextPage: pagination.nextPage,
    previousPage: pagination.previousPage,
    // sort / search / filters
    sort,
    dir,
    q,
    filters,
    toggleSort,
    setSearch,
    setFilter,
    // manual refresh (after mutations)
    refresh: fetchPage,
  }
}
