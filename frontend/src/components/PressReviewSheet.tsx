import type { PressReviewEntry, StructuredReview } from '../api/types'

/** Revue de presse au format diffusé par les cellules de communication (même mise en page
 * que les exports Word / PDF) : bandeau daté, rubriques en couleur, une notice par journal. */
export function PressReviewSheet({ review }: { review: StructuredReview }) {
  const subtitle = [review.country, review.date_label].filter(Boolean).join('  —  ')
  return (
    <div>
      <header className="rounded-2xl bg-[#1A237E] px-5 py-6 text-center text-white shadow-sm sm:py-7">
        <p className="text-2xl font-bold tracking-[0.06em] sm:text-3xl">REVUE DE PRESSE</p>
        {subtitle && <p className="mt-1.5 text-sm tracking-wide text-[#AAAAFF]">{subtitle}</p>}
      </header>

      {review.sections.map((section) => (
        <section key={section.key} className="mt-8">
          <h2
            className="flex items-center gap-2.5 rounded-lg px-4 py-2.5 text-[13px] font-bold tracking-wide text-white sm:text-sm"
            style={{ backgroundColor: section.color }}
          >
            <span aria-hidden="true">{section.icon}</span>
            {section.title}
          </h2>
          <div className="divide-y divide-slate-200/70">
            {section.entries.map((entry, index) => (
              <article key={`${entry.source}-${index}`} className="py-4">
                <h3 className="text-[15px] font-bold tracking-wide text-[#8B0000]">▶ {entry.source}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-slate-800 hyphens-auto sm:text-justify">
                  {entry.headline && (
                    <span className="font-medium text-slate-950">{`« ${entry.headline} » — `}</span>
                  )}
                  {entry.summary}
                </p>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function entryText(entry: PressReviewEntry) {
  return entry.headline ? `« ${entry.headline} » — ${entry.summary}` : entry.summary
}

/** Texte brut de la revue, pour la coller dans un e-mail ou WhatsApp. */
export function pressReviewToText(review: StructuredReview) {
  const lines = [['REVUE DE PRESSE', review.country, review.date_label].filter(Boolean).join(' — '), '']
  for (const section of review.sections) {
    lines.push(`${section.icon} ${section.title}`, '')
    for (const entry of section.entries) lines.push(`▶ ${entry.source}`, entryText(entry), '')
  }
  return lines.join('\n').trim()
}
