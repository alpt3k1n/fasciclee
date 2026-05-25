import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { courses, type GenerationOut, type SectionOut, type Artifact } from '@/lib/api'

const SECTION_PASSES = [
  { key: 'pass1_done', label: 'Outline' },
  { key: 'pass2_done', label: 'Genişlet' },
  { key: 'pass3_done', label: 'Zenginleştir' },
  { key: 'pass4_done', label: 'Sorular' },
  { key: 'completed', label: 'QA ✓' },
]

const PASS_ORDER = ['pending', 'pass1_done', 'pass2_done', 'pass3_done', 'pass4_done', 'completed', 'failed']

const GEN_STATUS_COLOR: Record<string, string> = {
  generating: 'text-blue-700 bg-blue-50',
  qa_running: 'text-violet-700 bg-violet-50',
  completed: 'text-green-700 bg-green-50',
  compiling: 'text-amber-700 bg-amber-50',
  failed: 'text-red-700 bg-red-50',
  cancelled: 'text-slate-500 bg-slate-100',
  planning: 'text-slate-600 bg-slate-50',
}

const GEN_STATUS_LABEL: Record<string, string> = {
  generating: 'Üretiliyor',
  qa_running: 'QA',
  completed: 'Tamamlandı',
  compiling: 'Derleniyor',
  failed: 'Hata',
  cancelled: 'İptal',
  planning: 'Planlıyor',
}

const ARTIFACT_LABEL: Record<string, string> = {
  markdown: 'MD',
  html: 'HTML',
  pdf: 'PDF',
}

const ARTIFACT_COLOR: Record<string, string> = {
  markdown: 'text-slate-700 border-slate-300 hover:bg-slate-50',
  html: 'text-blue-700 border-blue-300 hover:bg-blue-50',
  pdf: 'text-red-700 border-red-300 hover:bg-red-50',
}

function passIndex(status: string) {
  return PASS_ORDER.indexOf(status)
}

function SectionRow({ section }: { section: SectionOut }) {
  const [showPreview, setShowPreview] = useState(false)
  const done = section.status === 'completed'
  const failed = section.status === 'failed'
  const currentPassIdx = passIndex(section.status)

  return (
    <div className={`border rounded-lg p-3 ${failed ? 'border-red-200 bg-red-50' : ''}`}>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-sm font-medium flex-1 truncate">{section.topic_node_title}</span>
        {section.retry_count > 0 && (
          <span className="text-xs text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded">
            {section.retry_count} retry
          </span>
        )}
        {done && section.final_md && (
          <button
            onClick={() => setShowPreview(p => !p)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showPreview ? 'Gizle' : 'Önizle'}
          </button>
        )}
      </div>

      {/* Pass progress bar */}
      <div className="flex gap-1">
        {SECTION_PASSES.map((pass, i) => {
          const reached = currentPassIdx > i || done
          const current = !done && !failed && currentPassIdx === i
          return (
            <div key={pass.key} className="flex-1">
              <div
                className={`h-1.5 rounded-full transition-colors ${
                  done ? 'bg-green-500' :
                  failed && i === currentPassIdx ? 'bg-red-400' :
                  reached ? 'bg-blue-500' :
                  current ? 'bg-blue-300 animate-pulse' :
                  'bg-slate-200'
                }`}
              />
              <div className={`text-[10px] mt-0.5 text-center truncate ${
                reached || done ? 'text-slate-600' : 'text-slate-400'
              }`}>
                {pass.label}
              </div>
            </div>
          )
        })}
      </div>

      {/* Content preview */}
      {showPreview && section.final_md && (
        <div className="mt-3 p-3 bg-white border rounded text-xs font-mono text-slate-700 max-h-48 overflow-y-auto whitespace-pre-wrap">
          {section.final_md.slice(0, 1500)}
          {section.final_md.length > 1500 && '\n…'}
        </div>
      )}
    </div>
  )
}

function ArtifactBar({ generationId }: { generationId: string }) {
  const { data: artifacts, isLoading } = useQuery({
    queryKey: ['artifacts', generationId],
    queryFn: () => courses.listArtifacts(generationId),
    staleTime: 30_000,
  })

  if (isLoading) return <span className="text-xs text-slate-400">Yükleniyor...</span>
  if (!artifacts?.length) return <span className="text-xs text-slate-400">Henüz artifact yok</span>

  return (
    <div className="flex gap-2 flex-wrap">
      {artifacts.map((art: Artifact) => (
        art.url ? (
          <a
            key={art.id}
            href={art.url}
            target="_blank"
            rel="noreferrer"
            className={`text-xs px-3 py-1 border rounded font-medium ${ARTIFACT_COLOR[art.type] ?? ''}`}
          >
            ↓ {ARTIFACT_LABEL[art.type] ?? art.type}
            {art.size_bytes ? ` (${(art.size_bytes / 1024).toFixed(0)} KB)` : ''}
          </a>
        ) : (
          <span key={art.id} className="text-xs text-slate-400">
            {ARTIFACT_LABEL[art.type] ?? art.type} (URL yok)
          </span>
        )
      ))}
    </div>
  )
}

function GenerationCard({
  gen,
  courseId,
  isActive,
}: {
  gen: GenerationOut
  courseId: string
  isActive: boolean
}) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(isActive)
  const [showArtifacts, setShowArtifacts] = useState(false)

  const cancelMut = useMutation({
    mutationFn: () => courses.cancelGeneration(gen.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generations', courseId] }),
  })

  const compileMut = useMutation({
    mutationFn: () => courses.compileGeneration(gen.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['generations', courseId] })
      setShowArtifacts(true)
    },
  })

  const completedSections = gen.sections.filter(s => s.status === 'completed').length
  const totalSections = gen.sections.length
  const running = gen.status === 'generating' || gen.status === 'qa_running'
  const compiling = gen.status === 'compiling'
  const canCompile = gen.status === 'completed' || gen.status === 'failed'

  return (
    <div className="border rounded-lg overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50"
        onClick={() => setExpanded(e => !e)}
      >
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${GEN_STATUS_COLOR[gen.status] ?? ''}`}>
          {GEN_STATUS_LABEL[gen.status] ?? gen.status}
        </span>
        <span className="text-sm flex-1">
          {new Date(gen.started_at).toLocaleString('tr-TR')}
        </span>
        {totalSections > 0 && (
          <span className="text-xs text-slate-500">
            {completedSections}/{totalSections} bölüm
          </span>
        )}
        {(running || compiling) && (
          <span className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        )}
        {running && (
          <button
            onClick={e => { e.stopPropagation(); cancelMut.mutate() }}
            className="text-xs text-red-500 hover:text-red-700 border border-red-200 rounded px-2 py-0.5"
          >
            İptal
          </button>
        )}
        <span className="text-slate-400 text-sm">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="border-t px-4 py-3 space-y-2">
          {gen.error_message && (
            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{gen.error_message}</div>
          )}
          {gen.sections.map(s => (
            <SectionRow key={s.id} section={s} />
          ))}

          {canCompile && (
            <div className="pt-3 border-t flex items-center gap-3 flex-wrap">
              <button
                onClick={() => compileMut.mutate()}
                disabled={compileMut.isPending || compiling}
                className="text-sm px-3 py-1.5 bg-slate-800 text-white rounded hover:bg-slate-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {compileMut.isPending && (
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                Derle (PDF + HTML)
              </button>
              <button
                onClick={() => setShowArtifacts(a => !a)}
                className="text-sm text-blue-600 hover:underline"
              >
                {showArtifacts ? 'İndir ▲' : 'İndir ▼'}
              </button>
              {compileMut.isError && (
                <span className="text-xs text-red-600">Derleme başlatılamadı</span>
              )}
            </div>
          )}

          {showArtifacts && canCompile && (
            <div className="pt-1">
              <ArtifactBar generationId={gen.id} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function GenerationTab({ courseId }: { courseId: string }) {
  const qc = useQueryClient()

  const { data: generations, isLoading } = useQuery({
    queryKey: ['generations', courseId],
    queryFn: () => courses.listGenerations(courseId),
    refetchInterval: (q) => {
      const gens = q.state.data ?? []
      const active = ['generating', 'qa_running', 'compiling', 'planning']
      return gens.some(g => active.includes(g.status)) ? 5000 : false
    },
  })

  const startMut = useMutation({
    mutationFn: () => courses.startGeneration(courseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generations', courseId] }),
  })

  const active = generations?.find(g =>
    ['generating', 'qa_running', 'compiling', 'planning'].includes(g.status)
  )
  const hasActive = !!active

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-medium">Fasikül Üretimi</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Konu grafiği onaylandıktan sonra üretimi başlat
          </p>
        </div>
        <button
          onClick={() => startMut.mutate()}
          disabled={startMut.isPending || hasActive}
          className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm hover:bg-slate-700 disabled:opacity-50 flex items-center gap-2"
        >
          {startMut.isPending && (
            <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {hasActive ? 'Üretim Devam Ediyor' : '+ Fasikül Üret'}
        </button>
      </div>

      {startMut.isError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {(startMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Hata oluştu'}
        </div>
      )}

      {isLoading ? (
        <div className="text-slate-400 text-sm">Yükleniyor...</div>
      ) : !generations?.length ? (
        <div className="text-center py-12 text-slate-400">
          <p className="mb-1">Henüz üretim yok</p>
          <p className="text-sm">Konu grafiğini onayladıktan sonra fasikül üretimini başlat</p>
        </div>
      ) : (
        <div className="space-y-3">
          {generations.map((gen: GenerationOut) => (
            <GenerationCard
              key={gen.id}
              gen={gen}
              courseId={courseId}
              isActive={gen.id === active?.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
