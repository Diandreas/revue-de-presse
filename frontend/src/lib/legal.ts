/** Identité de l'éditeur et paramètres des pages légales (CGU/CGV, confidentialité,
 * mentions légales) : UNE seule source pour les trois pages, le pied de page et
 * l'inscription.
 *
 * Les valeurs encore inconnues valent `TO_COMPLETE` : elles s'affichent surlignées sur les
 * pages publiques tant qu'elles ne sont pas remplacées. Les textes doivent être relus par
 * un juriste avant d'encaisser des clients (audit P0 « CGU/CGV »). */
import { WHATSAPP_DISPLAY, WHATSAPP_NUMBER } from './contact'

/** Marqueur des informations à fournir par l'éditeur (RCCM, NIU, adresse…). */
export const TO_COMPLETE = '[à compléter]'

export function isPlaceholder(value: string | null | undefined): boolean {
  return !value || value.includes('[à compléter')
}

/** Version des CGU/CGV et de la politique de confidentialité, enregistrée avec la case
 * d'acceptation à l'inscription. À changer (nouvelle date) à chaque modification de fond
 * des textes : les comptes existants devront alors accepter la nouvelle version. */
export const TERMS_VERSION = '2026-10-11'

/** « Dernière mise à jour » affichée en tête des pages légales (AAAA-MM-JJ). */
export const LEGAL_LAST_UPDATED = '2026-10-11'

/** Adresse publique du site : balises Open Graph, sitemap.xml et robots.txt (frontend/public)
 * reprennent la même origine — à modifier ensemble en cas de changement de domaine. */
export const SITE_URL = 'https://presse.mirlab.cloud'

export const LEGAL_ROUTES = [
  { to: '/cgu', label: 'CGU / CGV' },
  { to: '/confidentialite', label: 'Confidentialité' },
  { to: '/mentions-legales', label: 'Mentions légales' },
] as const

export const LEGAL = {
  /** Nom commercial du service. */
  brand: 'Revue de Presse',
  publisher: {
    /** Raison sociale de l'éditeur. */
    name: 'Mirlab',
    /** Forme juridique (SARL, SAS, établissement…). */
    legalForm: TO_COMPLETE,
    /** Capital social, si société. */
    capital: TO_COMPLETE,
    /** Registre du commerce et du crédit mobilier. */
    rccm: TO_COMPLETE,
    /** Numéro d'identifiant unique (administration fiscale). */
    niu: TO_COMPLETE,
    /** Adresse du siège social. */
    address: TO_COMPLETE,
    /** E-mail de contact (commercial, support, données personnelles). */
    email: TO_COMPLETE,
    /** Téléphone / WhatsApp (lib/contact.ts). */
    phone: WHATSAPP_DISPLAY,
    whatsappUrl: `https://wa.me/${WHATSAPP_NUMBER}`,
    /** Directeur (ou directrice) de la publication. */
    publicationDirector: TO_COMPLETE,
  },
  host: {
    // À vérifier sur le contrat d'hébergement du VPS (raison sociale et adresse de l'hébergeur).
    name: 'Hostinger International Ltd.',
    address: '61 Lordou Vironos Street, 6023 Larnaca, Chypre',
    website: 'https://www.hostinger.com',
    /** Pays du centre de données du serveur (VPS). */
    dataLocation: TO_COMPLETE,
  },
  aiProvider: {
    name: 'Mistral AI',
    address: '15 rue des Halles, 75001 Paris, France',
    website: 'https://mistral.ai',
    dataLocation: 'Union européenne',
    /** Conservation et réutilisation des contenus par Mistral AI selon l'offre souscrite
     * (exclusion de l'entraînement des modèles, durée de conservation). */
    dataTerms: TO_COMPLETE,
  },
  /** Juridiction compétente en cas de litige (ex. « tribunaux de Douala »). */
  jurisdiction: TO_COMPLETE,
  /** Durées de conservation (proposition à valider par l'éditeur, idéalement avec un juriste). */
  retention: [
    {
      data: 'Compte utilisateur (nom, e-mail, rôle, organisation)',
      duration: 'Pendant toute la durée du compte, puis suppression dans les 90 jours suivant sa clôture.',
    },
    {
      data: 'Documents déposés, textes extraits, revues et points clés',
      duration:
        'Pendant la durée de l’abonnement ou de l’essai, puis suppression dans les 90 jours suivant leur fin. Vous pouvez demander une suppression anticipée à tout moment.',
    },
    {
      data: 'Factures et pièces comptables',
      duration: '10 ans, conformément aux obligations comptables (Acte uniforme OHADA).',
    },
    {
      data: 'Journaux techniques et de sécurité (connexions, adresses IP)',
      duration: '12 mois au plus.',
    },
    {
      data: 'Échanges avec notre équipe (WhatsApp, e-mail)',
      duration: '3 ans après le dernier échange.',
    },
    {
      data: 'Sauvegardes chiffrées',
      duration: '12 mois au plus, par rotation : une donnée supprimée disparaît des sauvegardes à leur renouvellement.',
    },
  ],
} as const

/** « 11 octobre 2026 » à partir d'une date AAAA-MM-JJ (sans décalage de fuseau). */
export function formatLegalDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(year, month - 1, day),
  )
}
