# AI.Watch — Veille Nouveautés IA

Application PWA (Progressive Web App) de veille sur les dernières nouveautés de **Claude**, **ChatGPT** et **Gemini Pro**.

## Fonctionnalités

- Recherche des dernières nouveautés via l'API Claude + Web Search
- Navigation par onglets : Tous / Claude / ChatGPT / Gemini / Liens
- Installable sur Android (écran d'accueil, mode plein écran)
- Clef API stockée localement sur l'appareil
- Fonctionne hors-ligne (Service Worker)

## Déploiement

Hébergé via **GitHub Pages** : [https://qevedeveq-art.github.io/news-ai](https://qevedeveq-art.github.io/news-ai)

## Usage

1. Ouvrir l'URL sur Chrome Android
2. Saisir sa clef API Anthropic (`sk-ant-api03-…`)
3. Appuyer sur **ACTUALISER**
4. Installer via "Ajouter à l'écran d'accueil"

## Stack

- HTML/CSS/JS vanilla (zéro dépendance)
- API Anthropic `claude-sonnet-4-6` + web_search tool
- PWA : Manifest + Service Worker
