# Critique — Revue de Presse, présentation (60 s, 16:9 + 9:16)

## Round 1
| hook | read | motion | variety | brand | sync | min |
|  7   |  7   |   7    |    8    |   8   |  8   |  7  |

Preuves : b0 s'ouvre serré sur une page qui claque (secousse), mais la moitié gauche reste vide jusqu'à « Chaque » (b1) ; à 640 px, titres, cartes points clés, classement et écran final se lisent, l'écran du téléphone (b20–27) non ; ressorts + flou de mouvement propres sur l'amarrage du bandeau (b43) et le reclassement (b49.6) ; un nouvel élément toutes les 2–4 s ; uniquement de vraies captures, Fraunces + Inter, un seul accent ambre ; sync.py : 43/65 accents < 20 ms (médiane 5,7 ms ; les écarts sont des « whoosh » ancrés sur leur crête), master −14,0 LUFS / −1,3 dBTP.

Worst three (most damaging first):
1. [b83.3–84.2, both] Le balayage ambre découvre un écran final vide pendant ~0,2 s : le logo part de l'échelle 0 à b83.95 → le moment de marque perd son élan → démarrer le ressort du logo à b83.7 et le mot-symbole à b83.8 pour que le balayage dévoile un logo déjà en mouvement.
2. [b20–27, 16:9] La scène de dépôt est une juxtaposition statique : l'écran du téléphone est illisible et les pages qui y plongent passent entre deux images clés → la phrase « Photographiez les unes avec votre téléphone » n'a pas d'image forte → caméra : zoom 1.22 centré sur le téléphone pendant D1 (b20–24), recul à 1.0 sur D2 (b24.25) quand les cartes bureau arrivent ; pages agrandies (420 px) pour qu'elles se lisent en vol.
3. [b76–84, both] Équipe + catégories : après l'entrée, 5 s quasi immobiles (dérive de 12 px) → ça ressemble à une diapositive → poussée caméra 1 → 1.06 sur b77–84 et parallaxe opposée des deux cartes (±40 px), la carte catégories arrive avec un léger tangage (wobble).

Checks failed: aucun (pas de bordures/étiquettes d'angle, pas de titre centré sur dégradé, pas de fondu par défaut ; plus long passage sans événement b51.4–55.6 = 2,5 s ; 9:16 recomposé, pas recadré ; écran final immobile 2,5 s après le dernier mot ; conforme au découpage validé, plus l'appel WhatsApp demandé ensuite).
Verdict: ANOTHER ROUND

## Round 2
| hook | read | motion | variety | brand | sync | min |
|  8   |  7   |   8    |    8    |   8   |  8   |  7  |

Preuves : b0 cadre désormais la page qui claque au centre (×1.38) puis recule vers la pile, le titre ne chevauche plus la pile (16:9 et 9:16) ; le balayage ambre de b83.3 dévoile un logo déjà en mouvement ; caméra sur le téléphone pendant « Photographiez les unes » (b20–24) ; parallaxe + poussée sur équipe/catégories ; sync inchangée (43/65 < 20 ms, médiane 5,7 ms).

Worst three (most damaging first):
1. [b24–27, 16:9] Sur « ou déposez vos PDF », la caméra recule à 1.0 : à 640 px le titre « Glissez-déposez vos PDF et photos » fait ~8 px, illisible ; seul le bouton se lit → clé caméra intermédiaire ×1.32 centrée sur la zone de dépôt (1350, 360) à b24.1, recul à 1.0 à b25.9 juste avant que le bouton n'apparaisse.
2. [b40–43, both] Le bandeau « REVUE DE PRESSE » reste 3 s immobile après son atterrissage (le moment fort est plat) → poussée caméra 1 → 1.06 sur b40.3–43 et léger rebond de l'ombre, pour que le plan vive jusqu'à l'amarrage.
3. [b14–20, both] Le sous-titre du logo « Veille média augmentée par l'IA » (32 px) tombe à ~11 px à taille téléphone → 42 px en 16:9, 40 px en 9:16.

Checks failed: aucun.
Verdict: ANOTHER ROUND

## Round 3
| hook | read | motion | variety | brand | sync | min |
|  8   |  8   |   8    |    8    |   8   |  8   |  8  |

Preuves : b0 = page plein cadre qui claque (secousse + impact), titre avec la voix à 0,6 s ; à 640 px tous les messages se lisent dans les deux formats (titres, « Glissez-déposez vos PDF et photos » grâce à la clé caméra ×1.32, étapes de l'analyse, classement 1–5, cartes points clés, boutons d'export, adresse et numéro WhatsApp) — le corps des articles reste une texture de document, volontairement ; ressorts avec dépassement, flou de mouvement, caméra qui vit sur le moment fort (b40–43) et sur l'équipe ; transitions motivées (surligneur → logo, poussées, balayages ambre) ; uniquement de vraies captures, Fraunces + Inter, un seul accent ; sync 43/65 < 20 ms (médiane 5,7 ms, écarts = whooshes ancrés sur leur crête), −14,0 LUFS / −1,3 dBTP.

Restant (à améliorer ensuite) :
1. Le balayage de transition est un parallélogramme ambre net ; un vrai tracé de surligneur (bords irréguliers, transparence en bout) serait plus fidèle au logo.
2. L'accéléré de l'analyse saute d'état en état (~12 images/s) : il se lit comme un accéléré, mais l'anneau de % pourrait être interpolé.
3. Dans la scène de dépôt, l'écran du téléphone reste illisible à taille téléphone (c'est la vraie capture mobile, montrée petite).

Checks failed: aucun.
Verdict: READY
