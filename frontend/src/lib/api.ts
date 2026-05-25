import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

export interface Course {
  id: string
  name: string
  description: string | null
  language: string
  created_at: string
  updated_at: string
}

export interface Source {
  id: string
  course_id: string
  type: 'pdf' | 'audio' | 'video' | 'youtube' | 'image' | 'text' | 'curriculum'
  status: 'pending' | 'processing' | 'processed' | 'indexed' | 'failed'
  original_filename: string | null
  storage_key: string | null
  external_url: string | null
  metadata_: Record<string, unknown>
  error_message: string | null
  uploaded_at: string
  processed_at: string | null
  indexed_at: string | null
}

export interface SectionOut {
  id: string
  topic_node_id: string
  topic_node_title: string
  position: number | null
  status: string
  retry_count: number
  pass1_outline: Record<string, unknown> | null
  pass2_expanded_md: string | null
  pass3_enriched_md: string | null
  pass4_questions_md: string | null
  final_md: string | null
  generated_at: string | null
}

export interface GenerationOut {
  id: string
  course_id: string
  status: string
  config: Record<string, unknown>
  started_at: string
  completed_at: string | null
  error_message: string | null
  sections: SectionOut[]
}

export interface Artifact {
  id: string
  type: 'markdown' | 'html' | 'pdf'
  storage_key: string
  size_bytes: number | null
  created_at: string | null
  url: string | null
}

export interface GenerationConfig {
  depth: string
  language: string
  test_question_count: number
  include_clinical_correlations: boolean
}

export interface TopicNodeOut {
  id: string
  parent_id: string | null
  title: string
  summary: string | null
  position: number | null
  status: 'auto' | 'user_edited' | 'approved'
  ai_confidence: number | null
  objective_codes: string[]
  children: TopicNodeOut[]
}

export interface GapReportItem {
  objective_code: string
  objective_text: string
  issue: string
  severity: 'high' | 'medium' | 'low'
}

export interface TopicGraphOut {
  extraction_status: string | null
  nodes: TopicNodeOut[]
  gap_report: GapReportItem[]
  all_approved: boolean
}

export interface Objective {
  id: string
  parent_id: string | null
  code: string | null
  text: string
  bloom_level: string | null
  position: number | null
  children: Objective[]
}

export interface Curriculum {
  id: string
  course_id: string
  title: string
  source_format: string | null
  created_at: string
  objectives: Objective[]
}

export const courses = {
  list: () => api.get<Course[]>('/courses').then(r => r.data),
  get: (id: string) => api.get<Course>(`/courses/${id}`).then(r => r.data),
  create: (data: { name: string; description?: string; language?: string }) =>
    api.post<Course>('/courses', data).then(r => r.data),
  update: (id: string, data: Partial<{ name: string; description: string; language: string }>) =>
    api.patch<Course>(`/courses/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/courses/${id}`),

  listSources: (courseId: string) =>
    api.get<Source[]>(`/courses/${courseId}/sources`).then(r => r.data),
  uploadSource: (courseId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Source>(`/courses/${courseId}/sources/upload`, form).then(r => r.data)
  },
  addYouTube: (courseId: string, url: string) =>
    api.post<Source>(`/courses/${courseId}/sources/youtube`, { url }).then(r => r.data),
  deleteSource: (courseId: string, sourceId: string) =>
    api.delete(`/courses/${courseId}/sources/${sourceId}`),
  retrySource: (courseId: string, sourceId: string) =>
    api.post<Source>(`/courses/${courseId}/sources/${sourceId}/retry`).then(r => r.data),

  listGenerations: (courseId: string) =>
    api.get<GenerationOut[]>(`/courses/${courseId}/generations`).then(r => r.data),
  startGeneration: (courseId: string, config?: Partial<GenerationConfig>) =>
    api.post<GenerationOut>(`/courses/${courseId}/generate`, config ?? {}).then(r => r.data),
  getGeneration: (generationId: string) =>
    api.get<GenerationOut>(`/generations/${generationId}`).then(r => r.data),
  cancelGeneration: (generationId: string) =>
    api.post(`/generations/${generationId}/cancel`),
  compileGeneration: (generationId: string) =>
    api.post(`/generations/${generationId}/compile`).then(r => r.data),
  listArtifacts: (generationId: string) =>
    api.get<Artifact[]>(`/generations/${generationId}/artifacts`).then(r => r.data),

  getTopicGraph: (courseId: string) =>
    api.get<TopicGraphOut>(`/courses/${courseId}/topic-graph`).then(r => r.data),
  extractTopicGraph: (courseId: string) =>
    api.post(`/courses/${courseId}/extract-topic-graph`).then(r => r.data),
  approveNode: (courseId: string, nodeId: string) =>
    api.post<TopicNodeOut>(`/courses/${courseId}/topic-graph/${nodeId}/approve`).then(r => r.data),
  approveAll: (courseId: string) =>
    api.post(`/courses/${courseId}/topic-graph/approve-all`),
  updateNode: (courseId: string, nodeId: string, data: Partial<{ title: string; summary: string; status: string }>) =>
    api.patch<TopicNodeOut>(`/courses/${courseId}/topic-graph/${nodeId}`, data).then(r => r.data),
  deleteNode: (courseId: string, nodeId: string) =>
    api.delete(`/courses/${courseId}/topic-graph/${nodeId}`),
  createNode: (courseId: string, data: { title: string; parent_id?: string }) =>
    api.post<TopicNodeOut>(`/courses/${courseId}/topic-graph/nodes`, data).then(r => r.data),

  listCurricula: (courseId: string) =>
    api.get<Curriculum[]>(`/courses/${courseId}/curriculum`).then(r => r.data),
  createCurriculum: (courseId: string, data: { title: string; source_format: string; raw_content: string }) =>
    api.post<Curriculum>(`/courses/${courseId}/curriculum`, data).then(r => r.data),
  deleteCurriculum: (courseId: string, curriculumId: string) =>
    api.delete(`/courses/${courseId}/curriculum/${curriculumId}`),
}
