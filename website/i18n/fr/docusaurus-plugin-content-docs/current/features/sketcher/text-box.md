---
description:
  "Placez du texte gravé, des étiquettes et des numéros de série sur une esquisse avec l'outil de
  zone de texte de Rayforge."
---

# Zone de texte

L'outil de zone de texte (`G+T`) place du texte sur l'esquisse comme géométrie modifiable — texte
gravé, étiquettes et numéros de série. Les zones de texte sont entièrement paramétriques : les
glyphes vivent dans un cadre contraint, si bien qu'ils se résolvent à nouveau dès que le cadre est
déplacé ou dimensionné.

![Un logotype et une étiquette de pièce](/screenshots/addons-sketcher-tool-text-box.webp)

## Créer et modifier du texte

1. Sélectionnez l'outil de zone de texte dans le menu radial, le menu **Esquisse**, ou avec `G+T`.
2. Cliquez à l'endroit où le texte doit commencer : une zone de texte apparaît au point du clic et
   l'outil passe directement en mode modification.
3. Saisissez le texte — la zone se redimensionne pour l'adapter au fur et à mesure.
4. Appuyez sur `Entrée` ou `Échap` pour terminer la modification.

Pour modifier une zone de texte existante, cliquez à l'intérieur. Un double-clic sélectionne un mot,
un triple-clic toute la ligne, et le texte peut être sélectionné et remplacé comme dans n'importe
quel éditeur de texte, y compris `Ctrl+C`/`Ctrl+V`, annuler/rétablir et coller en cours de
modification.

## Propriétés de la police

![Le panneau des propriétés de la police](/screenshots/addons-sketcher-tool-text-box-font-properties.webp)

Le panneau **Propriétés de la police** de la barre latérale contrôle l'apparence de la zone de texte
sélectionnée sur le canevas :

- **Famille de police** — choisissez parmi les polices système installées.
- **Police personnalisée** — choisissez une police que vous avez installée vous-même (voir
  [Polices personnalisées](#custom-fonts)).
- **Taille de la police** — en points.
- Interrupteurs **Gras** et **Italique**.

## Transformations de texte {#text-transforms}

Le même panneau permet de modifier la disposition du texte à l'intérieur de son cadre :

- **Miroir** — inverse le texte de gauche à droite, pour graver au dos d'un matériau transparent.
- **Inverser les caractères** — écrit les caractères dans l'ordre inverse sans les retourner.
- **Vertical** — empile les caractères droits de haut en bas.
- **Rotation** — fait tourner le texte autour du centre de son cadre. Le cadre lui-même reste
  horizontal.
- **À l'envers** — un raccourci pour une rotation de 180°.

Tant que l'une de ces options est active, vous pouvez toujours taper dans la zone de texte, mais
cliquer ne place plus le curseur dans le texte.

## Texte knock-out {#knock-out-text}

Activez **Knock-out** pour graver une plaque en laissant le texte en réserve. La plaque correspond
au cadre de texte agrandi de la **Marge de knock-out** de chaque côté. Le contour contient la plaque
et les lettres ; le remplissage couvre la plaque à l'exception des lettres.

Les parties intérieures des lettres telles que O, A et B ne sont pas conservées, si bien que le
texte knock-out est destiné à la gravure, non à la découpe de pochoirs.

## Texte sur un chemin {#text-on-a-path}

Le texte peut suivre une ligne, un arc, un cercle ou une courbe :

1. Sélectionnez la zone de texte avec la forme qu'elle doit suivre.
2. Activez **Suivre le chemin** dans le panneau Propriétés de la police.

- **Côté du chemin** — **Extérieur** place le texte à gauche du sens du chemin ; **Intérieur** le
  place de l'autre côté et inverse le sens de lecture, de sorte que le texte à l'intérieur d'un
  cercle se lise à l'endroit en bas.
- **Alignement du chemin** — début, centre ou fin du chemin.
- **Décalage du chemin** — décale le texte le long du chemin.
- **Texte inférieur** — sur un cercle, une deuxième ligne de texte centrée en bas à l'intérieur,
  tandis que le texte principal est centré en haut à l'extérieur. Les deux se lisent à l'endroit, ce
  qui permet de créer un tampon ou un sceau rond.

Pour libérer le texte, sélectionnez uniquement la zone de texte et activez à nouveau **Suivre le
chemin**. Si la forme est supprimée, le texte revient dans son cadre.

Le texte sur un chemin conserve sa taille de police, et miroir, vertical, rotation et knock-out ne
s'appliquent pas à lui. Un chemin est une forme unique ; le texte ne se poursuit pas d'une ligne ou
d'un arc au suivant.

## Polices personnalisées {#custom-fonts}

Utilisez **Installer la police…** pour ajouter un fichier `.ttf` ou `.otf`. Les polices installées
apparaissent dans la liste **Police personnalisée** sur chaque esquisse, et **Supprimer la police
personnalisée** supprime celle sélectionnée.

Les polices sont stockées sur votre ordinateur, pas dans le fichier de projet. Lorsqu'un projet
utilise une police qui n'est pas installée, le panneau affiche **Police non installée** et une
police de substitution est utilisée jusqu'à ce que vous installiez la police ou en choisissiez une
autre.

## Préréglages {#presets}

Un préréglage enregistre la police et le style de texte, mais pas le texte lui-même ni le chemin
qu'il suit. Saisissez un nom dans **Enregistrer comme préréglage** pour stocker les paramètres de la
zone de texte sélectionnée, choisissez un nom dans **Préréglage** pour l'appliquer, et utilisez
**Supprimer le préréglage** pour retirer le préréglage sélectionné. L'application d'un préréglage
est une action d'annulation unique.

## Numéros de série {#serial-numbers}

**Insérer un numéro de série** ajoute `{serial()}` au texte, affiche le numéro suivant et explique
que le compteur avance d'un pas chaque fois qu'un travail est envoyé à la machine ou exporté en
G-code. Le cadrage, les aperçus et les travaux annulés ou échoués ne consomment pas de numéro.

Les compteurs sont partagés entre tous les documents et sont gérés dans **Paramètres → Numéros de
série**. La page des paramètres vous guide en trois étapes : créez un compteur, référencez-le avec
`{serial("name")}` ou Insérer un numéro de série dans Propriétés de la police, et notez que le
compteur avance une fois par travail plutôt que pour chaque copie sur le canevas. Chaque carte de
compteur affiche `Use as {serial("name")}. Next number: ...` (ou `{serial()}` pour le compteur par
défaut), ainsi que des commandes pour la valeur de départ, le pas, le remplissage de zéros, le
préfixe et le suffixe.

## Un cadre paramétrique

Une zone de texte n'est pas une image matricielle : ses glyphes sont une véritable géométrie
d'esquisse, disposée dans un cadre défini par une origine et des points de largeur et de hauteur. Le
cadre est dessiné en tiretés comme géométrie de construction, il sert donc de référence de mise en
page et ne se retrouve jamais dans les trajectoires d'outils lors de la fabrication de l'esquisse.
Comme tout le reste dans l'esquisseur, le cadre est contraint, si bien qu'il peut être dimensionné
comme n'importe quelle autre géométrie — modifiez la contrainte de largeur et le texte se résout à
nouveau pour remplir la zone.

Un clic dans une zone de texte avec l'[outil de remplissage](fill.md) bascule le remplissage des
glyphes du texte au lieu de créer un remplissage de région.

## Expressions de modèle

Les zones de texte acceptent les **expressions de modèle** : tout ce qui est entre accolades est
évalué quand l'esquisse se résout, si bien que les étiquettes peuvent afficher des valeurs en direct
comme des dimensions, des dates ou des numéros de série uniques. Voir
[Expressions de modèle dans les zones de texte](expressions.md#template-expressions-in-text-boxes)
pour les détails et les fonctions intégrées.
