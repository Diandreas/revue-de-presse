import { Link } from 'react-router-dom'
import {
  ExternalLink,
  LegalContact,
  LegalDocument,
  LegalEmail,
  LegalTable,
  type LegalSection,
} from '../components/LegalDocument'
import { LEGAL, hasLegalEmail, isPlaceholder } from '../lib/legal'

const { publisher, host, aiProvider } = LEGAL

const LAW = 'loi n° 2024/017 relative à la protection des données à caractère personnel au Cameroun'

/** Politique de confidentialité (texte à faire relire par un juriste). */
const SECTIONS: LegalSection[] = [
  {
    id: 'responsable',
    title: 'Qui est responsable de vos données ?',
    body: (
      <>
        <p>
          {publisher.name}, éditeur du service {LEGAL.brand} (coordonnées dans les{' '}
          <Link to="/mentions-legales">mentions légales</Link>), est responsable des traitements liés aux comptes
          utilisateurs, à la relation commerciale, à la facturation et à la sécurité du service.
        </p>
        <p>
          Les documents déposés par une organisation cliente peuvent contenir des données personnelles (par exemple les
          personnes citées dans les articles). Pour ces données, l’organisation cliente est responsable du traitement ;
          nous agissons comme sous-traitant, uniquement sur ses instructions et pour lui fournir le service.
        </p>
      </>
    ),
  },
  {
    id: 'donnees',
    title: 'Les données que nous traitons',
    body: (
      <>
        <ul>
          <li>
            <strong>Compte :</strong> nom, adresse e-mail professionnelle, mot de passe (enregistré sous forme hachée, jamais
            en clair), rôle, organisation, dates d’inscription et d’acceptation des conditions.
          </li>
          <li>
            <strong>Contenus :</strong> documents déposés (PDF, photos de pages), texte extrait, revues, points clés et
            catégories de détection.
          </li>
          <li>
            <strong>Abonnement :</strong> formule, période, devis, factures et échanges liés au règlement.
          </li>
          <li>
            <strong>Données techniques :</strong> adresse IP, journaux de connexion et d’erreur, cookie de session.
          </li>
          <li>
            <strong>Échanges :</strong> messages adressés à notre équipe par WhatsApp ou par e-mail.
          </li>
        </ul>
        <p>
          Aucun paiement n’est effectué sur le site : nous ne collectons aucune donnée de carte bancaire ou de compte Mobile
          Money. Nous n’utilisons ni cookie publicitaire, ni outil de mesure d’audience.
        </p>
      </>
    ),
  },
  {
    id: 'finalites',
    title: 'Pourquoi nous les traitons (finalités et bases légales)',
    body: (
      <>
        <LegalTable
          head={['Finalité', 'Base légale']}
          rows={[
            [
              'Fournir le service : comptes, lecture et analyse des documents, revues, exports',
              'Exécution du contrat (conditions générales)',
            ],
            [
              'Gérer la relation commerciale : devis, activation et renouvellement des abonnements, factures, assistance',
              'Exécution du contrat ; obligations légales comptables et fiscales',
            ],
            [
              'Sécuriser le service : authentification, prévention des abus et des fraudes, journaux techniques',
              'Intérêt légitime à protéger le service et ses utilisateurs',
            ],
            ['Améliorer le service : correction des erreurs, statistiques d’usage agrégées', 'Intérêt légitime'],
            ['Vous informer des évolutions importantes du service ou des conditions', 'Exécution du contrat'],
          ]}
        />
        <p className="mt-3">Nous ne vendons pas vos données et ne les utilisons pas à des fins publicitaires.</p>
      </>
    ),
  },
  {
    id: 'ia',
    title: 'Analyse des documents par l’intelligence artificielle',
    body: (
      <>
        <p>
          Pour produire la revue, le texte et les images des documents déposés sont transmis à {aiProvider.name} (
          {aiProvider.address}, <ExternalLink href={aiProvider.website}>mistral.ai</ExternalLink>), qui fournit les modèles
          d’analyse. Ces traitements sont réalisés dans l’{aiProvider.dataLocation}.
        </p>
        <p>
          {aiProvider.name} agit en qualité de sous-traitant, pour notre compte et selon ses conditions contractuelles de
          traitement des données.
          {!isPlaceholder(aiProvider.dataTerms) && (
            <>
              {' '}
              Conservation et réutilisation des contenus chez {aiProvider.name} : {aiProvider.dataTerms}.
            </>
          )}
        </p>
        <p>
          Les résultats de l’IA peuvent être inexacts ou incomplets : voir les{' '}
          <Link to="/cgu#ia">conditions générales</Link>.
        </p>
      </>
    ),
  },
  {
    id: 'destinataires',
    title: 'Qui peut accéder à vos données ?',
    body: (
      <ul>
        <li>Les membres de votre organisation, selon leur rôle. Les données d’une organisation ne sont jamais visibles par une autre.</li>
        <li>
          Notre équipe, pour l’assistance, l’activation des abonnements et la sécurité, dans la limite de ce qui est
          nécessaire.
        </li>
        <li>
          Nos sous-traitants techniques :
          <ul className="mt-2">
            <li>
              hébergement du site et des données : {host.name} ({host.address}) — serveur situé : {host.dataLocation} ;
            </li>
            <li>analyse des documents par l’IA : {aiProvider.name} (France, Union européenne) ;</li>
            <li>polices de caractères : Google Fonts (Google), qui reçoit l’adresse IP du navigateur au chargement des pages ;</li>
            <li>messagerie : WhatsApp (Meta), lorsque vous choisissez de nous écrire par ce canal.</li>
          </ul>
        </li>
        <li>Les autorités administratives ou judiciaires, sur demande légalement fondée.</li>
      </ul>
    ),
  },
  {
    id: 'transferts',
    title: 'Transferts hors du Cameroun',
    body: (
      <p>
        Certains de nos sous-traitants sont établis ou traitent les données hors du Cameroun, notamment dans l’Union
        européenne pour l’analyse par l’IA. Ces transferts sont nécessaires à la fourniture du service et sont encadrés par
        des engagements contractuels de confidentialité et de sécurité, conformément à la {LAW}. Les prestataires établis
        dans l’Union européenne sont en outre soumis au règlement général sur la protection des données (RGPD).
      </p>
    ),
  },
  {
    id: 'conservation',
    title: 'Combien de temps nous les conservons',
    body: (
      <LegalTable
        head={['Données', 'Durée de conservation']}
        rows={LEGAL.retention.map((item) => [item.data, item.duration])}
      />
    ),
  },
  {
    id: 'securite',
    title: 'Sécurité',
    body: (
      <>
        <p>
          Connexion chiffrée (HTTPS), mots de passe hachés, cloisonnement strict des données entre organisations, accès de
          notre équipe limité au strict nécessaire et sauvegardes chiffrées : nous mettons en œuvre des mesures techniques et
          organisationnelles adaptées pour protéger vos données.
        </p>
        <p>
          En cas de violation de données susceptible de vous affecter, nous vous en informons et prévenons l’autorité
          compétente dans les conditions prévues par la loi.
        </p>
      </>
    ),
  },
  {
    id: 'droits',
    title: 'Vos droits',
    body: (
      <>
        <p>
          Conformément à la {LAW}, vous disposez d’un droit d’accès, de rectification, d’effacement, d’opposition et de
          limitation du traitement de vos données, du droit à leur portabilité dans les cas prévus par la loi, et du droit de
          retirer à tout moment un consentement donné.
        </p>
        <p>
          Pour les exercer, écrivez-nous{' '}
          {hasLegalEmail && (
            <>
              par e-mail (<LegalEmail />) ou{' '}
            </>
          )}
          sur WhatsApp (
          <ExternalLink href={publisher.whatsappUrl}>{publisher.phone}</ExternalLink>) en précisant votre demande ; nous
          pouvons vous demander de justifier de votre identité. Nous répondons dans un délai d’un mois.
        </p>
        <p>
          Pour les données contenues dans les documents d’une organisation cliente, adressez-vous d’abord à cette
          organisation : nous l’aiderons à vous répondre. Vous pouvez également saisir l’autorité de protection des données à
          caractère personnel instituée par la loi.
        </p>
      </>
    ),
  },
  {
    id: 'cookies',
    title: 'Cookies',
    body: (
      <p>
        Le service n’utilise qu’un cookie strictement nécessaire : un cookie de session sécurisé, inaccessible aux scripts,
        qui maintient votre connexion. Aucun cookie publicitaire ou de mesure d’audience n’est déposé.
      </p>
    ),
  },
  {
    id: 'modifications',
    title: 'Modifications de cette politique',
    body: (
      <p>
        Nous pouvons mettre à jour cette politique ; la date en tête de page indique la version en vigueur. En cas de
        changement important, nous vous prévenons dans l’application ou par e-mail.
      </p>
    ),
  },
  {
    id: 'contact',
    title: 'Nous contacter',
    body: <LegalContact />,
  },
]

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Politique de confidentialité"
      description="Données traitées par Revue de Presse, finalités, sous-traitants (hébergeur, Mistral AI), durées de conservation et droits des personnes selon la loi camerounaise n° 2024/017."
      intro={
        <p>
          Cette politique explique quelles données personnelles nous traitons lorsque vous utilisez {LEGAL.brand}, pourquoi,
          avec qui nous les partageons, combien de temps nous les conservons et comment exercer vos droits, dans le cadre de
          la {LAW}.
        </p>
      }
      sections={SECTIONS}
    />
  )
}
