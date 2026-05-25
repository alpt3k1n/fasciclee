import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { courses, type Source } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  pending: 'Bekliyor',
  processing: 'İşleniyor',
  processed: 'İşlendi',
  indexed: 'İndekslendi',
  failed: 'Hata',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  processed: 'bg-teal-100 text-teal-800',
  indexed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

const TYPE_ICON: Record<string, string> = {
  pdf: '📄',
  audio: '🎵',
  video: '🎬',
  youtube: '▶️',
  image: '🖼️',
  text: '📝',
  curriculum: '📋',
}

export default function CourseDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [ytUrl, setYtUrl] = useState('')
  const [showYt, setShowYt] = useState(false)

  const { data: course } = useQuery({
    queryKey: ['courses', id],
    queryFn: () => courses.get(id!),
    enabled: !!id,
  })

  const { data: sources, isLoading: loadingSources } = useQuery({
    queryKey: ['courses', id, 'sources'],
    queryFn: () => courses.listSources(id!),
    enabled: !!id,
    refetchInterval: (data) =>
      data?.state.data?.some(s => s.status === 'pending' || s.status === 'processing') ? 3000 : false,
  })

  const uploadMut = useMutation({
    mutationFn: (file: File) => courses.uploadSource(id!, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['courses', id, 'sources'] }),
  })

  const ytMut = useMutation({
    mutationFn: (url: string) => courses.addYouTube(id!, url),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courses', id, 'sources'] })
      setYtUrl('')
      setShowYt(false)
    },
  })

  const onFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    Array.from(e.dataTransfer.files).forEach(f => uploadMut.mutate(f))
  }

  if (!course) return <div className="text-slate-500">Yükleniyor...</div>

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{course.name}</h1>
        {course.description && <p className="text-slate-500 mt-1">{course.description}</p>}
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-medium mb-3">Kaynaklar</h2>

        <div
          onDrop={onFileDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center cursor-pointer hover:border-slate-400 hover:bg-slate-50 transition-colors mb-4"
        >
          <div className="text-slate-500 text-sm">
            Dosya sürükle & bırak veya tıkla
            <br />
            <span className="text-xs text-slate-400">PDF, MP3, MP4, görsel, metin — aynı anda birden fazla</span>
          </div>
          <input
            ref={fileRef}
            type="file"
            multiple
            className="hidden"
            onChange={e => Array.from(e.target.files || []).forEach(f => uploadMut.mutate(f))}
          />
        </div>

        <div className="mb-4">
          {!showYt ? (
            <button
              onClick={() => setShowYt(true)}
              className="text-sm text-slate-600 hover:text-slate-900 border rounded px-3 py-1.5"
            >
              + YouTube linki ekle
            </button>
          ) : (
            <div className="flex gap-2">
              <input
                className="border rounded px-3 py-2 text-sm flex-1"
                placeholder="https://youtube.com/watch?v=..."
                value={ytUrl}
                onChange={e => setYtUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && ytUrl && ytMut.mutate(ytUrl)}
              />
              <button
                onClick={() => ytMut.mutate(ytUrl)}
                disabled={!ytUrl || ytMut.isPending}
                className="px-4 py-2 bg-slate-900 text-white rounded text-sm disabled:opacity-50"
              >
                Ekle
              </button>
              <button onClick={() => setShowYt(false)} className="px-3 py-2 border rounded text-sm">
                İptal
              </button>
            </div>
          )}
        </div>

        {loadingSources ? (
          <div className="text-slate-400 text-sm">Yükleniyor...</div>
        ) : !sources?.length ? (
          <div className="text-slate-400 text-sm">Henüz kaynak yok</div>
        ) : (
          <div className="space-y-2">
            {sources.map((s: Source) => (
              <div key={s.id} className="flex items-center gap-3 p-3 border rounded-lg">
                <span className="text-lg">{TYPE_ICON[s.type] || '📁'}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {s.original_filename || s.external_url || s.type}
                  </div>
                  {s.error_message && (
                    <div className="text-xs text-red-500">{s.error_message}</div>
                  )}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[s.status]}`}>
                  {STATUS_LABEL[s.status]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

