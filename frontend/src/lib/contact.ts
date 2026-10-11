/** Contact commercial et assistance : WhatsApp (canal de prédilection des entreprises au
 * Cameroun). Le numéro peut être remplacé au build par `VITE_WHATSAPP_NUMBER` (format
 * international, avec ou sans « + » et espaces). */
const DEFAULT_WHATSAPP_NUMBER = '237693427913'

export const WHATSAPP_NUMBER =
  ((import.meta.env.VITE_WHATSAPP_NUMBER as string | undefined) ?? '').replace(/\D/g, '') || DEFAULT_WHATSAPP_NUMBER

/** « +237 693 42 79 13 » pour un numéro camerounais, sinon « +<chiffres> ». */
export function formatPhone(digits: string): string {
  if (digits.startsWith('237') && digits.length === 12) {
    const n = digits.slice(3)
    return `+237 ${n.slice(0, 3)} ${n.slice(3, 5)} ${n.slice(5, 7)} ${n.slice(7)}`
  }
  return `+${digits}`
}

export const WHATSAPP_DISPLAY = formatPhone(WHATSAPP_NUMBER)

export type WhatsAppTopic = 'demo' | 'billing' | 'help'

/** Message pré-rempli : l'équipe sait d'emblée qui écrit et pourquoi. */
export function whatsappMessage(topic: WhatsAppTopic, organizationName?: string | null): string {
  const org = organizationName ? ` (entreprise : ${organizationName})` : ''
  switch (topic) {
    case 'billing':
      return `Bonjour, j’ai une question sur l’abonnement Revue de Presse${org}.`
    case 'help':
      return `Bonjour, j’ai besoin d’aide sur Revue de Presse${org}.`
    default:
      return `Bonjour, je souhaite une démo de Revue de Presse pour mon entreprise${org}.`
  }
}

/** Lien « click to chat » : ouvre WhatsApp (application ou web) sur la conversation. */
export function whatsappUrl(topic: WhatsAppTopic, organizationName?: string | null): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(whatsappMessage(topic, organizationName))}`
}
