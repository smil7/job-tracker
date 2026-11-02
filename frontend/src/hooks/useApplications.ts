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

const aiKeys = {
  profile: ['profile'] as const,
  review: (id: string) => ['applications', id, 'review'] as const,
  letter: (id: string) => ['applications', id, 'cover-letter'] as const,
}

export function useProfile() {
  return useQuery({
    queryKey: aiKeys.profile,
    queryFn: async () => unwrap(await api.GET('/api/profile')),
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (about_me: string | null) => unwrap(await api.PUT('/api/profile', { body: { about_me } })),
    onSuccess: (profile) => queryClient.setQueryData(aiKeys.profile, profile),
  })
}

export function useUploadResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.PUT('/api/profile/resume', {
          // The generated type says `string`, but the wire format is a multipart file
          body: { file } as unknown as { file: string },
          bodySerializer: () => {
            const data = new FormData()
            data.append('file', file)
            return data
          },
        }),
      ),
    onSuccess: (profile) => queryClient.setQueryData(aiKeys.profile, profile),
  })
}

/** The latest review, or null when none has been run yet (the API answers 404). */
export function useResumeReview(id: string) {
  return useQuery({
    queryKey: aiKeys.review(id),
    queryFn: async () => {
      const result = await api.GET('/api/applications/{application_id}/review', {
        params: { path: { application_id: id } },
      })
      if (result.response.status === 404) return null
      return unwrap(result)
    },
  })
}

export function useRunReview(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/applications/{application_id}/review', { params: { path: { application_id: id } } })),
    onSuccess: (review) => queryClient.setQueryData(aiKeys.review(id), review),
  })
}

export function useCoverLetter(id: string) {
  return useQuery({
    queryKey: aiKeys.letter(id),
    queryFn: async () => {
      const result = await api.GET('/api/applications/{application_id}/cover-letter', {
        params: { path: { application_id: id } },
      })
      if (result.response.status === 404) return null
      return unwrap(result)
    },
  })
}

export function useGenerateCoverLetter(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (instructions: string | null) =>
      unwrap(
        await api.POST('/api/applications/{application_id}/cover-letter', {
          params: { path: { application_id: id } },
          body: { instructions },
        }),
      ),
    onSuccess: (letter) => queryClient.setQueryData(aiKeys.letter(id), letter),
  })
}

export function useSaveCoverLetter(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (content: string) =>
      unwrap(
        await api.PUT('/api/applications/{application_id}/cover-letter', {
          params: { path: { application_id: id } },
          body: { content },
        }),
      ),
    onSuccess: (letter) => queryClient.setQueryData(aiKeys.letter(id), letter),
  })
}
