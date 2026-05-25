import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { courses, type Curriculum } from '@/lib/api'
import ObjectiveTree from './ObjectiveTree'

const FORMAT_EXAMPLES = {
  markdown: `# Nöroloji Klerkliği

## 1. Serebrovasküler Hastalıklar
### 1.1 İskemik İnme
- 1.1.1 Tanım ve epidemiyoloji
- 1.1.2 Akut tedavi ve tPA penceresi
### 1.2 Hemorajik İnme
- 1.2.1 İntraserebral kanama yönetimi

## 2. Epilepsi
### 2.1 Status epileptikus tedavisi`,
  json: `{
  "title": "Nöroloji Klerkliği",
  "objectives": [
    {
      "code": "1",
      "text": "Serebrovasküler Hastalıklar",
      "children": [
        {
          "code": "1.1",
          "text": "İskemik inme tanı ve tedavisi",
          "bloom_level": "apply"
        }
      ]
    }
  ]
}`,
}

export default function CurriculumTab({ courseId }: { courseId: string }) {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [format, setFormat] = useState<'markdown' | 'json'>('markdown')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: curricula, isLoading } = useQuery({
    queryKey: ['curricula', courseId],
    queryFn: () => courses.listCurricula(courseId),
  })

  const createMut = useMutation({
    mutationFn: () =>
      courses.createCurriculum(courseId, {
        title: title || 'Müfredat',
        source_format: format,
        raw_content: content,
      }),
    onSuccess: (newCurriculum) => {
      qc.invalidateQueries({ queryKey: ['curricula', courseId] })
      setAdding(false)
      setContent('')
      setTitle('')
      setExpandedId(newCurriculum.id)
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => courses.deleteCurriculum(courseId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['curricula', courseId] }),
  })

  function countObjectives(objectives: Curriculum['objectives']): number {
    return objectives.reduce((sum, o) => sum + 1 + countObjectives(o.children), 0)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium">Müfredat / Kazanımlar</h2>
        <button
          onClick={() => setAdding(true)}
          className="px-3 py-1.5 bg-slate-900 text-white rounded text-sm hover:bg-slate-700 transition-colors"
        >
          + Müfredat Ekle
        </button>
      </div>

      {adding && (
        <div className="mb-6 border rounded-lg p-4 bg-slate-50">
          <h3 className="font-medium mb-3">Yeni Müfredat</h3>

          <div className="mb-3">
            <input
              className="w-full border rounded px-3 py-2 text-sm bg-white"
              placeholder="Müfredat başlığı (örn. Nöroloji Klerkliği)"
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
          </div>

          <div className="flex gap-2 mb-3">
            {(['markdown', 'json'] as const).map(f => (
              <button
                key={f}
                onClick={() => { setFormat(f); setContent('') }}
                className={`px-3 py-1 rounded text-sm border transition-colors ${
                  format === f
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-600 hover:border-slate-400'
                }`}
              >
                {f === 'markdown' ? 'Markdown / Serbest metin' : 'JSON'}
              </button>
            ))}
          </div>

          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {format === 'markdown'
                ? 'Tıp fakültesi müfredatını yapıştır — DeepSeek otomatik parse eder'
                : 'Yapısal JSON formatı'}
            </span>
            <button
              onClick={() => setContent(FORMAT_EXAMPLES[format])}
              className="text-xs text-blue-600 hover:underline"
            >
              Örnek yükle
            </button>
          </div>

          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono bg-white resize-y"
            rows={12}
            placeholder={format === 'markdown' ? '# Ders Adı\n## Konu\n- Alt konu' : '{ "objectives": [...] }'}
            value={content}
            onChange={e => setContent(e.target.value)}
          />

          <div className="flex gap-2 mt-3">
            <button
              onClick={() => createMut.mutate()}
              disabled={!content.trim() || createMut.isPending}
              className="px-4 py-2 bg-slate-900 text-white rounded text-sm disabled:opacity-50 flex items-center gap-2"
            >
              {createMut.isPending && (
                <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )}
              {createMut.isPending ? 'Parse ediliyor...' : 'Kaydet'}
            </button>
            <button
              onClick={() => { setAdding(false); setContent(''); setTitle('') }}
              className="px-4 py-2 border rounded text-sm hover:bg-slate-100"
            >
              İptal
            </button>
          </div>

          {createMut.isError && (
            <p className="text-red-500 text-sm mt-2">
              {(createMut.error as Error).message}
            </p>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="text-slate-400 text-sm">Yükleniyor...</div>
      ) : !curricula?.length ? (
        <div className="text-center py-12 text-slate-400">
          <p className="mb-1">Henüz müfredat yok</p>
          <p className="text-sm">Tıp fakültesi müfredatını yapıştırarak ekleyebilirsin</p>
        </div>
      ) : (
        <div className="space-y-3">
          {curricula.map((c: Curriculum) => {
            const isExpanded = expandedId === c.id
            const total = countObjectives(c.objectives)
            return (
              <div key={c.id} className="border rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50"
                  onClick={() => setExpandedId(isExpanded ? null : c.id)}
                >
                  <div>
                    <span className="font-medium">{c.title}</span>
                    <span className="ml-2 text-xs text-slate-400">
                      {total} kazanım · {c.source_format}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={e => { e.stopPropagation(); deleteMut.mutate(c.id) }}
                      className="text-xs text-red-400 hover:text-red-600 px-2 py-1"
                    >
                      Sil
                    </button>
                    <span className="text-slate-400 text-sm">{isExpanded ? '▲' : '▼'}</span>
                  </div>
                </div>
                {isExpanded && (
                  <div className="px-4 pb-4 pt-1 border-t">
                    <ObjectiveTree objectives={c.objectives} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
