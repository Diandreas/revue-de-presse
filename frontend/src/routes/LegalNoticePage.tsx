import { Link } from 'react-router-dom'
import {
  ExternalLink,
  LegalContact,
  LegalDocument,
  LegalEmail,
  LegalFacts,
  type LegalSection,
} from '../components/LegalDocument'
import { LEGAL, hasLegalEmail, isPlaceholder } from '../lib/legal'

const { publisher, host } = LEGAL

/** Valeur facultative : null (ligne masquée) tant qu'elle n'est pas renseignée. */
const optional = (value: string) => (isPlaceholder(value) ? null : value)

const SECTIONS: LegalSection[] = [
  {
    id: 'editeur',
    title: 'Éditeur du site',
    body: (
      <>
        <p>
          Le site et le service {LEGAL.brand} sont édités par :
        </p>
        <LegalFacts
          items={[
            ['Raison sociale', publisher.name],
            [
              'Site',
              <ExternalLink key="website" href={publisher.website}>
                excelcisgroup.com
              </ExternalLink>,
            ],
            ['Forme juridique', optional(publisher.legalForm)],
            ['Capital social', optional(publisher.capital)],
            ['Siège social', publisher.address],
            ['RCCM', optional(publisher.rccm)],
            ['NIU', optional(publisher.niu)],
            ['E-mail', hasLegalEmail ? <LegalEmail key="email" /> : null],
            [
              'Téléphone / WhatsApp',
              <ExternalLink key="phone" href={publisher.whatsappUrl}>
                {publisher.phone}
              </ExternalLink>,
            ],
          ]}
        />
      </>
    ),
  },
  ...(isPlaceholder(publisher.publicationDirector)
    ? []
    : [
        {
          id: 'publication',
          title: 'Direction de la publication',
          body: <p>Directeur ou directrice de la publication : {publisher.publicationDirector}.</p>,
        },
      ]),
  {
    id: 'hebergement',
    title: 'Hébergement',
    body: (
      <LegalFacts
        items={[
          ['Hébergeur', host.name],
          ['Adresse', host.address],
          ['Site', <ExternalLink key="site" href={host.website}>{host.website.replace('https://', '')}</ExternalLink>],
          ['Localisation du serveur', host.dataLocation],
        ]}
      />
    ),
  },
  {
    id: 'propriete',
    title: 'Propriété intellectuelle',
    body: (
      <>
        <p>
          La marque {LEGAL.brand}, le logo, les textes, l’interface et le logiciel du site sont protégés. Toute reproduction
          ou réutilisation sans autorisation écrite de l’éditeur est interdite.
        </p>
        <p>
          Les exemples de coupures et de revues présentés sur la page d’accueil sont fictifs : journaux et contenus inventés
          pour illustrer le service.
        </p>
      </>
    ),
  },
  {
    id: 'donnees',
    title: 'Données personnelles',
    body: (
      <p>
        Le traitement de vos données est décrit dans la <Link to="/confidentialite">politique de confidentialité</Link> ; les
        conditions d’utilisation du service figurent dans les <Link to="/cgu">conditions générales</Link>.
      </p>
    ),
  },
  {
    id: 'contact',
    title: 'Contact',
    body: <LegalContact />,
  },
]

export default function LegalNoticePage() {
  return (
    <LegalDocument
      title="Mentions légales"
      description="Mentions légales du site Revue de Presse : éditeur, direction de la publication, hébergeur et contact."
      intro={<p>Informations sur l’éditeur et l’hébergeur du site {LEGAL.brand}.</p>}
      sections={SECTIONS}
    />
  )
}
