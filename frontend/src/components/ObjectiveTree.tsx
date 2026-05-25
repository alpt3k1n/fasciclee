import type { Objective } from '@/lib/api'

const BLOOM_COLOR: Record<string, string> = {
  remember: 'bg-slate-100 text-slate-600',
  understand: 'bg-blue-50 text-blue-700',
  apply: 'bg-teal-50 text-teal-700',
  analyze: 'bg-violet-50 text-violet-700',
  evaluate: 'bg-orange-50 text-orange-700',
  create: 'bg-rose-50 text-rose-700',
}

const BLOOM_TR: Record<string, string> = {
  remember: 'Hatırla',
  understand: 'Anla',
  apply: 'Uygula',
  analyze: 'Analiz',
  evaluate: 'Değerlendir',
  create: 'Yarat',
}

function ObjectiveNode({ obj, depth = 0 }: { obj: Objective; depth?: number }) {
  return (
    <div>
      <div
        className="flex items-start gap-2 py-1.5 rounded px-2 hover:bg-slate-50 group"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        {obj.code && (
          <span className="text-xs font-mono text-slate-400 min-w-[2.5rem] pt-0.5">{obj.code}</span>
        )}
        <span className="text-sm flex-1">{obj.text}</span>
        {obj.bloom_level && (
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${BLOOM_COLOR[obj.bloom_level] ?? 'bg-slate-100 text-slate-600'}`}>
            {BLOOM_TR[obj.bloom_level] ?? obj.bloom_level}
          </span>
        )}
      </div>
      {obj.children.map(child => (
        <ObjectiveNode key={child.id} obj={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export default function ObjectiveTree({ objectives }: { objectives: Objective[] }) {
  if (!objectives.length) return <div className="text-slate-400 text-sm">Kazanım yok</div>
  return (
    <div className="border rounded-lg divide-y">
      {objectives.map(obj => (
        <ObjectiveNode key={obj.id} obj={obj} />
      ))}
    </div>
  )
}
