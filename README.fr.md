![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)

# SYR Connect - Intégration Home Assistant

![Syr](custom_components/syr_connect/logo.png)

Cette integration personnalisée permet de piloter les appareils SYR Connect depuis Home Assistant.

## Installation

### HACS (recommandé)

1. Ouvrez HACS dans Home Assistant
2. Allez dans "Integrations"
3. Cliquez sur les trois points en haut à droite
4. Sélectionnez "Custom repositories"
5. Ajoutez l'URL du dépôt
6. Sélectionnez la catégorie "Integration"
7. Cliquez sur "Add"
8. Recherchez "SYR Connect" et installez-le
9. Redémarrez Home Assistant

### Installation manuelle

1. Copiez le dossier `syr_connect` dans votre répertoire `custom_components`
2. Redémarrez Home Assistant

## Configuration

1. Allez dans Paramètres > Appareils et services
2. Cliquez sur "+ Ajouter une intégration"
3. Recherchez "SYR Connect"
4. Entrez vos identifiants SYR Connect App :
   - Nom d'utilisateur
   - Mot de passe

## Fonctionnalités

L'intégration crée automatiquement des entités pour tous vos appareils SYR Connect.

### Appareils supportés

Fonctionne avec les adoucisseurs d'eau SYR présents dans le portail SYR Connect.

Testé et reporté fonctionnel :
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

Non testé, mais devrait fonctionner :
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect
- SYR LEX 1500 Connect Simple
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Alternant
- SYR LEX 1500 Connect Triple
- SYR IT 3000 Système pendulaire
- Autres modèles SYR avec Connect ou gateway retrofit

**Remarque** : Si l'appareil est visible sur votre compte SYR Connect, l'intégration le découvrira automatiquement et créera les entités. Pour les appareils non testés, partager les diagnostics aide à compléter la prise en charge.

### Fonctionnalités prises en charge

#### Capteurs
- Surveillance de la dureté de l'eau (entrée/sortie)
- Capacité restante
- Capacité totale
- Unité de dureté
- Statut de régénération (actif/inactif)
- Nombre de régénérations
- Intervalle et horaire de régénération
- Gestion du sel (volume, stock)
- Surveillance de la pression et du débit
- État de fonctionnement et alarmes

#### Capteurs binaires
- Régénération active
- État opérationnel
- Alarmes

#### Boutons (Actions)
- Régénérer maintenant (`setSIR`)
- Régénération multiple (`setSMR`)
- Réinitialiser l'appareil (`setRST`)

### Limitations connues

- Dépendance cloud : nécessite une connexion Internet et le service SYR Connect
- Intervalle de mise à jour minimum recommandé : 60s
- Majoritairement en lecture seule : seules les actions de régénération sont possibles
- Un seul compte SYR Connect par instance Home Assistant
- Pas d'API locale : communication via le cloud

## Mise à jour des données

L'intégration interroge l'API SYR Connect à intervalles réguliers (par défaut 60s) :

1. Authentification
2. Découverte des appareils
3. Récupération des statuts
4. Mise à jour des entités Home Assistant

En cas d'appareil hors ligne, les entités deviennent `unavailable` jusqu'au prochain update réussi.

## Exemples d'utilisation
- Automatisations : alerte sel bas, rapport quotidien régénération, notification d'alarme, surveillance du débit, régénération planifiée (voir le README original pour exemples)

## Options de configuration

L'intervalle de scan peut être ajusté dans les options de l'intégration (par défaut 60s).

## Suppression

1. Paramètres > Appareils et services
2. Sélectionnez SYR Connect
3. Menu (⋮) > Supprimer

## Dépannage

- Téléchargement des diagnostics disponible (données sensibles masquées)
- Erreurs de connexion/authentification : vérifiez les identifiants, testez l'app, consultez les logs

## Dépendances

- `pycryptodomex==3.19.0`

## Licence

Licence MIT - voir le fichier LICENSE

## Remerciements

- Basé sur l'adaptateur [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) par TA2k.
- Merci à l'équipe SYR IoT pour les logos.
