text
# Security Logs Platform

Plateforme web de visualisation et d’analyse de logs de sécurité, basée sur Flask, MongoDB, Elasticsearch, Redis et Kibana.  
Elle permet d’uploader des fichiers CSV de logs, de les rechercher via une interface web et de les visualiser dans un dashboard Kibana intégré.

---

## 1. Architecture

- **Flask** : application web (upload, recherche, authentification, pages HTML).
- **MongoDB** : stockage des métadonnées d’upload et des alertes.
- **Elasticsearch** : indexation et recherche des événements de logs.
- **Kibana** : dashboards et visualisations des logs.
- **Redis** : compteur d’uploads et healthcheck.
- **Docker Compose** : orchestration de tous les services.

---

## 2. Prérequis

- Git
- Docker et Docker Compose installés
- Accès internet pour télécharger les images Docker

---

## 3. Installation et lancement

Cloner le dépôt :

```bash
git clone https://github.com/<ton-user>/security-logs-platform.git
cd security-logs-platform
Lancer la stack Docker :

bash
docker compose up -d
Les principaux services :

Application Flask : http://localhost:8000

Kibana : http://localhost:5601

Elasticsearch : http://localhost:9200

Pour arrêter :

bash
docker compose down
4. Utilisation de la plateforme
4.1 Connexion
Ouvrir http://localhost:8000.

Se connecter avec un compte de démo :

admin / admin123 (rôle administrateur)

analyst / analyst123 (rôle analyste)

4.2 Upload de logs
Menu Upload.

Sélectionner un fichier CSV respectant le format :

text
timestamp,level,action,username,ip,country,resource,user_agent,message
2025-12-18T10:00:00Z,INFO,LOGIN_SUCCESS,alice,192.168.1.10,FR,/login,Mozilla/5.0,User logged in successfully
...
Le fichier est :

Sauvegardé dans le volume /logs.

Enregistré dans MongoDB (collection uploads).

Indexé dans Elasticsearch (index security-logs-YYYY-MM-DD).

4.3 Recherche de logs
Menu Recherche.

Champs disponibles :

Texte libre : IP, username, message...

Filtre par action (LOGIN_FAILED, ACCESS_DENIED, etc.).

Filtre temporel (date de début / fin).

La page affiche les événements trouvés (timestamp, niveau, action, utilisateur, IP, pays, message).

4.4 Dashboards Kibana
Menu Stats (iframe Kibana embarquée).

Visualisations possibles :

Volume d’événements dans le temps.

Top IP sources.

Top utilisateurs et pays.

Répartition par niveau (INFO / WARNING / ERROR).

L’URL utilise le mode embed=true pour masquer la barre d’édition Kibana et n’afficher que les dashboards.

5. Système d’alertes
Menu Alertes pour consulter les alertes stockées.

Route /alerts/run (réservée au rôle admin) :

Analyse les événements LOGIN_FAILED dans Elasticsearch.

Agrège par IP sur une fenêtre de temps.

Crée une alerte de type BRUTE_FORCE_SUSPECT si une IP dépasse un certain nombre d’échecs.

Sauvegarde l’alerte dans Elasticsearch (security-alerts) et MongoDB (alerts).

6. Healthcheck et supervision
Endpoint /health exposé par Flask :

Vérifie l’état de l’application web, d’Elasticsearch, de MongoDB et de Redis.

Retourne 200 OK si tous les services sont disponibles, sinon 500.

Docker Compose utilise cet endpoint dans un healthcheck pour marquer le conteneur webapp comme sain ou non.

7. Variables et configuration
Les mots de passe et paramètres de connexion peuvent être externalisés dans un fichier .env et référencés dans docker-compose.yml.

Exemple de variables possibles :

MONGO_INITDB_ROOT_USERNAME, MONGO_INITDB_ROOT_PASSWORD

ELASTIC_USERNAME, ELASTIC_PASSWORD

FLASK_SECRET_KEY

8. Limites et pistes d’amélioration
Authentification simple (comptes en mémoire, pas de base utilisateurs).

Pas encore de rôles/permissions avancés sur les dashboards Kibana.

Possibles évolutions :

Ajout de nouveaux types d’alertes (exfiltration de données, anomalies par pays).

Mise en place d’une vraie gestion des utilisateurs.

Ajout de tests automatisés et pipeline CI/CD.
