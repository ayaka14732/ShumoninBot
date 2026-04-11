# Shumonin Bot

[[中文說明]](README-zh.md)

Un bot Telegram anti-spam pour groupes, propulsé par l’IA. Lorsqu’un nouveau membre rejoint, le bot engage un dialogue en plusieurs tours afin de vérifier son admissibilité. L’IA décide s’il remplit les critères d’entrée ; dans le cas contraire, il est automatiquement expulsé ou banni. Les membres du groupe peuvent également signaler des messages suspects ; l’IA détermine s’il s’agit de spam et agit en conséquence.

## Fonctionnalités

**Vérification à l’entrée**

Lorsqu’un nouveau membre rejoint, le bot pose des questions dans le groupe auxquelles il doit répondre publiquement. L’IA analyse l’historique de la conversation et peut relancer si nécessaire, jusqu’à rendre une décision finale : acceptation ou rejet. En cas d’échec ou de dépassement du délai, le membre est expulsé. Après plusieurs échecs cumulés, il est définitivement banni.

Le bot permet aux administrateurs de définir les critères d’évaluation en langage naturel, par exemple en exigeant des réponses substantielles et correctes à certaines questions, tout en refusant les réponses vagues ou évasives.

**Filtrage des noms**

À l’arrivée d’un nouveau membre, le bot examine son nom d’affichage et son identifiant. Les noms comportant des éléments manifestement liés à la publicité, au contenu pornographique ou à l’escroquerie entraînent une expulsion immédiate, avant même le début de la vérification.

**Signalement de spam**

Les membres peuvent répondre à un message et envoyer `/report`. Le bot transmet alors ce message à l’IA pour évaluation. Si le contenu est confirmé comme spam, le message est supprimé et son auteur est banni. Si le message est jugé normal, il est ignoré sans notification. Dans tous les cas, le bot reste silencieux afin de ne pas perturber le groupe. Les signalements visant des messages d’administrateurs sont supprimés automatiquement.

**Mécanismes anti-abus**

* Si un membre en cours de vérification envoie une réponse de plus de 50 caractères, il est immédiatement expulsé
* Toute tentative de manipulation de l’IA (demande d’ignorer les instructions, jeu de rôle, écriture de code, etc.) entraîne une expulsion immédiate
* Le dépassement du délai de vérification (2 minutes par défaut) est considéré comme un échec

## Préparation

### 1. Créer le bot

Rendez-vous sur Telegram via [@BotFather](https://t.me/BotFather), envoyez `/newbot` et suivez les instructions pour créer votre bot. Vous obtiendrez un Bot Token.

### 2. Désactiver le Privacy Mode

Le bot doit pouvoir lire tous les messages du groupe pour fonctionner correctement. Par défaut, les bots Telegram ne peuvent lire que les commandes commençant par `/`. Cette restriction doit être désactivée :

1. Envoyer `/mybots` à BotFather
2. Sélectionner votre bot
3. Aller dans **Bot Settings → Group Privacy → Turn off**

Sans cette étape, le bot ne pourra pas lire les réponses des membres.

### 3. Ajouter le bot au groupe avec les droits d’administrateur

Le bot nécessite les permissions suivantes :

* Restreindre des membres
* Expulser des membres
* Bannir des membres
* Supprimer des messages

## Configuration et lancement

Créer un fichier `.env` à la racine du projet :

```env
TELEGRAM_BOT_TOKEN=VotreBotToken
OPENAI_API_KEY=VotreCléOpenAI
OPENROUTER_API_KEY=VotreCléOpenRouter  # Optionnel, fournisseur de secours
ALLOWED_CHAT_IDS=-100123456789,-100987654321
DB_PATH=bot.db
```

`ALLOWED_CHAT_IDS` contient les identifiants des groupes autorisés, séparés par des virgules. Le bot ne répond qu’aux groupes figurant dans cette liste blanche.

Pour obtenir l’identifiant d’un groupe, ajoutez [@userinfobot](https://t.me/userinfobot) au groupe ; il vous fournira l’ID (généralement commençant par `-100`).

Installation et lancement :

```bash
pip install -r requirements.txt
python main.py
```

## Configuration administrateur

Le bot se configure via des commandes dans le groupe, réservées aux administrateurs.

### Configuration initiale

Envoyer `/setup`. Le bot vous guide à travers les étapes suivantes :

1. **Question de vérification** — Question posée aux nouveaux membres. Exemple :

   ```
   Qu’est-ce que RIME et pourquoi souhaitez-vous rejoindre ce groupe ?
   ```

2. **Critères d’évaluation** — Instructions en langage naturel pour guider l’IA. Exemple :

   ```
   Pour la question « Qu’est-ce que RIME », la réponse doit inclure des notions telles que « méthode de saisie », « moteur de saisie », « framework », « IME » ou « clavier ».

   Une explication détaillée n’est pas nécessaire.

   Les réponses évidentes ou vides comme « RIME est RIME » sont refusées.
   Les réponses vantant une ancienneté (« je l’utilise depuis longtemps ») ou esquivant la question (« je peux apprendre ») sont également refusées.

   Une relance est autorisée ; en cas de second échec, expulsion.

   La question « pourquoi rejoindre » est plus souple : une réponse raisonnable suffit.
   ```

3. **Délai** — Temps imparti pour répondre, en minutes (2 minutes par défaut).

Une fois confirmé, le bot commence immédiatement la vérification des nouveaux membres.

### Modifier les paramètres

Chaque élément peut être modifié individuellement :

* `/setquestion` — Modifier la question
* `/setexpected` — Modifier les critères
* `/settimeout` — Modifier le délai

### Autres commandes

| Commande           | Description                                    |
| ------------------ | ---------------------------------------------- |
| `/settings`        | Afficher la configuration actuelle             |
| `/unban <user_id>` | Réinitialiser le statut d’un utilisateur banni |
| `/status`          | Vérifier les permissions du bot                |
| `/cancel`          | Annuler une configuration en cours             |
| `/help`            | Afficher l’aide                                |

### À propos de `/unban`

Débannir un utilisateur via Telegram ne réinitialise pas les enregistrements internes du bot. Il faut également utiliser `/unban <user_id>` pour remettre à zéro son nombre d’échecs, sans quoi il sera immédiatement banni à nouveau en rejoignant le groupe.

## Description du processus de vérification (pour les administrateurs)

1. Un nouveau membre rejoint ; le bot restreint immédiatement ses permissions
2. Le bot vérifie son nom ; en cas d’anomalie, il est expulsé
3. Sinon, une question de vérification est posée dans le groupe avec mention du membre
4. Le membre répond publiquement ; chaque réponse est analysée par l’IA
5. L’IA peut demander une relance (`continue`), valider (`pass`) ou expulser (`kick`)
6. En cas de validation, les restrictions sont levées ; sinon, expulsion et enregistrement d’un échec
7. Après 3 échecs cumulés, bannissement permanent

Le processus est entièrement visible par les autres membres, ce qui oblige les nouveaux arrivants à démontrer leur compréhension du sujet du groupe en public.
