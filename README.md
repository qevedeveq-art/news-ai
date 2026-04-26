# AI.Watch — Veille Nouveautés IA

Application PWA (Progressive Web App) de veille sur les dernières nouveautés de **Claude**, **ChatGPT** et **Gemini Pro**.

Le dépôt contient aussi une automatisation GitHub Actions pour publier une newsletter quotidienne dans Slack.

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
- Script Python standard library pour l'envoi Slack
- GitHub Actions pour l'automatisation quotidienne

## Automatisation Slack

Le workflow [`.github/workflows/newsletter-slack.yml`](.github/workflows/newsletter-slack.yml) exécute chaque jour `scripts/send_newsletter.py`, récupère les flux RSS officiels d'OpenAI, Anthropic et Google, construit un message Slack, puis l'envoie via un webhook entrant.

### Configuration

1. Créer un *Slack Incoming Webhook* pour le canal cible.
2. Ajouter ce webhook dans les secrets GitHub du repo, sous le nom `SLACK_WEBHOOK_URL`.
3. Vérifier que GitHub Actions est activé sur le dépôt.
4. Lancer une première exécution via `Actions > Send AI Newsletter To Slack > Run workflow`.

### Déclenchement

- Horaire automatique : tous les jours à `07:00 UTC`.
- Déclenchement manuel : `workflow_dispatch`.

### Test local

```bash
python3 scripts/send_newsletter.py --dry-run --stdout
```
