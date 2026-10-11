import { Link } from 'react-router-dom'
import { LegalContact, LegalDocument, LegalEmail, type LegalSection } from '../components/LegalDocument'
import { LEGAL, TERMS_VERSION, hasLegalEmail, isPlaceholder } from '../lib/legal'

const { publisher } = LEGAL

/** Conditions générales d'utilisation et de vente (texte à faire relire par un juriste). */
const SECTIONS: LegalSection[] = [
  {
    id: 'objet',
    title: 'Objet et acceptation',
    body: (
      <>
        <p>
          Le service {LEGAL.brand} (le « Service ») est édité par {publisher.name} (l’« Éditeur »), dont l’identité complète
          figure dans les <Link to="/mentions-legales">mentions légales</Link>.
        </p>
        <p>
          Les présentes conditions (les « Conditions ») s’appliquent à toute organisation qui crée un espace sur le Service
          (le « Client ») et à chaque personne qu’elle y invite (les « Utilisateurs »). La personne qui crée l’espace déclare
          être habilitée à engager l’organisation.
        </p>
        <p>
          En cochant la case prévue lors de l’inscription, le Client accepte la version des Conditions en vigueur,
          identifiée par sa date (version {TERMS_VERSION}). En cas de contradiction, les conditions particulières d’un
          devis accepté prévalent sur les présentes.
        </p>
      </>
    ),
  },
  {
    id: 'service',
    title: 'Description du Service',
    body: (
      <>
        <p>
          Le Service permet de déposer des documents de presse (PDF ou photos de pages), d’en faire lire et analyser le texte
          par un système d’intelligence artificielle, puis d’obtenir une revue de presse mise en page, des points clés
          classés par catégorie et des exports aux formats Word et PDF.
        </p>
        <p>
          Les fonctionnalités du Service peuvent évoluer. L’Éditeur informe le Client de toute évolution qui supprimerait ou
          réduirait de façon importante une fonctionnalité essentielle.
        </p>
      </>
    ),
  },
  {
    id: 'compte',
    title: 'Compte, accès et sécurité',
    body: (
      <ul>
        <li>
          Le propriétaire de l’espace gère les Utilisateurs et leurs rôles (propriétaire, administrateur, membre). Le Client
          est responsable de l’usage fait du Service par les Utilisateurs qu’il invite.
        </li>
        <li>
          Les identifiants sont personnels et confidentiels. Toute utilisation non autorisée ou suspecte doit être signalée
          sans délai à l’Éditeur.
        </li>
        <li>Le nombre d’Utilisateurs et de revues par période dépend de la formule en cours.</li>
      </ul>
    ),
  },
  {
    id: 'essai',
    title: 'Essai gratuit',
    body: (
      <ul>
        <li>
          La création d’un espace ouvre un essai gratuit de 7 jours, sans moyen de paiement ni engagement, dans les limites
          (nombre de revues et de membres) de la formule d’essai affichées dans l’espace.
        </li>
        <li>
          À la fin de l’essai, aucune somme n’est due et aucun abonnement n’est souscrit automatiquement. Les revues déjà
          produites restent consultables ; la création de nouvelles revues nécessite l’activation d’un abonnement.
        </li>
        <li>
          L’Éditeur peut refuser ou interrompre un essai en cas d’abus (essais multiples, usage contraire aux Conditions).
        </li>
      </ul>
    ),
  },
  {
    id: 'abonnement',
    title: 'Abonnement, devis et paiement',
    body: (
      <ul>
        <li>
          Les prix sont établis sur devis, selon le volume de revues, le nombre d’Utilisateurs et l’accompagnement souhaité.
          Le Client en fait la demande auprès de l’Éditeur par WhatsApp ({publisher.phone})
          {hasLegalEmail && (
            <>
              {' '}
              ou par e-mail (<LegalEmail />)
            </>
          )}
          .
        </li>
        <li>
          Aucun paiement n’est effectué en ligne. Le devis accepté précise la formule, la durée de la période d’abonnement,
          le prix (hors taxes ou toutes taxes comprises) et les modalités de règlement ; une facture est émise.
        </li>
        <li>
          L’abonnement est activé ou prolongé par l’Éditeur après réception du règlement. Il court jusqu’à la date de fin
          indiquée dans l’espace du Client, rubrique « Abonnement ».
        </li>
        <li>
          Sauf stipulation contraire du devis, l’abonnement n’est pas reconduit tacitement : à son échéance, il est renouvelé
          pour une nouvelle période sur demande du Client et après règlement. Sans renouvellement, les revues restent
          consultables mais la création de nouvelles revues est suspendue.
        </li>
        <li>
          Les quotas de la formule (revues par période, membres) s’apprécient sur la période en cours ; les revues non
          utilisées ne sont pas reportées sur la période suivante.
        </li>
      </ul>
    ),
  },
  {
    id: 'resiliation',
    title: 'Durée et résiliation',
    body: (
      <ul>
        <li>Les Conditions s’appliquent pendant toute la durée d’utilisation du Service.</li>
        <li>
          Le Client peut cesser d’utiliser le Service à tout moment et demander la clôture de son espace. La période
          d’abonnement en cours, déjà réglée, n’est pas remboursée, sauf manquement de l’Éditeur ou stipulation contraire du
          devis.
        </li>
        <li>
          L’Éditeur peut suspendre ou résilier l’accès en cas de manquement grave du Client (usage illicite, atteinte à la
          sécurité du Service, défaut de paiement…), après une mise en demeure restée sans effet pendant 15 jours, sauf
          urgence.
        </li>
        <li>
          Avant la clôture de l’espace, le Client peut récupérer ses revues (exports Word et PDF). Les données sont ensuite
          supprimées selon les durées indiquées dans la <Link to="/confidentialite">politique de confidentialité</Link>.
        </li>
      </ul>
    ),
  },
  {
    id: 'contenus',
    title: 'Contenus fournis par le Client',
    body: (
      <ul>
        <li>
          Le Client reste titulaire de ses droits sur les documents qu’il dépose et sur les revues produites à partir de
          ceux-ci. Il garantit disposer des droits nécessaires (abonnements, autorisations des éditeurs de presse le cas
          échéant) pour reproduire ces documents dans le Service et pour diffuser les revues.
        </li>
        <li>
          Les revues sont destinées à l’information du Client. Leur diffusion à des tiers ou leur publication relève de sa
          seule responsabilité, dans le respect des droits des auteurs et éditeurs de presse et des personnes citées.
        </li>
        <li>
          Le Client s’interdit de déposer des contenus illicites, malveillants ou sans rapport avec la revue de presse.
        </li>
        <li>
          Le Client autorise l’Éditeur à traiter ces contenus pour la seule fourniture du Service (stockage, lecture du
          texte, analyse par l’IA, génération des exports). L’Éditeur ne les utilise à aucune autre fin et ne les
          communique qu’aux sous-traitants techniques listés dans la politique de confidentialité.
        </li>
      </ul>
    ),
  },
  {
    id: 'ia',
    title: 'Intelligence artificielle : une aide, pas un avis',
    body: (
      <ul>
        <li>
          Les revues, notices et points clés sont produits automatiquement par des modèles d’intelligence artificielle. Ils
          peuvent comporter des erreurs, des omissions ou des approximations (photo peu lisible, article attribué au mauvais
          journal, résumé incomplet).
        </li>
        <li>
          Les étiquettes <strong>« risque juridique »</strong>, <strong>« intox potentielle »</strong>, « point important »
          et les catégories personnalisées sont une aide à la lecture. Elles ne constituent ni un avis ou une consultation
          juridique, ni une vérification des faits, et n’engagent pas l’Éditeur sur la qualification juridique ou la
          véracité d’une information.
        </li>
        <li>
          Le Client relit les revues et les points clés avant toute diffusion ou décision, et consulte un professionnel du
          droit pour toute question juridique.
        </li>
      </ul>
    ),
  },
  {
    id: 'disponibilite',
    title: 'Disponibilité et assistance',
    body: (
      <ul>
        <li>
          L’Éditeur met en œuvre des moyens raisonnables pour rendre le Service accessible en permanence, sans garantir une
          disponibilité ininterrompue : maintenances, mises à jour et incidents chez ses prestataires (hébergeur, fournisseur
          d’IA) ou sur les réseaux peuvent l’interrompre.
        </li>
        <li>
          L’assistance est assurée par WhatsApp ({publisher.phone}) et par e-mail, dans des délais raisonnables.
        </li>
      </ul>
    ),
  },
  {
    id: 'responsabilite',
    title: 'Responsabilité',
    body: (
      <ul>
        <li>
          L’Éditeur est tenu d’une obligation de moyens. Il n’est pas responsable des dommages indirects (perte de chiffre
          d’affaires, atteinte à l’image, perte de chance), ni des conséquences des décisions prises ou des diffusions faites
          sur la base des revues et des points clés.
        </li>
        <li>
          Sauf faute lourde ou intentionnelle, la responsabilité totale de l’Éditeur est limitée aux sommes effectivement
          payées par le Client pour le Service au cours des douze mois précédant le fait qui l’engage. Pendant l’essai
          gratuit, le Service est fourni sans garantie.
        </li>
        <li>
          Le Client est responsable des contenus qu’il dépose, de l’usage qu’il fait des revues et du respect des Conditions
          par ses Utilisateurs.
        </li>
      </ul>
    ),
  },
  {
    id: 'propriete',
    title: 'Propriété intellectuelle',
    body: (
      <ul>
        <li>
          Le Service, son logiciel, la marque « {LEGAL.brand} », ses éléments graphiques et sa documentation appartiennent à
          l’Éditeur ou à ses concédants. Le Client bénéficie d’un droit d’utilisation non exclusif et non transférable,
          pour la durée de son essai ou de son abonnement.
        </li>
        <li>Toute reproduction, extraction, ingénierie inverse ou revente du Service est interdite sans accord écrit.</li>
        <li>Les articles de presse restent la propriété de leurs auteurs et éditeurs.</li>
      </ul>
    ),
  },
  {
    id: 'donnees',
    title: 'Données personnelles et confidentialité',
    body: (
      <>
        <p>
          Les traitements de données personnelles sont décrits dans la{' '}
          <Link to="/confidentialite">politique de confidentialité</Link>. Pour les données contenues dans les documents qu’il
          dépose, le Client agit en qualité de responsable du traitement et l’Éditeur en qualité de sous-traitant ; un accord
          de traitement des données peut être signé sur demande.
        </p>
        <p>
          Chaque partie garde confidentielles les informations non publiques de l’autre partie dont elle a connaissance à
          l’occasion du Service.
        </p>
      </>
    ),
  },
  {
    id: 'modification',
    title: 'Modification des Conditions',
    body: (
      <p>
        L’Éditeur peut modifier les Conditions, notamment pour suivre l’évolution du Service ou de la réglementation. La
        nouvelle version, datée, est publiée sur cette page et portée à la connaissance du Client au moins 30 jours avant son
        entrée en vigueur, sauf obligation légale. Le Client qui la refuse peut mettre fin au Service ; la poursuite de
        l’utilisation après cette date vaut acceptation.
      </p>
    ),
  },
  {
    id: 'droit',
    title: 'Droit applicable et litiges',
    body: (
      <>
        <p>Les Conditions sont régies par le droit camerounais, y compris les Actes uniformes OHADA applicables.</p>
        <p>
          En cas de différend, les parties recherchent d’abord une solution amiable. À défaut d’accord dans un délai de 30
          jours, le litige est porté devant les juridictions camerounaises compétentes
          {isPlaceholder(LEGAL.jurisdiction) ? '' : ` (${LEGAL.jurisdiction})`}.
        </p>
      </>
    ),
  },
  {
    id: 'contact',
    title: 'Contact',
    body: <LegalContact />,
  },
]

export default function TermsPage() {
  return (
    <LegalDocument
      showVersion
      title="Conditions générales d’utilisation et de vente"
      description="Conditions générales d’utilisation et de vente du service Revue de Presse : essai gratuit, abonnement sur devis activé par notre équipe, résiliation, responsabilités et limites des analyses par l’IA."
      intro={
        <p>
          Ces conditions encadrent l’accès au service {LEGAL.brand} et son utilisation par les organisations clientes et
          leurs membres : essai gratuit, abonnement sur devis activé par notre équipe, responsabilités de chacun et limites
          des analyses produites par l’intelligence artificielle.
        </p>
      }
      sections={SECTIONS}
    />
  )
}
