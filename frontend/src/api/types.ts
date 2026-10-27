import type { components } from './schema'

type Schemas = components['schemas']

export type Application = Schemas['ApplicationRead']
export type ApplicationDetail = Schemas['ApplicationDetail']
export type ApplicationCreate = Schemas['ApplicationCreate']
export type ApplicationUpdate = Schemas['ApplicationUpdate']
export type StatusEvent = Schemas['EventRead']
export type Status = Schemas['ApplicationStatus']
export type JobType = Schemas['JobType']
export type Stats = Schemas['Stats']
