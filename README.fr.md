<!-- markdownlint-disable-next-line MD041 -->
<img src="custom_components/syr_connect/brand/logo.png" alt="Syr" width="200">

# SYR Connect - Intégration pour Home Assistant

[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![syr_connect installs](https://img.shields.io/badge/dynamic/json?logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.syr_connect.total)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)
[![Quality scale: Platinum](https://img.shields.io/badge/Quality%20scale-Platinum%20%F0%9F%8F%86-b5d2e0?style=flat)](https://github.com/alexhass/syr_connect/blob/main/quality_scale.yaml)

<!-- ha-marketplace:exclude-start -->

[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

<!-- ha-marketplace:exclude-end -->

Cette intégration personnalisée permet de commander les appareils SYR Connect depuis Home Assistant. Elle peut également être utilisée avec des appareils identiques d'autres marques. Les installations mixtes de différentes marques sont également prises en charge.

| Marque | Lien |
| ------ | ------ |
| comfort by sanibel | <https://comfort-by-sanibel.de/> |
| CONEL | <https://www.conel.de/> |
| DITECH | <https://www.ditech-haustechnik.de/> |
| Hansgrohe Pontos | <https://www.hansgrohe.de/> |
| mein concept | <https://www.mein-concept.de/> |
| mein Optima | <https://www.mein-optima.de/> |
| POLYGONVATRO | <https://www.polygongroup.com/de-DE/> |
| Reliance Valves | <https://www.rwc.com/brands/reliance-valves> |
| SYR | <https://www.syr.de/> |
| SYR Oceanic | <https://www.debestewaterbehandeling.be/> |
| TAKE | <https://take-bad.de/> |

## Captures d'écran

Exemples d'interfaces d'appareils :

![Capture d'écran du LEXplus10S](docs/assets/screenshots/en/lexplus10s.png)

![Capture d'écran du Safe-T+](docs/assets/screenshots/en/safetplus.png)

<!-- ha-marketplace:exclude-start -->

## Installation

[![Ouvrir l'instance Home Assistant et ouvrir un dépôt dans le Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=alexhass&repository=syr_connect&category=integration)

### Marketplace (recommandé)

1. Aller dans Paramètres > Marketplace.
2. Rechercher « SYR Connect ».
3. Cliquer sur « Installer ».
4. Redémarrer Home Assistant.

### Installation manuelle

1. Copier le dossier `syr_connect` dans le répertoire `custom_components`.
2. Redémarrer Home Assistant.

<!-- ha-marketplace:exclude-end -->

## Configuration

[![Ouvrir l'instance Home Assistant et commencer la configuration d'une nouvelle intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)

L'intégration prend en charge deux modes de configuration :

### Configuration avec l'API cloud (tous les appareils)

1. Aller dans Paramètres > Appareils et services.
2. Cliquer sur « + Ajouter une intégration ».
3. Rechercher « SYR Connect ».
4. Sélectionner « Cloud ».
5. Saisir les identifiants de l'application mobile :
   - **Service** : L'application dans laquelle les appareils sont configurés
   - **Nom d'utilisateur** : Nom d'utilisateur du compte dans cette application
   - **Mot de passe** : Mot de passe du compte dans cette application

### Configuration avec l'API locale (appareils récents uniquement)

Pour les appareils récents disposant d'une API JSON locale, par exemple les appareils NeoSoft et Trio, SafeTech Lock, TRIO Lock, AC 3200 et RSA Connect ainsi que leurs appareils identiques d'autres marques. La sélection du modèle lors de la configuration liste tous les modèles pris en charge :

1. Aller dans Paramètres > Appareils et services.
2. Cliquer sur « + Ajouter une intégration ».
3. Rechercher « SYR Connect ».
4. Sélectionner « Local ».
5. Saisir les informations de l'appareil :
   - **Modèle de l'appareil** : Modèle de l'appareil (p. ex. NeoSoft 2500 Connect)
   - **Nom d'hôte ou adresse IP** : Adresse IP ou nom d'hôte de l'appareil (p. ex. `192.168.178.199`)

**Remarque** : L'adresse IP de l'appareil figure dans la liste des clients DHCP du routeur ou dans le menu de l'écran de l'appareil.

**Important** : Pour un fonctionnement stable, l'appareil doit avoir une **adresse IP statique** ou un **bail DHCP réservé** (réservation DHCP). Si l'adresse IP de l'appareil change, l'intégration perd la connexion. La nouvelle adresse se saisit avec « Reconfigurer » dans le menu à trois points (⋮) de l'entrée. L'entrée reste liée à son appareil par le numéro de série : un autre appareil à la nouvelle adresse est refusé et doit être ajouté comme nouvelle entrée. Un nom d'hôte peut aussi être utilisé si le réseau prend en charge la résolution DNS locale.

## Fonctionnalités

L'intégration crée automatiquement des entités pour tous les appareils SYR Connect du compte.

### Appareils pris en charge

Cette intégration fonctionne avec les adoucisseurs d'eau et les détecteurs de fuites SYR ainsi qu'avec d'autres appareils qui apparaissent dans le cloud SYR Connect (via l'application mobile correspondante).

Testés et signalés comme fonctionnels :

- CONEL CLEAR PRO FILL
- CONEL CLEAR PRO Floor Sensor
- CONEL CLEAR PRO LEAKAGE PROTECTION
- CONEL CLEAR PRO SOFT
- CONEL CLEAR PRO SOFT TWIN
- concept 200 Dual Water Softener
- concept Dual Water Softener
- concept Single Water Softener
- concept SafeFloor Floor Sensor
- DITECH Dual Water Softener
- DITECH Single Water Softener
- DITECH Wireless Floor Sensor
- Optima Dual Water Softener
- Optima Single Water Softener
- Optima T2 Dual Water Softener
- Optima T2 Floor Sensor
- POLYGONVATRO Wireless Floor Sensor
- Sanibel Leak Protection Module A25
- Sanibel Softwater DUO A25
- Sanibel Softwater UNO A25
- Sanibel Wireless Floor Sensor A25
- SYR All-in-One+
- SYR LEX 1500 Connect Single (LEX10/LEX20/LEX30/LEX40/LEX60/LEX80/LEX100)
- SYR LEX Plus 10 Connect
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect
- SYR NeoSoft 2500 Connect
- SYR NeoSoft 5000 Connect
- SYR NeoSoft Lock Connect I
- SYR NeoSoft Lock Connect II
- SYR SafeFloor Connect
- SYR Safe-T+ Connect
- SYR SafeTech Connect
- SYR SafeTech plus Connect
- SYR SafeTech V3 Connect
- SYR SafeTech V4 Connect
- SYR TRIO DFR/LS Connect 2425
- SYR TRIO Lock Connect
- SYR Oceanic i-LEX / Limex iQ Single (L10/L12/L15/L20/L25/L30/L40/L50/L60/L70/L80/L90/L100)
- TAKE Dual Water Softener
- TAKE Single Water Softener

D'autres appareils sont également intéressants, mais doivent éventuellement être intégrés ou au moins testés (merci de les signaler) :

- CONEL CLEAR PRO MULTICONTROL-KIT
- concept 200 Replacement Filter
- concept 300 Automatic Backwash RSA
- concept 300 Trio Filter with Leak Protection
- DITECH Automatic Backwash HWS/RF
- DITECH Backwash Filter Protect
- DITECH Connection Module Plus
- DITECH Hygiene Flush Box
- Hansgrohe PontosBase
- Optima T Replacement Filter
- POLYGONVATRO SafeTech Connect (vendu avec l'assurance habitation AXA sous le nom « Wasserwächter »)
- RWC MultiSafe Floor Leak Sensor
- RWC MultiSafe Leak Detector Control Valve
- Sanibel Automatic Backwash System RSA A25
- SYR AC 3200 Connect
- SYR AC All-in-One 3228 Connect
- SYR CONTROLICmini
- SYR HVA
- SYR HygBox Connect
- SYR Hygiene Module (froide / chaude / froide et chaude)
- SYR Inliner-HWA 3300
- SYR IT 3000 Pendulum system
- SYR LEX 1500 Connect Alternating
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Triple
- SYR NeoDos Connect
- SYR RSA Connect
- SYR Safe-T Communication Module
- SYR Safe-T Hygiene Module
- SYR Safe-T Master / Slave
- SYR SafeTech Lock Connect
- SYR Trio LS Connect

**Remarque** : Si un appareil est visible dans le compte SYR Connect, l'intégration le détecte et crée automatiquement les entités. Pour un « appareil non testé », le partage des diagnostics aide à trouver les valeurs inconnues et à vérifier que tout fonctionne comme prévu. Cela permet aussi d'étendre la liste des appareils testés.

### Appareils non pris en charge

- Appareils SYR Oceanic Limex SMART COMPACT/MINI/MAXI. Ces appareils utilisent un autre portail cloud (`i-lexconnect.com`) au lieu du service cloud SYR Connect. Il s'agit d'appareils Husty SaoCal vendus sous une autre marque.
- Appareils Husty SaoCal. Voir [husty_integration_home_assistant](https://github.com/trafopowielacz/husty_integration_home_assistant).

### Fonctionnalités prises en charge

#### Capteurs

L'intégration offre une surveillance complète des appareils :

#### Qualité de l'eau et capacité

- Surveillance de la dureté de l'eau brute et de l'eau adoucie
- Conductivité de l'eau (µS/cm)
- Plage de dureté de l'eau (douce, moyenne, dure), estimée à partir de la conductivité (famille SafeTech)
- Facteur de conductivité
- Température de l'eau (°C)
- Suivi de la capacité d'adoucissement restante
- Capacité de résine par réservoir (jusqu'à 3 réservoirs, %)
- Surveillance du volume total
- Affichage de l'unité de dureté de l'eau

#### Informations sur la régénération

- État de la régénération et indicateur du réservoir actif (jusqu'à 3 réservoirs)
- Mode de régénération (Standard / ECO / Power / Automatique)
- Nombre de régénérations effectuées
- Horodatage de la dernière régénération
- Réglages de l'intervalle de régénération
- Horaire de régénération
- Compteurs de cycles et durées

#### Gestion du sel

- Quantité de sel dans les réservoirs (1–3)
- Réserve de sel (semaines restantes)
- Capacité de réserve de résine par bouteille

#### Surveillance du système

- Surveillance de la pression de l'eau
- Débit (actuel et instantané)
- Compteur de débit (consommation totale)
- Tension de la batterie et du secteur
- État des alarmes, notifications et avertissements (code actuel et 8 dernières entrées de l'historique)

#### Protection contre les fuites (LEXplus10SL / Trio DFR/LS)

- Limites de volume et de durée de la protection contre les fuites (profils présent et absent)
- Index du profil de protection contre les fuites actif
- Profils de protection contre les fuites 1–8 (limite de volume, durée maximale, seuil de débit, indicateurs d'avertissement et d'avertisseur)
- Minuterie de désactivation temporaire
- Seuil d'avertissement de fuite (%)

#### Test de microfuite (Trio DFR/LS, SafeTech, SafeTech+, TRIO Lock, SafeTech Lock)

- Intervalle et état du test de microfuite
- Durée du test et nombre d'événements

#### Phase d'auto-apprentissage (Trio DFR/LS, SafeTech+, TRIO Lock, SafeTech Lock)

- Temps d'auto-apprentissage restant et écoulé
- Débit et volume cumulé pendant l'auto-apprentissage
- Réglages de l'auto-apprentissage : marge de volume et de temps, marge de débit, débit minimal

#### Capteur de sol (SafeFloor)

- Humidité et température actuelles
- Niveau de batterie (%)
- État de l'alarme

#### Filtre et contre-lavage

- Type de filtre (SafeTech, SafeTech Lock, TRIO Lock, AC All-in-One 3228 Connect)
- Teneur en fer (famille LEX)
- Compteurs de contre-lavages automatiques et manuels (contre-lavage automatique RSA)

#### Maintenance

- Prochaines dates de maintenance prévues (semestrielle et annuelle)
- Consommation d'eau journalière prévue

#### Informations sur l'appareil

- Numéro de série
- Version du micrologiciel et modèle
- Type d'appareil et fabricant
- Informations réseau (IP, MAC, passerelle)
- État de la connexion Wi-Fi et intensité du signal
- Fuseau horaire (décalage UTC)

#### Capteurs binaires

- **Avertisseur en cas d'alarme** : Indique si l'avertisseur retentit en cas d'alarme.
- **Protection contre les fuites** : Indique si la protection contre les fuites est active ou désactivée.
- **Test de vanne** : Indique si un test de vanne est en cours.
- **Vérification du micrologiciel** : Indique si un nouveau micrologiciel est disponible (vérifié au démarrage et toutes les 6 heures).
- **Heure d'été** : Indique si l'appareil passe automatiquement à l'heure d'été.
- **Capteur de température**, **Capteur de pression**, **Capteur de conductivité** : Indiquent si le capteur de mesure est actif ou désactivé.
- **Surveillance du capteur de sol** : Indique si la surveillance des capteurs de sol est activée.

#### Boutons (actions)

- **Régénérer maintenant** : Lancer une régénération immédiate. Elle est refusée pendant qu'une régénération est en cours.
- **Réinitialiser l'alarme** : Effacer les messages d'alarme actifs.
- **Réinitialiser la notification** : Effacer les messages de notification.
- **Réinitialiser l'avertissement** : Effacer les messages d'avertissement.
- **Démarrer le test de microfuite** : Lancer le test de microfuite. La vanne reste fermée pendant environ 4 minutes, et un puisage d'eau pendant le test donne un résultat négatif (API locale uniquement).
- **Rinçage manuel (eau froide)**, **Rinçage manuel (eau chaude)** : Lancer un rinçage manuel de la conduite d'eau (module d'hygiène).

#### Interrupteurs

- **Avertisseur en cas d'alarme** : Activer ou désactiver l'avertisseur en cas d'alarme.
- **Autoriser le changement de profil sur l'appareil** : Autoriser ou bloquer le changement du profil de protection contre les fuites avec la touche de l'appareil.
- **Mode de remplissage** : Activer ou désactiver le remplissage automatique (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect et ses appareils identiques d'autres marques, All-in-One+).
- **Remplissage initial** : Démarrer ou arrêter le remplissage initial (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect et ses appareils identiques d'autres marques, All-in-One+).
- **Remplissage manuel** : Démarrer ou arrêter le remplissage manuel (All-in-One+).
- **Contre-lavage automatique** : Activer ou désactiver le contre-lavage automatique (contre-lavage automatique RSA).
- **Rappel de contre-lavage** : Activer ou désactiver le rappel de contre-lavage (contre-lavage automatique RSA).
- **Rinçage de stagnation**, **Rinçage de température**, **Rinçage périodique** : Activer ou désactiver les trois fonctions de rinçage (HygBox).

#### Listes de sélection (configuration)

- **Heure de régénération** : Régler l'heure quotidienne de la régénération (intervalles de 15 minutes).
- **Profil de protection contre les fuites actif** : Sélectionner le profil de protection contre les fuites actif (pour les appareils à plusieurs profils).
- **Quantité de sel dans le réservoir 1–3** : Régler la quantité de sel par réservoir (selon le modèle, jusqu'à 3 réservoirs).
- **Intervalle de régénération** : Régler la fréquence de la régénération (selon le modèle : jusqu'à 3, 4 ou 99 jours).
- **Orientation de l'affichage** : Régler l'orientation de l'écran (0 / 90 / 180 / 270 degrés, pour les appareils avec écran).
- **Langue de l'appareil** : Régler la langue de l'écran de l'appareil : allemand, anglais, espagnol, italien ou polonais (SafeTech).
- **Mode de régénération** : Sélectionner Standard / ECO / Power / Automatique (pour les appareils qui le prennent en charge).
- **Dureté de l'eau brute**, **Dureté de l'eau adoucie** : Régler la dureté de l'eau brute et de l'eau adoucie (famille LEX, CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect et ses appareils identiques d'autres marques, All-in-One+). L'unité suit l'unité de dureté configurée sur l'appareil (°dH, °fH, °e, mg/l CaCO₃, ppm, mmol/l ou mval/l).
- **Traitement de l'eau et remplissage** (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect et ses appareils identiques d'autres marques, All-in-One+) : Taille et type de cartouche, dureté de l'eau adoucie ou conductivité maximale en sortie (selon la cartouche), période de remplissage, nombre de cycles de remplissage, durée et quantité maximales de remplissage, pression cible, seuil d'avertissement de capacité restante, volume et durée maximaux du remplissage initial.
- **Capteur de sol** (SafeFloor) : Durée de l'alarme, seuils minimal et maximal d'humidité et de température (« Désactivé » désactive un seuil), intervalle de mesure et intervalle de synchronisation des réglages.
- **Rinçage d'hygiène** (HygBox) : Type d'eau, temps de stagnation et volume de rinçage, température de démarrage et d'arrêt, durée maximale de rinçage et rinçages par jour, intervalle et volume du rinçage périodique, intervalle de synchronisation des réglages.
- **Rinçage d'hygiène** (module d'hygiène, Safe-T Hygiene Module) : Temps de stagnation, intervalle de rinçage, limite de température, durée maximale et volume maximal de rinçage de la conduite d'eau froide et de celle d'eau chaude.
- **Dosage** (NeoDos Connect) : Taille du bidon, liquide de dosage et mode de fonctionnement.
- **Contre-lavage** (contre-lavage automatique RSA) : Intervalle de contre-lavage et intervalle de rappel de contre-lavage (1–365 jours).
- **Protection contre les fuites** (Safe-T+) : Niveau de protection contre les fuites en présence et en absence (un niveau en absence active le profil d'absence, « Désactivé » revient au profil de présence), fuite de temps et désactivation temporaire de la protection contre les fuites.

#### Commande de la vanne

- **Coupure de vanne** : Commander la vanne principale de coupure d'eau.
  - Ouvrir et fermer la vanne.
  - Surveiller la position et l'état actuels de la vanne.
  - Intégration avec des automatisations de détection de fuites pour une coupure automatique.

#### Mise à jour du micrologiciel

- **Mise à jour du micrologiciel** : Indique si un nouveau micrologiciel est disponible et l'installe. L'appareil doit être connecté à Internet. L'appareil ne communique pas le numéro de la nouvelle version.

### Modes d'API

L'intégration prend en charge deux modes d'API :

#### API cloud (basée sur XML)

- **Prise en charge par** : Tous les appareils SYR Connect
- **Connexion** : Via le service cloud SYR Connect
- **Authentification** : Nom d'utilisateur et mot de passe du compte SYR Connect
- **Avantages** : Fonctionne avec tous les modèles d'appareils, accès à distance depuis n'importe où
- **Prérequis** : Connexion Internet, compte SYR Connect

#### API locale (basée sur JSON)

- **Prise en charge par** : Les modèles récents dotés d'une API locale intégrée, par exemple NeoSoft, Trio DFR/LS, TRIO Lock, SafeTech Lock, AC 3200, RSA, Pontos Base, All-in-One+, HygBox et les variantes récentes de SafeTech, également d'autres marques. La sélection du modèle lors de la configuration liste tous les modèles pris en charge.
- **Connexion** : Directement avec l'appareil via le réseau local (port 5333).
- **Authentification** : Aucun identifiant n'est nécessaire.
- **Avantages** : Aucune dépendance à Internet, temps de réponse plus courts, pas de limites de requêtes du cloud.
- **Prérequis** : L'appareil doit se trouver sur le même réseau que Home Assistant et doit avoir une adresse IP statique ou un nom d'hôte.

Le mode d'API est choisi lors de la configuration (Cloud ou Local).

## Mise à jour des données

L'intégration interroge l'API de l'appareil à intervalles réguliers (par défaut : 60 secondes). Le processus de mise à jour dépend du mode d'API :

### Processus de mise à jour avec l'API cloud

1. **Connexion** : S'authentifie auprès de l'API cloud SYR Connect avec les identifiants.
2. **Découverte des appareils** : Récupère tous les projets et appareils associés au compte, au démarrage puis toutes les 30 minutes. Un appareil supprimé du compte est supprimé de Home Assistant avec ses entités.
3. **Mises à jour de l'état** : Pour chaque appareil, récupère l'état actuel avec toutes les valeurs des capteurs.
4. **Mises à jour des entités** : Met à jour toutes les entités de Home Assistant avec les dernières valeurs.

### Processus de mise à jour avec l'API locale

1. **Mises à jour de l'état** : Récupère directement l'état de l'appareil depuis le point d'accès local.
2. **Mises à jour des entités** : Met à jour toutes les entités de Home Assistant avec les dernières valeurs.

L'API locale est plus rapide et ne dépend pas de la connexion Internet, ce qui la rend plus fiable pour la surveillance en temps réel et les automatisations.

Si une mise à jour échoue temporairement (p. ex. délai dépassé, maintenance du cloud ou réponse incomplète), les entités conservent leurs dernières valeurs et l'erreur est écrite dans le journal. Les entités ne deviennent indisponibles que lorsque le cloud signale l'appareil comme hors ligne. Elles restent indisponibles jusqu'à ce que l'appareil envoie à nouveau un état complet.

Tant qu'aucune donnée ne peut être récupérée, l'intégration interroge moins souvent : l'intervalle double après chaque mise à jour échouée, jusqu'à 15 minutes. La première mise à jour réussie rétablit l'intervalle configuré.

Si aucune donnée ne peut être récupérée pendant plus d'une heure, la panne n'est plus considérée comme temporaire : les entités concernées deviennent indisponibles et un message s'affiche dans **Paramètres** → **Réparations**. Les deux disparaissent dès que des données sont à nouveau récupérées.

### Historique des mesures du SafeFloor

Un SafeFloor mesure régulièrement la température et l'humidité, mais n'envoie ses mesures au cloud que tous les quelques jours ; ses capteurs affichent donc une ligne plate suivie d'un saut. L'intégration récupère les mesures individuelles depuis le cloud toutes les 12 heures et les enregistre comme statistiques portant le nom des capteurs (p. ex. « Buanderie Température »). Pour voir la courbe réelle, une carte est ajoutée à un tableau de bord :

1. Ouvrir le tableau de bord et sélectionner **Modifier le tableau de bord** en haut à droite.
2. Sélectionner **Ajouter une carte**, saisir `Statistics` dans **Rechercher des cartes** et choisir **Graphique des statistiques**.
3. Sélectionner **Afficher l'éditeur de code**, remplacer le texte par l'un des extraits ci-dessous et sélectionner **Enregistrer**.
4. Sélectionner **Terminé**.

`123456789` est remplacé par le numéro de série du SafeFloor. Une carte est nécessaire par mesure.

Température :

```yaml
type: statistics-graph
title: Température
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_getcel_history
```

Humidité :

```yaml
type: statistics-graph
title: Humidité
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_gethmd_history
```

Le cloud ne conserve que les mesures des 6 derniers jours. L'intervalle de synchronisation du capteur doit rester de 6 jours ou moins, sinon des mesures sont perdues. Les statistiques sont supprimées avec l'appareil.

### Limitations connues

- **Dépendance au cloud** : L'API cloud nécessite une connexion Internet active et un service cloud opérationnel.
- **Intervalle de mise à jour** : L'API cloud permet un intervalle de mise à jour d'au moins 60 secondes, l'API locale d'au moins 10 secondes.
- **Accès en écriture limité** : Les modifications de configuration (heure de régénération, quantités de sel, intervalles) et les actions de commande (régénération, commande de la vanne) sont prises en charge, mais certains réglages avancés ne sont disponibles que dans l'application SYR Connect.
- **Prise en charge de l'API locale** : Tous les modèles ne proposent pas d'API JSON locale. LEX 1500, LEXplus, i-LEX, Safe-T, SafeFloor, HVA, les modules d'hygiène et les anciennes variantes de SafeTech nécessitent l'accès par l'API cloud.

## Cas d'usage et exemples

### Exemples d'automatisations

Les exemples utilisent la syntaxe YAML de `configuration.yaml`. Dans tous les exemples, `<serial_number>` est remplacé par le numéro de série de l'appareil et `<device_name>` par le nom de l'appareil de l'application mobile dans Home Assistant.

#### Alerte de sel bas

Notification lorsque la réserve de sel s'épuise :

```yaml
automation:
  - alias: "SYR : Alerte de sel bas"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Moins de 2 semaines de sel restantes
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Adoucisseur d'eau"
          message: "Réserve de sel basse - moins de 2 semaines restantes"
```

#### Rapport quotidien de régénération

Résumé quotidien des régénérations, de la capacité restante et de la réserve de sel :

```yaml
automation:
  - alias: "SYR : Rapport quotidien de régénération"
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Rapport quotidien de l'adoucisseur d'eau"
          message: >
            Régénérations (total) : {{ states('sensor.syr_connect_<serial_number>_getnor') }}
            Capacité restante : {{ states('sensor.syr_connect_<serial_number>_getres') }} L
            Réserve de sel : {{ states('sensor.syr_connect_<serial_number>_getss1') }} semaines
```

#### Notification d'alarme

Notification immédiate lorsque l'appareil signale une alarme :

```yaml
automation:
  - alias: "SYR : Notification d'alarme"
    triggers:
      - trigger: template
        value_template: >
          {{ states('sensor.syr_connect_<serial_number>_getala')
             not in ['no_alarm', 'unknown', 'unavailable'] }}
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "⚠️ Alarme SYR"
          message: "Alarme actuelle : {{ states('sensor.syr_connect_<serial_number>_getala') }}"
          data:
            priority: high
```

#### Surveillance du débit d'eau

Alerte en cas de débit d'eau anormalement élevé pendant plusieurs minutes (fuite possible) :

```yaml
automation:
  - alias: "SYR : Alerte de débit élevé"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 1200  # Débit supérieur à 1200 l/h (20 l/min)
        for:
          minutes: 5
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Débit d'eau élevé détecté"
          message: "Débit d'eau inhabituel - fuite possible"
```

#### Détecteur de fuite : fermer la vanne d'eau

Ferme la vanne de coupure d'eau SYR avec l'action standard `valve.close` lorsqu'un détecteur de fuite détecte de l'eau. Les ID d'entité sont remplacés par ceux utilisés dans l'installation. Cette automatisation peut devenir une action de sécurité critique et doit donc être testée très soigneusement.

```yaml
automation:
  - alias: "SYR : Fermer la vanne en cas de fuite"
    triggers:
      - trigger: state
        entity_id: binary_sensor.house_leak_sensor
        to: "on"
    actions:
      - action: valve.close
        target:
          entity_id: valve.syr_connect_<serial_number>_getab
      - action: notify.mobile_app_<device_name>
        data:
          title: "SYR : Fuite détectée - vanne fermée"
          message: "Fuite d'eau détectée - la vanne de coupure d'eau SYR a été fermée automatiquement."
```

#### Régénération le week-end

Lance une régénération le samedi et le dimanche à 03:00 :

```yaml
automation:
  - alias: "SYR : Régénération le week-end"
    triggers:
      - trigger: time
        at: "03:00:00"
    conditions:
      - condition: time
        weekday:
          - sat
          - sun
    actions:
      - action: button.press
        target:
          entity_id: button.syr_connect_<serial_number>_setsir
```

## Options de configuration

### Intervalle de mise à jour

Les données sont mises à jour toutes les 60 secondes par défaut. L'intervalle se règle dans les options de l'intégration : au moins 60 secondes pour le cloud, au moins 10 secondes pour les appareils locaux et au plus 600 secondes dans les deux cas.

1. Ouvrir Paramètres > Appareils et services.
2. Ouvrir l'intégration SYR Connect.
3. Sélectionner « Configurer ».
4. Ajuster l'intervalle de mise à jour (en secondes).

## Suppression

Pour supprimer l'intégration de Home Assistant :

1. Aller dans Paramètres > Appareils et services.
2. Rechercher l'intégration SYR Connect.
3. Cliquer sur le menu à trois points (⋮).
4. Sélectionner « Supprimer ».
5. Confirmer la suppression.

Tous les appareils et entités associés sont supprimés automatiquement.

## Dépannage

### Télécharger les diagnostics

En cas de problème, les diagnostics de l'entrée de l'intégration sont utiles. Ils contiennent les données de tous les appareils de l'entrée :

1. Ouvrir Paramètres > Appareils et services.
2. Ouvrir l'intégration SYR Connect.
3. Ouvrir le menu à trois points (⋮) de l'entrée (compte ou appareil local).
4. Sélectionner « Télécharger les diagnostics ».

Les mots de passe, les noms d'utilisateur, les données de session, le numéro de code de l'appareil, les adresses IP, les passerelles et le nom du réseau Wi-Fi sont supprimés du fichier, et le numéro de série est masqué.

### Journaux de débogage

L'activation et la désactivation de la journalisation de débogage sont décrites dans [docs/howto-debugging.md](docs/howto-debugging.md) (en anglais).

### La connexion échoue

- **Vérifier les identifiants** : Contrôler le nom d'utilisateur et le mot de passe de l'application SYR Connect.
- **Tester l'application** : La connexion à l'application mobile SYR Connect doit fonctionner avec le même compte.
- **Consulter les journaux** : Aller dans Paramètres > Système > Journaux et rechercher les erreurs « syr_connect ».
- **Problèmes de réseau** : Home Assistant doit avoir accès à Internet.

### Erreurs d'authentification

En cas d'erreur « Authentication failed » :

1. Vérifier les identifiants.
2. L'intégration demande une nouvelle authentification.
3. Aller dans Paramètres > Appareils et services.
4. Cliquer sur « S'authentifier » sur l'intégration SYR Connect.
5. Saisir à nouveau les identifiants.

La nouvelle authentification et « Reconfigurer » ne modifient que le mot de passe du compte. Un autre nom d'utilisateur correspond à un autre compte : il y est refusé et doit être ajouté comme nouvelle entrée.

### Aucun appareil trouvé

- **Configuration de l'application** : Les appareils doivent être correctement configurés dans l'application SYR Connect.
- **Accès au compte** : Le compte doit être celui dans lequel les appareils sont configurés.
- **État des appareils** : Vérifier si les appareils sont en ligne dans l'application SYR Connect.
- **Journaux** : Consulter les journaux de Home Assistant pour trouver des messages d'erreur précis.

### Les entités apparaissent comme indisponibles

- **Appareil hors ligne** : Le cloud signale l'appareil comme hors ligne. L'alimentation électrique et la connexion réseau de l'appareil doivent être vérifiées.
- **Application SYR Connect** : L'appareil doit apparaître en ligne dans l'application SYR Connect.
- **De nouveau en ligne** : Les entités redeviennent disponibles dès que l'appareil envoie un état complet.

- **Pas de connexion depuis plus d'une heure** : Aucune donnée n'a pu être récupérée depuis le cloud ou l'appareil pendant plus d'une heure. Un message s'affiche dans **Paramètres** → **Réparations**. La connexion Internet et l'état du cloud SYR Connect doivent être vérifiés.
- **Problème de réseau** : Si le nom d'hôte n'a pas pu être résolu ou si aucune connexion n'a pu être ouverte, le message indique le réseau comme cause. La connexion réseau et les paramètres DNS de Home Assistant doivent être vérifiés, et pour un appareil local également son adresse IP.

Les problèmes temporaires de connexion ou du service cloud ne rendent pas les entités indisponibles. Les entités conservent leurs dernières valeurs et l'erreur est écrite dans le journal.

### Utilisation élevée du processeur ou de la mémoire

- **Augmenter l'intervalle de mise à jour** : Définir une valeur plus élevée (p. ex. 120–300 secondes) dans les options de l'intégration.
- Cela réduit les appels à l'API et la charge du système.

<!-- ha-marketplace:exclude-start -->

## Dépendances

L'intégration nécessite les paquets Python suivants :

- `pycryptodomex>=3.19.0,<4.0` : Pour le chiffrement et le déchiffrement AES
- `defusedxml>=0.7.1,<1.0` : Pour l'analyse sécurisée du XML (empêche les attaques XXE)

**Remarque** : L'intégration utilise `defusedxml` pour l'analyse sécurisée du XML et `pycryptodomex` (et non `pycryptodome`) afin d'éviter les conflits avec les bibliothèques cryptographiques intégrées à Home Assistant.

Home Assistant installe les paquets **automatiquement** lorsque :

1. L'intégration est ajoutée via l'interface utilisateur.
2. Home Assistant est redémarré après l'installation.

Les exigences système détaillées et le dépannage se trouvent dans [REQUIREMENTS.md](REQUIREMENTS.md) (en anglais).

<!-- ha-marketplace:exclude-end -->

## Avertissement

### IMPORTANT : À lire avant d'utiliser l'intégration

Cette intégration commande des systèmes de traitement de l'eau et de coupure d'eau. Une configuration incorrecte ou des automatisations défaillantes peuvent entraîner des dégâts des eaux, des pannes du système ou des dommages matériels.

- **Utilisation à ses propres risques** : Ce logiciel est fourni « tel quel », sans garantie d'aucune sorte.
- **Tests approfondis** : Les automatisations doivent toujours être testées dans des conditions sûres avant leur mise en service.
- **Systèmes critiques** : Les automatisations de commande de la vanne peuvent couper toute l'alimentation en eau et doivent être testées avec soin.
- **Aucune responsabilité** : Les auteurs et contributeurs ne sont pas responsables des dommages, dégâts des eaux, dommages matériels ou autres problèmes résultant de l'utilisation de cette intégration.
- **Dépendance au cloud** : Cette intégration repose sur le service cloud SYR Connect, dont la disponibilité n'est pas garantie.
- **Solution de secours** : Un accès alternatif à la vanne de coupure d'eau doit exister en cas de panne du système.

L'installation et l'utilisation de cette intégration impliquent la reconnaissance de ces risques et l'engagement de l'utiliser de manière responsable.

## Licence

Apache License 2.0, voir [LICENSE](LICENSE)

## Remerciements

- Inspiré de l'adaptateur [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) de TA2k.
- Un grand merci à l'équipe SYR IoT-Development-Team pour le partage des logos.
