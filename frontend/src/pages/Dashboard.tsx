import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { courses, type Course } from '@/lib/api'

export default function Dashboard() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['courses'], queryFn: courses.list })
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', language: 'tr' })

  const create = useMutation({
    mutationFn: () => courses.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courses'] })
      setCreating(false)
      setForm({ name: '', description: '', language: 'tr' })
    },
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Derslerim</h1>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm hover:bg-slate-700 transition-colors"
        >
          + Yeni Ders
        </button>
      </div>

      {creating && (
        <div className="mb-6 p-4 border rounded-lg bg-slate-50">
          <h2 className="font-medium mb-3">Yeni Ders Oluştur</h2>
          <div className="space-y-3">
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Ders adı (örn. Nöroloji Klerkliği)"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Açıklama (opsiyonel)"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
            <select
              className="border rounded px-3 py-2 text-sm"
              value={form.language}
              onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
            >
              <option value="tr">Türkçe</option>
              <option value="en">English</option>
            </select>
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || create.isPending}
              className="px-4 py-2 bg-slate-900 text-white rounded text-sm disabled:opacity-50"
            >
              {create.isPending ? 'Oluşturuluyor...' : 'Oluştur'}
            </button>
            <button
              onClick={() => setCreating(false)}
              className="px-4 py-2 border rounded text-sm hover:bg-slate-100"
            >
              İptal
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="text-slate-500 text-sm">Yükleniyor...</div>
      ) : !data?.length ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg mb-2">Henüz ders yok</p>
          <p className="text-sm">Yeni ders oluşturarak başla</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((c: Course) => (
            <Link
              key={c.id}
              to={`/courses/${c.id}`}
              className="p-4 border rounded-lg hover:border-slate-400 hover:shadow-sm transition-all"
            >
              <div className="font-medium mb-1">{c.name}</div>
              {c.description && <div className="text-sm text-slate-500 mb-2">{c.description}</div>}
              <div className="text-xs text-slate-400">
                {c.language === 'tr' ? 'Türkçe' : 'English'} · {new Date(c.created_at).toLocaleDateString('tr-TR')}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
