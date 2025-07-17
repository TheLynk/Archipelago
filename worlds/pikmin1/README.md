# Pikmin 1 GameCube PAL APWorld

Un prototype simple d'APWorld pour Pikmin 1 GameCube PAL compatible avec Archipelago.

## Fonctionnalités

- Détection automatique du nombre de pikmin rouge via l'adresse mémoire `0x803D6CF7`
- Déclenchement de la location "10 Red Pikmin" quand le joueur a 10 pikmin rouge ou plus
- Connexion au serveur Archipelago
- Interface client simple

## Installation

1. Placez le dossier `pikmin` dans le répertoire `worlds` de votre installation Archipelago
2. Installez les dépendances :
   ```bash
   pip install psutil
   ```

## Structure du projet

```
pikmin/
├── __init__.py          # Classe principale PikminWorld
├── Items.py             # Définition des items
├── Locations.py         # Définition des locations
├── Regions.py          # Définition des régions
├── Rules.py            # Règles de logique
├── PikminClient.py     # Client pour connexion au jeu
├── setup.py            # Configuration du package
└── README.md           # Ce fichier
```

## Utilisation

### Génération d'un monde

1. Créez un fichier YAML avec les paramètres suivants :
   ```yaml
   name: VotreNom
   game: Pikmin
   ```

2. Générez le multiworld avec l'interface Archipelago habituelle

### Connexion au jeu

1. Lancez Pikmin 1 GameCube PAL dans Dolphin
2. Démarrez le client :
   ```bash
   python PikminClient.py
   ```
3. Connectez-vous au serveur Archipelago

### Test de fonctionnement

1. Dans le jeu, collectez des pikmin rouge
2. Quand vous atteignez 10 pikmin rouge, la location "10 Red Pikmin" sera automatiquement déclenchée
3. Vérifiez dans l'interface Archipelago que la location a été marquée comme complète

## Adresse mémoire

- **Pikmin Rouge** : `0x803D6CF7` (GameCube PAL)
- Cette adresse contient le nombre actuel de pikmin rouge que possède le joueur

## Développement

### Ajouter de nouvelles locations

1. Modifiez `Locations.py` pour ajouter de nouvelles locations
2. Ajoutez les conditions de déclenchement dans `PikminClient.py`
3. Mettez à jour les règles dans `Rules.py` si nécessaire

### Ajouter de nouveaux items

1. Modifiez `Items.py` pour définir les nouveaux items
2. Ajoutez la logique correspondante dans `__init__.py`

### Adresses mémoire additionnelles

Pour ajouter d'autres adresses mémoire :
1. Ajoutez les adresses dans `PikminClient.py`
2. Implémentez la lecture mémoire correspondante
3. Ajoutez les conditions de déclenchement dans `check_locations()`

## Limitations actuelles

- Seule la location "10 Red Pikmin" est fonctionnelle
- La lecture mémoire Dolphin est simulée (nécessite implémentation réelle)
- Pas de gestion des items envoyés vers le jeu
- Interface utilisateur basique

## Améliorations futures

- Implémentation complète de la lecture mémoire Dolphin
- Ajout de plus de locations basées sur la progression
- Gestion des items reçus d'autres joueurs
- Interface utilisateur améliorée
- Support des versions NTSC

## Contribuer

1. Forkez le projet
2. Créez une branche pour vos modifications
3.