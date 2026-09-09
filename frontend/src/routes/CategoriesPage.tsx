import { useState } from 'react'
import { extractErrorMessage } from '../api/client'
import type { CategoryType, DetectionCategory } from '../api/types'
import {
  type CategoryInput,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '../features/categories/useCategories'

const TYPE_LABELS: Record<CategoryType, string> = {
  legal_risk: 'Risque juridique',
  important_point: 'Point important',
  intox: 'Intox potentielle',
  custom: 'Autre',
}

const EMPTY_FORM: CategoryInput = {
  name: '',
  type: 'custom',
  description: '',
  prompt_hint: '',
  keywords: [],
  color: '#2563EB',
  is_active: true,
  sort_order: 0,
}

export default function CategoriesPage() {
  const { data: categories, isLoading } = useCategories()
  const createMutation = useCreateCategory()
  const updateMutation = useUpdateCategory()
  const deleteMutation = useDeleteCategory()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CategoryInput>(EMPTY_FORM)
  const [keywordsText, setKeywordsText] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const startCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setKeywordsText('')
    setFormError(null)
    setShowForm(true)
  }

  const startEdit = (category: DetectionCategory) => {
    setEditingId(category.id)
    setForm({
      name: category.name,
      type: category.type,
      description: category.description,
      prompt_hint: category.prompt_hint,
      keywords: category.keywords,
      color: category.color,
      is_active: category.is_active,
      sort_order: category.sort_order,
    })
    setKeywordsText(category.keywords.join(', '))
    setFormError(null)
    setShowForm(true)
  }

  const handleSubmit = async () => {
    setFormError(null)
    const payload: CategoryInput = {
      ...form,
      keywords: keywordsText
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean),
    }
    try {
      if (editingId) {
        await updateMutation.mutateAsync({ id: editingId, ...payload })
      } else {
        await createMutation.mutateAsync(payload)
      }
      setShowForm(false)
    } catch (error) {
      setFormError(extractErrorMessage(error, 'Impossible d’enregistrer cette catégorie.'))
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('Supprimer cette catégorie de détection ?')) return
    await deleteMutation.mutateAsync(id)
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Catégories de détection</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Ces catégories guident l&apos;IA pour surligner les points juridiques, importants et les intox
            potentielles. Les catégories globales sont gérées par l&apos;équipe Revue de Presse ; vous pouvez ajouter
            les vôtres ci-dessous.
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={startCreate}>
          Nouvelle catégorie
        </button>
      </div>

      {showForm && (
        <div className="card mt-6">
          <h2 className="text-sm font-semibold text-slate-900">{editingId ? 'Modifier la catégorie' : 'Nouvelle catégorie'}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Nom</label>
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="label">Type</label>
              <select
                className="input"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as CategoryType })}
              >
                {Object.entries(TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="label">Description</label>
              <textarea
                className="input"
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Instruction de détection (injectée dans le prompt IA)</label>
              <textarea
                className="input"
                rows={2}
                value={form.prompt_hint}
                onChange={(e) => setForm({ ...form, prompt_hint: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Mots-clés indicatifs (séparés par des virgules)</label>
              <input className="input" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} />
            </div>
            <div>
              <label className="label">Couleur</label>
              <input
                type="color"
                className="mt-1 h-10 w-full rounded-md border border-slate-300"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
              />
            </div>
            <div className="flex items-end gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="is_active" className="text-sm text-slate-700">
                Active
              </label>
            </div>
          </div>
          {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="btn-primary"
              disabled={createMutation.isPending || updateMutation.isPending}
              onClick={() => void handleSubmit()}
            >
              Enregistrer
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
              Annuler
            </button>
          </div>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {isLoading && <p className="text-sm text-slate-500">Chargement…</p>}
        {categories?.map((category) => (
          <div key={category.id} className="card flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: category.color }} />
                <p className="text-sm font-medium text-slate-900">{category.name}</p>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {TYPE_LABELS[category.type]}
                </span>
                {category.organization === null && (
                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">Globale</span>
                )}
                {!category.is_active && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">Inactive</span>
                )}
              </div>
              {category.description && <p className="mt-1.5 text-sm text-slate-600">{category.description}</p>}
            </div>
            {category.organization !== null && (
              <div className="flex shrink-0 gap-2">
                <button type="button" className="btn-secondary" onClick={() => startEdit(category)}>
                  Modifier
                </button>
                <button type="button" className="btn-danger" onClick={() => void handleDelete(category.id)}>
                  Supprimer
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
