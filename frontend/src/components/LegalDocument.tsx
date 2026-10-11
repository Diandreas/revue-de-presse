import type { ReactNode } from 'react'
import { LEGAL, LEGAL_LAST_UPDATED, TERMS_VERSION, formatLegalDate, isPlaceholder } from '../lib/legal'
import { useDocumentMeta } from '../lib/useDocumentMeta'
import { useScrollToHash } from '../lib/useScrollToHash'
import { ChevronDownIcon } from './icons'
import { PublicFooter, PublicHeader } from './PublicSite'

export interface LegalSection {
  id: string
  title: string
  body: ReactNode
}

interface LegalDocumentProps {
  title: string
  /** Description pour les moteurs de recherche. */
  description: string
  intro: ReactNode
  sections: LegalSection[]
  /** Affiche le numéro de version (CGU/CGV, acceptées à l'inscription). */
  showVersion?: boolean
}

/** Valeur issue de lib/legal.ts : surlignée tant qu'elle vaut « [à compléter] ». */
export function LegalValue({ value }: { value: string }) {
  if (isPlaceholder(value)) {
    return <mark className="rounded bg-amber-100 px-1 font-medium text-amber-900">{value || '[à compléter]'}</mark>
  }
  return <>{value}</>
}

/** Lien sortant (site d'un prestataire, WhatsApp) ouvert dans un nouvel onglet. */
export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  )
}

/** Adresse e-mail de l'éditeur : lien « mailto » une fois renseignée. */
export function LegalEmail() {
  const email = LEGAL.publisher.email
  return isPlaceholder(email) ? <LegalValue value={email} /> : <a href={`mailto:${email}`}>{email}</a>
}

/** Coordonnées de l'éditeur (fin des pages légales). */
export function LegalContact() {
  const { publisher } = LEGAL
  return (
    <ul>
      <li>
        E-mail : <LegalEmail />
      </li>
      <li>
        WhatsApp : <ExternalLink href={publisher.whatsappUrl}>{publisher.phone}</ExternalLink>
      </li>
      <li>
        Courrier : {publisher.name}, <LegalValue value={publisher.address} />
      </li>
    </ul>
  )
}

/** Tableau à deux colonnes (finalités / bases légales, données / durées…). */
export function LegalTable({ head, rows }: { head: [string, string]; rows: [ReactNode, ReactNode][] }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-slate-900">
          <tr>
            {head.map((label) => (
              <th key={label} scope="col" className="px-4 py-2.5 font-semibold">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(([first, second], index) => (
            <tr key={index} className="align-top">
              <td className="w-[45%] px-4 py-3 font-medium text-slate-800">{first}</td>
              <td className="px-4 py-3 text-slate-600">{second}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Liste « libellé : valeur » (identité de l'éditeur, de l'hébergeur). */
export function LegalFacts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[200px_minmax(0,1fr)] sm:gap-4">
          <dt className="text-slate-500">{label}</dt>
          <dd className="font-medium break-words text-slate-800">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function TableOfContents({ sections }: { sections: LegalSection[] }) {
  return (
    <ol className="space-y-1.5 text-sm">
      {sections.map((section, index) => (
        <li key={section.id}>
          <a href={`#${section.id}`} className="flex gap-2 text-slate-600 transition hover:text-brand-700">
            <span className="w-5 shrink-0 text-right text-slate-400 tabular-nums">{index + 1}.</span>
            {section.title}
          </a>
        </li>
      ))}
    </ol>
  )
}

/** Mise en page commune des pages légales : en-tête daté, sommaire, sections numérotées. */
export function LegalDocument({ title, description, intro, sections, showVersion = false }: LegalDocumentProps) {
  useDocumentMeta(`${title} — Revue de Presse`, description)
  useScrollToHash()

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />
      <main id="contenu" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-10 outline-none sm:px-6 sm:py-14">
        <header className="max-w-3xl">
          <p className="eyebrow !text-brand-600">Informations légales</p>
          <h1 className="mt-2 text-balance font-display text-[30px] leading-tight font-semibold text-slate-900 sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 text-sm text-slate-500">
            Dernière mise à jour : <time dateTime={LEGAL_LAST_UPDATED}>{formatLegalDate(LEGAL_LAST_UPDATED)}</time>
            {showVersion && <> · version {TERMS_VERSION}</>}
          </p>
          <div className="mt-5 text-[15px] leading-relaxed text-slate-600">{intro}</div>
        </header>

        <div className="mt-10 grid gap-8 lg:grid-cols-[250px_minmax(0,1fr)] lg:gap-14">
          <details className="surface-muted group p-4 lg:hidden">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-slate-800 [&::-webkit-details-marker]:hidden">
              Sommaire
              <ChevronDownIcon className="h-4 w-4 text-slate-400 transition group-open:rotate-180" />
            </summary>
            <div className="mt-3">
              <TableOfContents sections={sections} />
            </div>
          </details>
          <nav aria-label="Sommaire" className="hidden lg:sticky lg:top-24 lg:block lg:self-start">
            <p className="eyebrow mb-3">Sommaire</p>
            <TableOfContents sections={sections} />
          </nav>

          <div className="max-w-3xl space-y-10 text-[15px] leading-relaxed text-slate-700 [&_a]:font-medium [&_a]:text-brand-600 [&_a]:underline [&_a]:decoration-brand-200 [&_a]:underline-offset-2 [&_a:hover]:text-brand-700 [&_li]:pl-1 [&_p+p]:mt-3 [&_p+ul]:mt-3 [&_strong]:font-semibold [&_strong]:text-slate-900 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5 [&_ul+p]:mt-3 [&_ul]:marker:text-brand-300">
            {sections.map((section, index) => (
              <section key={section.id} id={section.id} className="scroll-mt-24">
                <h2 className="mb-3 font-display text-xl font-semibold text-slate-900">
                  {index + 1}. {section.title}
                </h2>
                {section.body}
              </section>
            ))}
          </div>
        </div>
      </main>
      <PublicFooter />
    </div>
  )
}
