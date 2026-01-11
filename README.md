# 🔐 Security Logs Platform

Plateforme web de **collecte, recherche et visualisation de logs de sécurité**, basée sur **Flask** et la stack **Elastic (Elasticsearch + Kibana)**, avec **MongoDB**, **Redis** et une orchestration via **Docker Compose**.

Ce projet a été réalisé dans un **contexte académique** afin de mettre en pratique les concepts de **centralisation des logs, supervision, détection d’incidents de sécurité et visualisation de données**.

---

## 🎯 1. Contexte et objectifs

Les systèmes d’information génèrent quotidiennement un grand volume de journaux (logs) liés à la sécurité : connexions, échecs d’authentification, accès refusés, etc.

L’objectif de ce projet est de proposer une solution simple et modulaire permettant de :

* Centraliser des logs de sécurité au format CSV
* Indexer et rechercher ces logs efficacement
* Visualiser les événements de sécurité via des dashboards interactifs
* Détecter automatiquement des comportements suspects (ex. attaques par force brute)

---

## 🏗️ 2. Architecture globale

L’architecture de la plateforme repose sur les composants suivants :

### 🔹 Application Web (Flask)

* Backend + Frontend
* Authentification avec gestion des rôles : `admin`, `analyst`
* Fonctionnalités principales :

  * Connexion utilisateur
  * Upload de fichiers de logs
  * Recherche et consultation des logs
  * Affichage d’alertes et de statistiques

### 🔹 Elasticsearch

* Indexation des événements de logs dans des index de type :

  * `security-logs-YYYY-MM-DD`
* Moteur principal pour la recherche et les agrégations

### 🔹 Kibana

* Visualisation des logs via des dashboards
* Intégration dans l’application Flask via des iframes (`embed=true`)

### 🔹 MongoDB

* Base NoSQL pour le stockage applicatif
* Collections principales :

  * `uploads` : historique des fichiers importés
  * `alerts` : alertes de sécurité générées

### 🔹 Redis

* Cache et compteur
* Stockage du nombre total d’uploads (`uploads:count`)
* Vérification de disponibilité dans le healthcheck

### 🔹 Docker Compose

* Orchestration de tous les services
* Volumes persistants pour :

  * Elasticsearch
  * MongoDB
  * Fichiers de logs
* Healthchecks pour la supervision

---

## 📄 3. Format des données de logs

Les logs traités par la plateforme sont fournis au format **CSV** avec la structure suivante :

```text
timestamp,level,action,username,ip,country,resource,user_agent,message
2025-12-18T10:00:00Z,INFO,LOGIN_SUCCESS,alice,192.168.1.10,FR,/login,Mozilla/5.0,User logged in successfully
```

### 🔁 Traitement lors de l’upload

Lorsqu’un fichier est importé :

* Le fichier CSV est sauvegardé dans le volume `/logs`
* Le fichier est lu ligne par ligne via `csv.DictReader`
* Chaque ligne est transformée en document JSON
* Les documents sont indexés dans Elasticsearch avec les champs suivants :

  * `@timestamp` (date normalisée)
  * `level`, `action`, `username`, `ip`, `country`, `resource`, `user_agent`, `message`
* Une entrée est ajoutée dans MongoDB (`uploads`)
* Le compteur Redis `uploads:count` est incrémenté

---

## ⚙️ 4. Fonctionnalités de l’application

### 🔐 4.1 Authentification et rôles

* Page de connexion : `/login`
* Comptes de démonstration :

  * `admin / admin123`
  * `analyst / analyst123`
* Protection des routes avec des décorateurs Flask :

  * `login_required`
  * `role_required("admin")`


---

### 📤 4.2 Upload et historique

#### Page Upload

* Sélection et import d’un fichier CSV
* Vérification basique (extension, taille)
* Message de confirmation en cas de succès

#### Historique des uploads

* Données issues de MongoDB (`uploads`)
* Informations affichées : nom du fichier, taille, date d’upload, source

#### Page Fichiers

* Liste des fichiers présents physiquement dans le dossier `/logs`

---

### 🔎 4.3 Recherche de logs

* Recherche multi‑champs : `username`, `ip`, `country`, `action`, `message`
* Filtres disponibles :

  * Type d’action (LOGIN_FAILED, ACCESS_DENIED, etc.)
  * Intervalle de temps basé sur `@timestamp`

Les résultats sont affichés sous forme de tableau avec :

* Date
* Niveau
* Action
* Utilisateur
* IP
* Pays
* Message

---

### 📊 4.4 Dashboards Kibana

* Intégration d’un dashboard Kibana existant : **Security Logs Dashboard**
* Affichage via iframe en mode `embed=true`

Exemples de visualisations :

* Nombre d’événements par période
* Top IP sources
* Répartition par niveau de log
* Top utilisateurs et pays

---

### 🚨 4.5 Génération d’alertes

#### Route `/alerts/run` (admin uniquement)

* Recherche des événements `LOGIN_FAILED` sur une période donnée
* Agrégation par adresse IP
* Déclenchement d’une alerte si un seuil est dépassé

Type d’alerte générée :

* `BRUTE_FORCE_SUSPECT`

Stockage de l’alerte dans :

* Elasticsearch (`security-alerts`)
* MongoDB (`alerts`)

#### Page Alertes

* Liste des alertes enregistrées avec :

  * Type
  * IP
  * Nombre d’échecs
  * Fenêtre temporelle
  * Date de création
  * Statut

---

## 🩺 5. Healthcheck et supervision

### Endpoint `/health`

* Vérifie l’état de :

  * Flask
  * Elasticsearch
  * MongoDB
  * Redis

* Réponse :

  * `200 OK` si tous les services sont disponibles
  * `500 ERROR` sinon

### Docker Compose

* Healthcheck de la webapp basé sur `/health`
* Healthcheck Elasticsearch basé sur `_cluster/health`

---

## 🚀 6. Mise en place et exécution

### Prérequis

* Git
* Docker
* Docker Compose

### Installation

```bash
git clone https://github.com/<ton-user>/security-logs-platform.git
cd security-logs-platform
```

### Démarrage

```bash
docker compose up -d
```

### Accès aux services

* Application Flask : [http://localhost:8000](http://localhost:8000)
* Kibana : [http://localhost:5601](http://localhost:5601)

### Arrêt des services

```bash
docker compose down
```

---

## 🧠 7. Limites et perspectives

* Authentification simplifiée (comptes en mémoire)
* Détection basée sur des règles statiques

Améliorations possibles :

* Gestion des utilisateurs en base de données
* Alertes temps réel
* Détection avancée par machine learning
* Règles de sécurité configurables via interface

---

## 🛠️ Technologies utilisées

* Python / Flask
* Elasticsearch
* Kibana
* MongoDB
* Redis
* Docker & Docker Compose

---

