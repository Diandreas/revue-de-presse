import clsx from 'clsx'
import { useState } from 'react'
import { extractErrorMessage } from '../api/client'
import type { CategoryType, DetectionCategory } from '../api/types'
import { isAdminRole, useAuth } from '../auth/useAuth'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import {
  AlertTriangleIcon,
  CheckIcon,
  PenLineIcon,
  PlusIcon,
  ScaleIcon,
  ShieldIcon,
  SparkleIcon,
  StarIcon,
  TagIcon,
  TrashIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, EmptyState, PageHeader, Skeleton, Spinner, Switch } from '../components/ui'
import {
  type CategoryInput,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '../features/categories/useCategories'
import { hexToRgba } from '../lib/format'

const TYPE_OPTIONS: { value: CategoryType; label: string; icon: IconComponent; hint: string }[] = [
  { value: 'legal_risk', label: 'Risque juridique', icon: ScaleIcon, hint: 'Diffamation, données personnelles…' },
  { value: 'important_point', label: 'Point important', icon: StarIcon, hint: 'À signaler à la direction' },
  { value: 'intox', label: 'Intox potentielle', icon: AlertTriangleIcon, hint: 'Information douteuse' },
  { value: 'custom', label: 'Autre', icon: TagIcon, hint: 'Votre propre critère' },
]
const TYPE_BY_VALUE = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o])) as Record<
  CategoryType,
  (typeof TYPE_OPTIONS)[number]
>

const COLOR_PRESETS = ['#DC2626', '#EA580C', '#D97706', '#16A34A', '#0891B2', '#2563EB', '#4F46E5', '#9333EA', '#DB2777', '#475569']

const EMPTY_FORM: CategoryInput = {
  name: '',
  type: 'custom',
  description: '',
  prompt_hint: '',
  keywords: [],
  color: '#4F46E5',
  is_active: true,
  sort_order: 10,
}

function CategoryCard({
  category,
  canEdit,
  onEdit,
  onDelete,
}: {
  category: DetectionCategory
  canEdit: boolean
  onEdit: () => void
  onDelete: () => void
}) {
  const type = TYPE_BY_VALUE[category.type] ?? TYPE_BY_VALUE.custom
  const isGlobal = category.organization === null
  return (
    <article
      className={clsx(
        'card relative flex flex-col overflow-hidden !p-0 transition',
        !category.is_active && 'opacity-60',
      )}
    >
      <div className="h-1.5" style={{ backgroundColor: category.color }} />
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start gap-3">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            style={{ backgroundColor: hexToRgba(category.color, 0.12), color: category.color }}
          >
            <type.icon className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-display text-[17px] font-semibold text-slate-900">{category.name}</h3>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <span className="chip bg-slate-100 text-slate-600">{type.label}</span>
              {isGlobal && (
                <span className="chip bg-brand-50 text-brand-700">
                  <ShieldIcon className="h-3 w-3" /> Par défaut
                </span>
              )}
              {!category.is_active && <span className="chip bg-slate-100 text-slate-500">Désactivée</span>}
            </div>
          </div>
        </div>

        {category.description && <p className="mt-4 text-sm leading-relaxed text-slate-600">{category.description}</p>}

        {category.prompt_hint && (
          <div className="mt-4 rounded-xl bg-slate-50 px-3.5 py-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
              <SparkleIcon className="h-3.5 w-3.5 text-brand-500" /> Consigne donnée à l’IA
            </p>
            <p className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-slate-600">{category.prompt_hint}</p>
          </div>
        )}

        {category.keywords.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {category.keywords.map((keyword) => (
              <span key={keyword} className="chip bg-white text-slate-600 ring-1 ring-slate-200">
                {keyword}
              </span>
            ))}
          </div>
        )}

        {!isGlobal && canEdit && (
          <div className="mt-5 flex gap-2 border-t border-slate-100 pt-4">
            <button type="button" className="btn-secondary btn-sm" onClick={onEdit}>
              <PenLineIcon className="h-3.5 w-3.5" /> Modifier
            </button>
            <button type="button" className="btn-ghost btn-sm text-red-600 hover:bg-red-50 hover:text-red-700" onClick={onDelete}>
              <TrashIcon className="h-3.5 w-3.5" /> Supprimer
            </button>
          </div>
        )}
      </div>
    </article>
  )
}

export default function CategoriesPage() {
  const toast = useToast()
  const { organization } = useAuth()
  const canEdit = isAdminRole(organization?.my_role)
  const { data: categories, isLoading } = useCategories()
  const createMutation = useCreateCategory()
  const updateMutation = useUpdateCategory()
  const deleteMutation = useDeleteCategory()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CategoryInput>(EMPTY_FORM)
  const [keywordsText, setKeywordsText] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [toDelete, setToDelete] = useState<DetectionCategory | null>(null)

  const globalCategories = categories?.filter((c) => c.organization === null) ?? []
  const ownCategories = categories?.filter((c) => c.organization !== null) ?? []

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
    if (form.name.trim().length < 2) {
      setFormError('Donnez un nom à la catégorie.')
      return
    }
    const payload: CategoryInput = {
      ...form,
      name: form.name.trim(),
      keywords: keywordsText
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean),
    }
    try {
      if (editingId) {
        await updateMutation.mutateAsync({ id: editingId, ...payload })
        toast.success('Catégorie mise à jour.')
      } else {
        await createMutation.mutateAsync(payload)
        toast.success('Catégorie créée : elle sera utilisée dès la prochaine revue.')
      }
      setShowForm(false)
    } catch (error) {
      setFormError(extractErrorMessage(error, 'Impossible d’enregistrer cette catégorie.'))
    }
  }

  const confirmDelete = async () => {
    if (!toDelete) return
    try {
      await deleteMutation.mutateAsync(toDelete.id)
      toast.success('Catégorie supprimée.')
      setToDelete(null)
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de supprimer cette catégorie.'))
      setToDelete(null)
    }
  }

  const saving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Configuration"
        title="Catégories de détection"
        subtitle="Elles indiquent à l’IA quels passages surligner dans vos revues. Ajoutez vos propres critères (secteur, concurrents, dirigeants…) pour une veille sur mesure."
        actions={
          canEdit && (
            <button type="button" className="btn-primary" onClick={startCreate}>
              <PlusIcon className="h-4 w-4" />
              Nouvelle catégorie
            </button>
          )
        }
      />

      <section>
        <h2 className="section-title">Vos catégories</h2>
        <p className="mt-0.5 text-sm text-slate-500">Propres à votre organisation, modifiables à tout moment.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {isLoading && [0, 1].map((i) => <Skeleton key={i} className="h-52 rounded-2xl" />)}
          {ownCategories.map((category) => (
            <CategoryCard
              key={category.id}
              category={category}
              canEdit={canEdit}
              onEdit={() => startEdit(category)}
              onDelete={() => setToDelete(category)}
            />
          ))}
        </div>
        {!isLoading && ownCategories.length === 0 && (
          <div className="card mt-4">
            <EmptyState
              icon={TagIcon}
              title="Aucune catégorie personnalisée"
              description="Exemple : « Concurrents » avec les noms de vos concurrents en mots-clés, ou « Réglementation télécoms »."
              action={
                canEdit && (
                  <button type="button" className="btn-secondary" onClick={startCreate}>
                    <PlusIcon className="h-4 w-4" /> Créer une catégorie
                  </button>
                )
              }
              className="!py-8"
            />
          </div>
        )}
      </section>

      <section>
        <h2 className="section-title">Catégories par défaut</h2>
        <p className="mt-0.5 text-sm text-slate-500">Toujours actives, maintenues par l’équipe Revue de Presse.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {globalCategories.map((category) => (
            <CategoryCard key={category.id} category={category} canEdit={false} onEdit={() => undefined} onDelete={() => undefined} />
          ))}
        </div>
      </section>

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title={editingId ? 'Modifier la catégorie' : 'Nouvelle catégorie'}
        description="L’IA s’appuie sur le nom, la description et la consigne pour repérer les passages concernés."
        size="lg"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
              Annuler
            </button>
            <button type="button" className="btn-primary" disabled={saving} onClick={() => void handleSubmit()}>
              {saving ? <Spinner /> : <CheckIcon className="h-4 w-4" />}
              {editingId ? 'Enregistrer' : 'Créer la catégorie'}
            </button>
          </>
        }
      >
        <div className="space-y-5">
          <div>
            <label className="label" htmlFor="cat-name">
              Nom
            </label>
            <input
              id="cat-name"
              className="input"
              placeholder="Ex : Concurrents"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>

          <div>
            <span className="label">Type</span>
            <div className="grid grid-cols-2 gap-2">
              {TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setForm({ ...form, type: option.value })}
                  className={clsx(
                    'flex items-start gap-2.5 rounded-xl border p-3 text-left transition',
                    form.type === option.value
                      ? 'border-brand-400 bg-brand-50/60 ring-2 ring-brand-500/15'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50',
                  )}
                >
                  <option.icon className={clsx('mt-0.5 h-4 w-4 shrink-0', form.type === option.value ? 'text-brand-600' : 'text-slate-400')} />
                  <span>
                    <span className="block text-[13px] font-semibold text-slate-800">{option.label}</span>
                    <span className="block text-[11px] text-slate-500">{option.hint}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="label" htmlFor="cat-description">
              Description
            </label>
            <textarea
              id="cat-description"
              className="input"
              rows={2}
              placeholder="Ce que cette catégorie doit couvrir."
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div>
            <label className="label" htmlFor="cat-hint">
              Consigne pour l’IA
            </label>
            <textarea
              id="cat-hint"
              className="input"
              rows={3}
              placeholder="Ex : Signale toute mention de nos concurrents directs, de leurs prix ou de leurs nouveaux produits."
              value={form.prompt_hint}
              onChange={(e) => setForm({ ...form, prompt_hint: e.target.value })}
            />
            <p className="field-hint">Formulée comme une instruction : « Signale… », « Repère… ».</p>
          </div>

          <div>
            <label className="label" htmlFor="cat-keywords">
              Mots-clés indicatifs
            </label>
            <input
              id="cat-keywords"
              className="input"
              placeholder="séparés par des virgules"
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
            />
          </div>

          <div>
            <span className="label">Couleur</span>
            <div className="flex flex-wrap items-center gap-2">
              {COLOR_PRESETS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Couleur ${color}`}
                  onClick={() => setForm({ ...form, color })}
                  className={clsx(
                    'flex h-8 w-8 items-center justify-center rounded-full ring-offset-2 transition',
                    form.color.toLowerCase() === color.toLowerCase() ? 'ring-2 ring-slate-900' : 'hover:scale-110',
                  )}
                  style={{ backgroundColor: color }}
                >
                  {form.color.toLowerCase() === color.toLowerCase() && <CheckIcon className="h-4 w-4 text-white" />}
                </button>
              ))}
              <label className="relative ml-1 flex h-8 cursor-pointer items-center gap-1.5 rounded-full border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50">
                <span className="h-4 w-4 rounded-full ring-1 ring-black/10" style={{ backgroundColor: form.color }} />
                Autre
                <input
                  type="color"
                  className="absolute inset-0 cursor-pointer opacity-0"
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value.toUpperCase() })}
                />
              </label>
            </div>
          </div>

          <Switch
            id="cat-active"
            checked={form.is_active}
            onChange={(checked) => setForm({ ...form, is_active: checked })}
            label="Active"
            description="Une catégorie désactivée n’est plus utilisée pour les nouvelles revues."
          />

          {formError && <Alert tone="danger">{formError}</Alert>}
        </div>
      </Modal>

      <Modal
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Supprimer cette catégorie ?"
        description={toDelete ? `« ${toDelete.name} » ne sera plus utilisée pour les prochaines revues.` : undefined}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setToDelete(null)}>
              Annuler
            </button>
            <button type="button" className="btn-danger" disabled={deleteMutation.isPending} onClick={() => void confirmDelete()}>
              {deleteMutation.isPending ? <Spinner /> : <TrashIcon className="h-4 w-4" />}
              Supprimer
            </button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-600">
          Si elle a déjà servi dans des revues, la suppression sera refusée : désactivez-la plutôt pour conserver
          l’historique.
        </p>
      </Modal>
    </div>
  )
}
