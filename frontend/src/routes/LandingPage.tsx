import type { ReactNode } from 'react'
import { Link, Navigate } from 'react-router-dom'
import type { StructuredReview } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { ClippingIllustration } from '../components/ClippingIllustration'
import {
  ArrowRightIcon,
  BuildingIcon,
  CameraIcon,
  CheckIcon,
  ChevronDownIcon,
  DownloadIcon,
  FlagIcon,
  GiftIcon,
  HighlighterIcon,
  LandmarkIcon,
  NewspaperIcon,
  ScaleIcon,
  ScanTextIcon,
  ShieldIcon,
  StarIcon,
  UsersIcon,
  type IconComponent,
} from '../components/icons'
import { PressReviewSheet } from '../components/PressReviewSheet'
import { PublicFooter, PublicHeader } from '../components/PublicSite'
import { WhatsAppButton } from '../components/WhatsAppButton'
import { WHATSAPP_DISPLAY } from '../lib/contact'
import { useScrollToHash } from '../lib/useScrollToHash'

/* ---------------------------------------------------------------------------
 * Contenu
 * ------------------------------------------------------------------------- */

const STEPS: { icon: IconComponent; title: string; text: string }[] = [
  {
    icon: CameraIcon,
    title: 'Photos ou PDF',
    text: 'Photographiez les pages au téléphone ou déposez les PDF des journaux, jusqu’à 50 documents par revue.',
  },
  {
    icon: ScanTextIcon,
    title: 'Lecture par l’IA',
    text: 'Chaque page est lue et découpée en articles sur nos serveurs. Vous pouvez fermer la page : l’analyse continue.',
  },
  {
    icon: NewspaperIcon,
    title: 'Revue au format classique',
    text: 'Une notice par journal, rangée par rubrique, des titres les plus lus aux moins connus.',
  },
  {
    icon: HighlighterIcon,
    title: 'Points clés',
    text: 'Risques juridiques, intox, annonces de concurrents : chaque passage est cité avec sa page d’origine.',
  },
  {
    icon: DownloadIcon,
    title: 'Export Word et PDF',
    text: 'Téléchargez la revue mise en page, ou copiez le texte pour l’envoyer par WhatsApp ou e-mail.',
  },
]

const FORMAT_POINTS = [
  'Un bandeau daté « Revue de presse — Cameroun »',
  'Des rubriques en couleur : presse générale, économique et financière, régionale et sécurité, santé et société, politique, sports et culture',
  'Une notice par journal : le titre de une entre guillemets, puis l’essentiel en quelques phrases',
  'Dans chaque rubrique, les journaux classés du plus lu au moins connu',
  'Le même rendu à l’écran, en Word et en PDF',
]

/** Revue fictive (journaux et contenus inventés) : sert uniquement à montrer la mise en page,
 * rendue par le même composant que les vraies revues. */
const SAMPLE_REVIEW: StructuredReview = {
  country: 'CAMEROUN',
  date_label: 'Lundi 12 octobre 2026',
  sections: [
    {
      key: 'generale',
      title: 'LA PRESSE GÉNÉRALE',
      color: '#1A237E',
      icon: '📰',
      entries: [
        {
          source: 'LE JOURNAL DU MATIN',
          headline: 'Rentrée scolaire : les prix des fournitures sous surveillance',
          summary:
            'Le quotidien consacre sa une aux préparatifs de la rentrée. Il relève des écarts de prix d’un marché à l’autre et rapporte les contrôles annoncés par les services du commerce.',
          documents: [],
        },
        {
          source: 'L’HEBDO DES RÉGIONS',
          headline: 'Routes : reprise des travaux de réhabilitation',
          summary:
            'L’hebdomadaire fait le point sur le chantier, son calendrier et les perturbations attendues pour les usagers.',
          documents: [],
        },
      ],
    },
    {
      key: 'economie',
      title: 'PRESSE ÉCONOMIQUE ET FINANCIÈRE',
      color: '#1B5E20',
      icon: '💰',
      entries: [
        {
          source: 'LA GAZETTE ÉCONOMIQUE',
          headline: 'Agriculture : une campagne prometteuse',
          summary:
            'Le journal annonce des prévisions de récolte en hausse et détaille les attentes des producteurs sur les prix.',
          documents: [],
        },
      ],
    },
  ],
}

const KEY_POINTS: { icon: IconComponent; title: string; text: string; tone: string }[] = [
  {
    icon: ScaleIcon,
    title: 'Risque juridique',
    text: 'Diffamation, accusations sans preuve, mise en cause de l’entreprise ou de ses dirigeants.',
    tone: 'bg-red-50 text-red-600 ring-red-100',
  },
  {
    icon: HighlighterIcon,
    title: 'Intox potentielle',
    text: 'Rumeurs relayées depuis les réseaux sociaux, chiffres invérifiables, informations déjà démenties.',
    tone: 'bg-amber-50 text-amber-600 ring-amber-100',
  },
  {
    icon: FlagIcon,
    title: 'Annonces des concurrents',
    text: 'Lancements, contrats, recrutements : créez vos propres catégories (concurrents, dirigeants, secteur) en langage courant.',
    tone: 'bg-brand-50 text-brand-600 ring-brand-100',
  },
  {
    icon: StarIcon,
    title: 'Points importants',
    text: 'Décisions, réglementations et chiffres qui concernent directement votre activité.',
    tone: 'bg-emerald-50 text-emerald-600 ring-emerald-100',
  },
]

const AUDIENCES: { icon: IconComponent; title: string; text: string }[] = [
  {
    icon: UsersIcon,
    title: 'Cellules de communication',
    text: 'La revue du jour prête pour le point du matin, au format que vos lecteurs connaissent déjà.',
  },
  {
    icon: BuildingIcon,
    title: 'Directions générales',
    text: 'L’essentiel de la presse en quelques minutes, avec les sujets sensibles en premier.',
  },
  {
    icon: ScaleIcon,
    title: 'Directions juridiques et conformité',
    text: 'Les mises en cause de l’entreprise et de ses dirigeants repérées dès leur parution.',
  },
  {
    icon: LandmarkIcon,
    title: 'Institutions et organisations',
    text: 'Ce que la presse nationale et régionale dit de vos programmes, rubrique par rubrique.',
  },
]

const INCLUDED = [
  'Lecture des photos et des PDF',
  'Revue au format classique, rubrique par rubrique',
  'Points clés et catégories personnalisées',
  'Export Word et PDF',
  'Espace partagé pour toute votre équipe',
  'Assistance sur WhatsApp',
]

const FAQ: { question: string; answer: ReactNode }[] = [
  {
    question: 'Quels documents puis-je envoyer ?',
    answer:
      'Des PDF de journaux ou des photos de pages prises au téléphone (JPG, PNG, WebP, HEIC), photos et PDF mélangés : jusqu’à 50 documents par revue et 30 Mo par fichier.',
  },
  {
    question: 'Combien de temps faut-il pour obtenir la revue ?',
    answer:
      'En général quelques minutes, selon le nombre de pages. L’analyse se fait sur nos serveurs : vous pouvez fermer la page et revenir quand la revue est prête.',
  },
  {
    question: 'Les étiquettes « risque juridique » et « intox » ont-elles une valeur juridique ?',
    answer:
      'Non. Ce sont des aides à la lecture produites par une intelligence artificielle, qui peut se tromper ou omettre un passage. Elles ne remplacent ni l’avis d’un juriste ni une vérification des faits : relisez les points sensibles avant toute diffusion.',
  },
  {
    question: 'Qui peut voir nos documents ?',
    answer: (
      <>
        Seuls les membres de votre organisation. Les textes sont analysés par Mistral AI, prestataire européen, uniquement
        pour produire votre revue. Tous les détails figurent dans notre{' '}
        <Link to="/confidentialite" className="font-semibold text-brand-600 underline-offset-2 hover:underline">
          politique de confidentialité
        </Link>
        .
      </>
    ),
  },
  {
    question: 'Comment souscrire un abonnement ?',
    answer:
      'Il n’y a pas de paiement en ligne. Écrivez-nous sur WhatsApp : nous établissons un devis selon votre volume de revues et la taille de votre équipe, puis notre équipe active votre abonnement dès réception du règlement.',
  },
  {
    question: 'Que se passe-t-il à la fin de l’essai gratuit ?',
    answer:
      'Rien n’est facturé automatiquement. Vos revues restent consultables ; pour en créer de nouvelles, contactez-nous afin d’activer un abonnement.',
  },
  {
    question: 'Puis-je travailler en équipe ?',
    answer:
      'Oui. Invitez vos collègues comme administrateurs ou membres : tout le monde partage les mêmes revues, documents et catégories de détection.',
  },
  {
    question: 'Faut-il installer un logiciel ?',
    answer: 'Non. Tout se fait dans le navigateur, sur ordinateur comme sur téléphone.',
  },
]

/* ---------------------------------------------------------------------------
 * Blocs de mise en page
 * ------------------------------------------------------------------------- */

function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <p className="eyebrow !text-brand-600">{eyebrow}</p>
      <h2 className="mt-2 text-balance font-display text-[28px] leading-tight font-semibold text-slate-900 sm:text-[34px]">
        {title}
      </h2>
      {children && <p className="mt-3 text-[15px] leading-relaxed text-slate-600 sm:text-base">{children}</p>}
    </div>
  )
}

function Section({ id, className, children }: { id: string; className?: string; children: ReactNode }) {
  return (
    <section id={id} className={`scroll-mt-16 py-16 sm:py-24 ${className ?? ''}`}>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">{children}</div>
    </section>
  )
}

function TrialCta({ className }: { className?: string }) {
  return (
    <Link to="/register" className={`btn-primary btn-lg ${className ?? ''}`}>
      Essai gratuit 7 jours
      <ArrowRightIcon className="h-4 w-4" />
    </Link>
  )
}

function Hero() {
  return (
    <section className="ink-gradient relative overflow-hidden text-white">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            'linear-gradient(rgb(255 255 255 / 0.6) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.6) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_1fr] lg:py-24">
        <div className="animate-slide-up">
          <p className="chip bg-white/10 py-1 text-slate-200 ring-1 ring-white/15">
            Pour les entreprises et institutions au Cameroun
          </p>
          <h1 className="mt-5 text-balance font-display text-[36px] leading-[1.1] font-semibold sm:text-5xl lg:text-[54px]">
            Votre revue de presse, <span className="text-amber-300">analysée</span> en quelques minutes.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-300 sm:text-lg">
            Photographiez ou scannez les journaux du jour. Revue de Presse lit chaque page, rédige la revue au format classique
            de votre cellule de communication et surligne ce qui mérite votre attention.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <TrialCta />
            <WhatsAppButton topic="demo" className="btn-lg" />
          </div>
          <div className="mt-5 space-y-1 text-sm text-slate-400">
            <p className="flex items-start gap-2">
              <GiftIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
              7 jours gratuits, 3 revues offertes, sans carte bancaire ni engagement
            </p>
            <p className="pl-6">Démo guidée sur WhatsApp : {WHATSAPP_DISPLAY}</p>
          </div>
        </div>
        <div className="px-4 pb-6 sm:px-10 lg:px-0">
          <ClippingIllustration />
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <Section id="fonctionnement" className="bg-white">
      <SectionHeading eyebrow="Comment ça marche" title="De la pile de journaux à la revue diffusée">
        Plus besoin de tout relire et de tout retaper : vous déposez les pages, Revue de Presse prépare la revue, vous
        relisez et diffusez.
      </SectionHeading>
      <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map((step, index) => (
          <li key={step.title} className="card relative !p-5">
            <div className="flex items-center justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <step.icon className="h-5 w-5" />
              </span>
              <span className="font-display text-2xl font-semibold text-slate-300" aria-hidden="true">
                {index + 1}
              </span>
            </div>
            <h3 className="mt-4 font-display text-[17px] font-semibold text-slate-900">{step.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{step.text}</p>
          </li>
        ))}
      </ol>
    </Section>
  )
}

function ClassicFormat() {
  return (
    <Section id="format" className="bg-slate-50">
      <div className="grid items-start gap-12 lg:grid-cols-[1fr_1.1fr]">
        <div className="lg:sticky lg:top-24">
          <SectionHeading eyebrow="Le format classique" title="La revue que vos lecteurs connaissent déjà">
            Pas un résumé générique : Revue de Presse reprend la mise en page diffusée chaque matin par les cellules de
            communication.
          </SectionHeading>
          <ul className="mt-8 space-y-3">
            {FORMAT_POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-[15px] leading-relaxed text-slate-700">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                  <CheckIcon className="h-3.5 w-3.5" />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
        <figure>
          <div className="rounded-3xl bg-paper p-4 shadow-[var(--shadow-lifted)] ring-1 ring-slate-200/80 sm:p-6">
            <PressReviewSheet review={SAMPLE_REVIEW} />
          </div>
          <figcaption className="mt-3 text-center text-xs text-slate-500">
            Exemple fictif : journaux et contenus inventés pour illustrer la mise en page.
          </figcaption>
        </figure>
      </div>
    </Section>
  )
}

function KeyPoints() {
  return (
    <Section id="points-cles" className="bg-white">
      <SectionHeading eyebrow="Points clés" title={<>Ce qui demande votre attention, <span className="highlighter">surligné</span></>}>
        En plus de la revue, l’IA relève les passages sensibles et les classe par catégorie, avec l’extrait exact et le
        document d’origine.
      </SectionHeading>
      <ul className="mt-12 grid gap-4 sm:grid-cols-2">
        {KEY_POINTS.map((point) => (
          <li key={point.title} className="card flex gap-4 !p-5">
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ${point.tone}`}>
              <point.icon className="h-5 w-5" />
            </span>
            <div>
              <h3 className="font-display text-[17px] font-semibold text-slate-900">{point.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{point.text}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3.5 text-sm leading-relaxed text-amber-900">
        <ShieldIcon className="mt-0.5 h-[18px] w-[18px] shrink-0 text-amber-600" />
        <span>
          <strong className="font-semibold">Une aide à la lecture, pas un avis juridique.</strong> L’IA peut se tromper ou
          omettre un passage : relisez les points sensibles avant toute diffusion.
        </span>
      </p>
    </Section>
  )
}

function Audience() {
  return (
    <Section id="pour-qui" className="bg-slate-50">
      <SectionHeading eyebrow="Pour qui" title="Pour les équipes qui suivent la presse chaque matin" />
      <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {AUDIENCES.map((audience) => (
          <li key={audience.title} className="card !p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink-900 text-amber-300">
              <audience.icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 font-display text-[17px] font-semibold text-slate-900">{audience.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{audience.text}</p>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function Pricing() {
  return (
    <Section id="tarifs" className="bg-white">
      <div className="grid items-center gap-10 lg:grid-cols-[1fr_1fr]">
        <div>
          <SectionHeading eyebrow="Tarifs" title="Tarifs : sur devis — contactez-nous">
            Chaque organisation a ses besoins : nombre de revues par mois, taille de l’équipe, accompagnement. Nous vous
            proposons une formule adaptée. Pas de paiement en ligne : votre abonnement est activé par notre équipe dès
            réception du règlement.
          </SectionHeading>
          <ul className="mt-8 grid gap-3 sm:grid-cols-2">
            {INCLUDED.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-[15px] text-slate-700">
                <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="ink-gradient rounded-3xl p-7 text-white shadow-[var(--shadow-lifted)] sm:p-9">
          <p className="eyebrow !text-slate-400">Toutes les formules</p>
          <p className="mt-3 font-display text-4xl font-semibold">
            Sur <span className="text-amber-300">devis</span>
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-slate-300">
            Dites-nous combien de revues vous préparez par mois et combien de personnes les utilisent : nous revenons vers
            vous avec une proposition.
          </p>
          <WhatsAppButton topic="billing" label="Demander un devis sur WhatsApp" className="btn-lg mt-7 w-full" />
          <p className="mt-3 text-center text-xs text-slate-400">WhatsApp : {WHATSAPP_DISPLAY}</p>
          <div className="mt-6 border-t border-white/10 pt-5 text-center text-sm text-slate-300">
            Envie d’essayer d’abord ?{' '}
            <Link to="/register" className="font-semibold text-amber-300 underline-offset-2 hover:underline">
              Essai gratuit de 7 jours
            </Link>
          </div>
        </div>
      </div>
    </Section>
  )
}

function Trial() {
  return (
    <section id="essai" className="scroll-mt-16 bg-amber-50/70">
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-8 px-4 py-14 sm:px-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="chip bg-white py-1 text-amber-800 ring-1 ring-amber-200">
            <GiftIcon className="h-3.5 w-3.5" />
            Essai gratuit
          </p>
          <h2 className="mt-4 font-display text-[28px] leading-tight font-semibold text-slate-900 sm:text-[32px]">
            Essayez pendant 7 jours, sur vos propres journaux
          </h2>
          <ul className="mt-4 space-y-2 text-[15px] text-slate-700">
            <li className="flex items-start gap-2.5">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              Votre espace d’entreprise prêt en une minute
            </li>
            <li className="flex items-start gap-2.5">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              3 revues de presse complètes offertes, sur vos propres journaux
            </li>
            <li className="flex items-start gap-2.5">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              Sans carte bancaire ni engagement : rien n’est facturé à la fin de l’essai
            </li>
            <li className="flex items-start gap-2.5">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              Invitez vos collègues pour tester ensemble
            </li>
          </ul>
        </div>
        <TrialCta className="w-full shrink-0 md:w-auto" />
      </div>
    </section>
  )
}

function Faq() {
  return (
    <Section id="faq" className="bg-white">
      <div className="grid gap-10 lg:grid-cols-[1fr_1.6fr]">
        <SectionHeading eyebrow="FAQ" title="Questions fréquentes">
          Une autre question ? Écrivez-nous sur WhatsApp au {WHATSAPP_DISPLAY}.
        </SectionHeading>
        <div className="divide-y divide-slate-200 border-y border-slate-200">
          {FAQ.map((item) => (
            <details key={item.question} className="group py-1">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-lg py-4 text-left font-semibold text-slate-900 [&::-webkit-details-marker]:hidden">
                {item.question}
                <ChevronDownIcon className="h-5 w-5 shrink-0 text-slate-400 transition group-open:rotate-180" />
              </summary>
              <div className="pb-5 text-[15px] leading-relaxed text-slate-600">{item.answer}</div>
            </details>
          ))}
        </div>
      </div>
    </Section>
  )
}

function FinalCta() {
  return (
    <section className="bg-white px-4 pb-16 sm:px-6 sm:pb-24">
      <div className="brand-gradient mx-auto max-w-6xl rounded-3xl px-6 py-12 text-center text-white shadow-[var(--shadow-lifted)] sm:px-12 sm:py-16">
        <h2 className="mx-auto max-w-2xl text-balance font-display text-[28px] leading-tight font-semibold sm:text-4xl">
          Votre prochaine revue de presse, prête en quelques minutes.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-brand-100">
          Commencez l’essai gratuit ou demandez une démonstration guidée : nous vous montrons le résultat sur vos journaux.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link to="/register" className="btn-lg inline-flex items-center justify-center gap-2 rounded-2xl bg-white font-semibold text-brand-700 shadow-sm transition hover:bg-brand-50">
            Essai gratuit 7 jours
            <ArrowRightIcon className="h-4 w-4" />
          </Link>
          <WhatsAppButton topic="demo" className="btn-lg" />
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------------- */

/** Page d'accueil publique (« / ») : présentation du service pour les visiteurs ; un
 * utilisateur connecté est renvoyé vers son tableau de bord. Aucun prix affiché. */
export default function LandingPage() {
  const { user } = useAuth()
  useScrollToHash()

  if (user) return <Navigate to="/dashboard" replace />

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />
      <main id="contenu" tabIndex={-1} className="outline-none">
        <Hero />
        <HowItWorks />
        <ClassicFormat />
        <KeyPoints />
        <Audience />
        <Pricing />
        <Trial />
        <Faq />
        <FinalCta />
      </main>
      <PublicFooter />
    </div>
  )
}
