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
}
