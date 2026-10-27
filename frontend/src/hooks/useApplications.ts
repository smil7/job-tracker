import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'
import type { Application, ApplicationCreate, ApplicationUpdate } from '../api/types'

const keys = {
  list: ['applications'] as const,
  detail: (id: string) => ['applications', id] as const,
  stats: ['stats'] as const,
}

export function useApplications() {
  return useQuery({
    queryKey: keys.list,
    queryFn: async () => unwrap(await api.GET('/api/applications')),
  })
}

export function useApplication(id: string | null) {
  return useQuery({
    queryKey: keys.detail(id ?? ''),
    queryFn: async () =>
      unwrap(await api.GET('/api/applications/{application_id}', { params: { path: { application_id: id! } } })),
    enabled: id !== null,
  })
}

export function useStats() {
  return useQuery({
    queryKey: keys.stats,
    queryFn: async () => unwrap(await api.GET('/api/stats')),
  })
}

function useInvalidateAll() {
  const queryClient = useQueryClient()
  return () => Promise.all([
    queryClient.invalidateQueries({ queryKey: keys.list }),
    queryClient.invalidateQueries({ queryKey: keys.stats }),
  ])
}

export function useCreateApplication() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: async (body: ApplicationCreate) => unwrap(await api.POST('/api/applications', { body })),
    onSuccess: invalidate,
  })
}

export function useUpdateApplication() {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: ApplicationUpdate }) =>
      unwrap(
        await api.PATCH('/api/applications/{application_id}', { params: { path: { application_id: id } }, body }),
      ),
    // Move the card straight away so drag and drop feels instant
    onMutate: async ({ id, body }) => {
      await queryClient.cancelQueries({ queryKey: keys.list })
      const previous = queryClient.getQueryData<Application[]>(keys.list)
      queryClient.setQueryData<Application[]>(keys.list, (apps) =>
        apps?.map((a) => (a.id === id ? ({ ...a, ...body } as Application) : a)),
      )
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(keys.list, context.previous)
    },
    onSuccess: (detail) => queryClient.setQueryData(keys.detail(detail.id), detail),
    onSettled: invalidate,
  })
}

export function useDeleteApplication() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.DELETE('/api/applications/{application_id}', { params: { path: { application_id: id } } })),
    onSuccess: invalidate,
  })
}

export function useAddNote() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note: string }) =>
      unwrap(
        await api.POST('/api/applications/{application_id}/events', {
          params: { path: { application_id: id } },
          body: { note },
        }),
      ),
    onSuccess: (_event, { id }) => queryClient.invalidateQueries({ queryKey: keys.detail(id) }),
  })
}
