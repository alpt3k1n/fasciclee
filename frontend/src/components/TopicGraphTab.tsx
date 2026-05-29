import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { courses, type TopicNodeOut, type GapReportItem } from '@/lib/api'

const STATUS_CONFIG = {
  auto:        { label: 'Otomatik', color: 'bg-slate-100 text-slate-600' },
  user_edited: { label: 'Düzenlendi', color: 'bg-blue-100 text-blue-700' },
  approved:    { label: 'Onaylandı', color: 'bg-green-100 text-green-700' },
}

const SEVERITY_CONFIG = {
  high:   { label: 'Yüksek', color: 'text-red-600 bg-red-50 border-red-200' },
  medium: { label: 'Orta', color: 'text-orange-600 bg-orange-50 border-orange-200' },
  low:    { label: 'Düşük', color: 'text-yellow-600 bg-yellow-50 border-yellow-200' },
}

function ConfidenceDot({ value }: { value: number | null }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  const color = value >= 0.7 ? 'bg-green-500' : value >= 0.4 ? 'bg-yellow-500' : 'bg-red-400'
  return (
    <span title={`Kaynak güveni: %${pct}`} className={`inline-block w-2 h-2 rounded-full ${color} shrink-0 mt-1.5`} />
  )
}

function NodeRow({
  node,
  depth,
  courseId,
  onRefresh,
}: {
  node: TopicNodeOut
  depth: number
  courseId: string
  onRefresh: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(node.title)
  const [summary, setSummary] = useState(node.summary ?? '')
  const [expanded, setExpanded] = useState(depth < 2)

  const approveMut = useMutation({
    mutationFn: () => courses.approveNode(courseId, node.id),
    onSuccess: onRefresh,
  })
  const updateMut = useMutation({
    mutationFn: () => courses.updateNode(courseId, node.id, { title, summary }),
    onSuccess: () => { setEditing(false); onRefresh() },
  })
  const deleteMut = useMutation({
    mutationFn: () => courses.deleteNode(courseId, node.id),
    onSuccess: onRefresh,
  })

  const cfg = STATUS_CONFIG[node.status] ?? STATUS_CONFIG.auto

  return (
    <div>
      <div
        className="flex items-start gap-2 py-2 px-3 rounded-lg hover:bg-slate-50 group"
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
      >
        {/* Expand toggle */}
        {node.children.length > 0 ? (
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-slate-400 text-xs mt-0.5 w-4 shrink-0"
          >
            {expanded ? '▼' : '▶'}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}

        <ConfidenceDot value={node.ai_confidence} />

        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="space-y-1.5">
              <input
                className="w-full border rounded px-2 py-1 text-sm"
                value={title}
                onChange={e => setTitle(e.target.value)}
                autoFocus
              />
              <textarea
                className="w-full border rounded px-2 py-1 text-xs text-slate-600 resize-none"
                rows={2}
                placeholder="Özet (opsiyonel)"
                value={summary}
                onChange={e => setSummary(e.target.value)}
              />
              <div className="flex gap-1.5">
                <button
                  onClick={() => updateMut.mutate()}
                  disabled={updateMut.isPending}
                  className="text-xs px-2 py-1 bg-slate-900 text-white rounded"
                >
                  Kaydet
                </button>
                <button
                  onClick={() => { setEditing(false); setTitle(node.title); setSummary(node.summary ?? '') }}
                  className="text-xs px-2 py-1 border rounded"
                >
                  İptal
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium">{node.title}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cfg.color}`}>
                  {cfg.label}
                </span>
                {node.objective_codes.length > 0 && (
                  <span className="text-xs text-slate-400">
                    {node.objective_codes.slice(0, 3).join(', ')}
                    {node.objective_codes.length > 3 && ` +${node.objective_codes.length - 3}`}
                  </span>
                )}
              </div>
              {node.summary && (
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{node.summary}</p>
              )}
            </>
          )}
        </div>

        {/* Actions — visible on hover */}
        {!editing && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            {node.status !== 'approved' && (
              <button
                onClick={() => approveMut.mutate()}
                disabled={approveMut.isPending}
                className="text-xs px-2 py-1 border border-green-400 text-green-700 rounded hover:bg-green-50"
              >
                Onayla
              </button>
            )}
            <button
              onClick={() => setEditing(true)}
              className="text-xs px-2 py-1 border rounded hover:bg-slate-100"
            >
              Düzenle
            </button>
            <button
              onClick={() => deleteMut.mutate()}
              className="text-xs px-2 py-1 text-red-400 hover:text-red-600"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {expanded && node.children.map(child => (
        <NodeRow key={child.id} node={child} depth={depth + 1} courseId={courseId} onRefresh={onRefresh} />
      ))}
    </div>
  )
}

export default function TopicGraphTab({ courseId }: { courseId: string }) {
  const [showGap, setShowGap] = useState(false)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['topic-graph', courseId],
    queryFn: () => courses.getTopicGraph(courseId),
    refetchInterval: (q) =>
      q.state.data?.extraction_status === 'running' ? 4000 : false,
  })

  const extractMut = useMutation({
    mutationFn: () => courses.extractTopicGraph(courseId),
    onSuccess: () => refetch(),
  })

  const approveAllMut = useMutation({
    mutationFn: () => courses.approveAll(courseId),
    onSuccess: () => refetch(),
  })

  const refresh = () => refetch()

  const totalNodes = countAll(data?.nodes ?? [])
  const approvedNodes = countApproved(data?.nodes ?? [])
  const highGaps = data?.gap_report.filter(g => g.severity === 'high').length ?? 0

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-medium">Konu Grafiği</h2>
          {data?.extraction_status === 'done' && totalNodes > 0 && (
            <p className="text-sm text-slate-500 mt-0.5">
              {totalNodes} konu · {approvedNodes} onaylandı
              {highGaps > 0 && <span className="text-red-500 ml-2">· {highGaps} kritik boşluk</span>}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {data?.extraction_status === 'done' && totalNodes > 0 && !data.all_approved && (
            <button
              onClick={() => approveAllMut.mutate()}
              disabled={approveAllMut.isPending}
              className="px-3 py-1.5 border border-green-500 text-green-700 rounded text-sm hover:bg-green-50"
            >
              Tümünü Onayla
            </button>
          )}
          <button
            onClick={() => extractMut.mutate()}
            disabled={extractMut.isPending || data?.extraction_status === 'running'}
            className="px-3 py-1.5 bg-slate-900 text-white rounded text-sm hover:bg-slate-700 disabled:opacity-50 flex items-center gap-2"
          >
            {data?.extraction_status === 'running' && (
              <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            {data?.extraction_status === 'running'
              ? 'Çıkarılıyor...'
              : data?.extraction_status === 'done'
              ? 'Yeniden Çıkar'
              : 'Konu Grafiği Çıkar'}
          </button>
        </div>
      </div>

      {/* All-approved banner */}
      {data?.all_approved && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800 flex items-center gap-2">
          <span>✓</span>
          <span>Tüm konular onaylandı — fasikül üretimine geçebilirsin.</span>
        </div>
      )}

      {/* Status states */}
      {isLoading ? (
        <div className="text-slate-400 text-sm">Yükleniyor...</div>
      ) : data?.extraction_status === 'running' ? (
        <div className="text-center py-12">
          <div className="w-8 h-8 border-4 border-slate-300 border-t-slate-700 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-600">DeepSeek konu grafiğini çıkarıyor...</p>
          <p className="text-slate-400 text-sm mt-1">Bu 30-60 saniye sürebilir</p>
        </div>
      ) : data?.extraction_status === 'failed' ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Çıkarma başarısız oldu. Kaynak ve müfredat eklendiğinden emin olup tekrar dene.
        </div>
      ) : !data?.nodes.length ? (
        <div className="text-center py-12 text-slate-400">
          <p className="mb-1">Konu grafiği henüz yok</p>
          <p className="text-sm">Kaynak ve müfredat ekledikten sonra "Konu Grafiği Çıkar" butonuna bas</p>
        </div>
      ) : (
        <>
          {/* Node tree */}
          <div className="border rounded-lg mb-4 divide-y overflow-hidden">
            {data.nodes.map(node => (
              <NodeRow key={node.id} node={node} depth={0} courseId={courseId} onRefresh={refresh} />
            ))}
          </div>

          {/* Gap report */}
          {data.gap_report.length > 0 && (
            <div>
              <button
                onClick={() => setShowGap(g => !g)}
                className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-2"
              >
                <span>{showGap ? '▼' : '▶'}</span>
                Gap Report ({data.gap_report.length} boşluk
                {highGaps > 0 && <span className="text-red-500">, {highGaps} kritik</span>})
              </button>
              {showGap && (
                <div className="space-y-2">
                  {data.gap_report.map((g: GapReportItem, i: number) => {
                    const sc = SEVERITY_CONFIG[g.severity] ?? SEVERITY_CONFIG.low
                    return (
                      <div key={i} className={`p-3 border rounded-lg text-sm ${sc.color}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-xs font-medium">{g.objective_code}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${sc.color}`}>
                            {sc.label}
                          </span>
                        </div>
                        <p className="font-medium">{g.objective_text}</p>
                        <p className="text-xs mt-0.5 opacity-80">{g.issue}</p>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function countAll(nodes: TopicNodeOut[]): number {
  return nodes.reduce((s, n) => s + 1 + countAll(n.children), 0)
}

function countApproved(nodes: TopicNodeOut[]): number {
  return nodes.reduce((s, n) =>
    s + (n.status === 'approved' ? 1 : 0) + countApproved(n.children), 0)
}
