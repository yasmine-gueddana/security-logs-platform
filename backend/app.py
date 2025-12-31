from elasticsearch import Elasticsearch
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from pymongo import MongoClient
from datetime import datetime
import redis
import csv
from io import StringIO

# --- Configuration Elasticsearch ---
es = Elasticsearch("http://elasticsearch:9200")
# on indexe maintenant dans un index logique sans wildcard
LOGS_INDEX = "security-logs"
INDEX_NAME = LOGS_INDEX + "-*"

# --- Configuration MongoDB ---
mongo_client = MongoClient("mongodb://mongodb:27017/")
db = mongo_client["security_logs"]
uploads_collection = db["uploads"]
alerts_collection = db["alerts"]

# --- Configuration Redis ---
redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

# --- Configuration Flask ---
UPLOAD_FOLDER = "/logs"  # volume partagé avec l'hôte

app = Flask(__name__)
app.secret_key = "change-me"  # à changer plus tard
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

# --- Utilisateurs de démo ---
USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin"
    },
    "analyst": {
        "password": "analyst123",
        "role": "analyst"
    }
}

# --------- Fonction utilitaire : indexer un CSV dans Elasticsearch ---------
def index_csv_to_elasticsearch(file_storage):
    """
    Parse un fichier CSV de logs et indexe chaque ligne comme document ES.
    Colonnes attendues :
    timestamp,level,action,username,ip,country,resource,user_agent,message
    """
    raw = file_storage.stream.read()
    # raw peut être bytes (upload direct) ou str (StringIO) [web:351]
    if isinstance(raw, bytes):
        content = raw.decode("utf-8")
    else:
        content = raw

    reader = csv.DictReader(StringIO(content))

    actions = []
    for row in reader:
        # si une ligne est vide / incomplète, on l'ignore
        if not row.get("timestamp"):
            continue

        # parser le timestamp ISO 8601 -> @timestamp
        # ex: 2025-12-18T10:00:00Z
        ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))

        doc = {
            "@timestamp": ts.isoformat(),
            "timestamp": row.get("timestamp"),
            "level": row.get("level"),
            "action": row.get("action"),
            "username": row.get("username"),
            "ip": row.get("ip"),
            "country": row.get("country"),
            "resource": row.get("resource"),
            "user_agent": row.get("user_agent"),
            "message": row.get("message"),
        }

        # action bulk : index dans un index daté (optionnel)
        index_name = f"{LOGS_INDEX}-{ts.date().isoformat()}"
        actions.append({"index": {"_index": index_name}})
        actions.append(doc)

    if actions:
        es.bulk(body=actions)  # bulk indexing [web:351]


# --- Décorateurs d'authentification/autorisation ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Veuillez vous connecter.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                flash("Veuillez vous connecter.")
                return redirect(url_for("login"))
            if session.get("role") != required_role:
                flash("Accès refusé (rôle insuffisant).")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/")
@login_required
def index():
    # Page d'accueil avec iframe Kibana
    return render_template("index.html")


# --- Upload de fichiers de logs ---
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("Aucun fichier reçu")
            return redirect(request.url)

        f = request.files["file"]
        if f.filename == "":
            flash("Aucun fichier sélectionné")
            return redirect(request.url)

        filename = f.filename
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        f.save(save_path)

        # Sauvegarde de la métadonnée d'upload dans MongoDB
        uploads_collection.insert_one({
            "filename": filename,
            "path": save_path,
            "size": os.path.getsize(save_path),
            "uploaded_at": datetime.utcnow(),
            "source": "webapp"
        })

        # Réouvrir le fichier pour l'indexer dans ES (on utilise une nouvelle FileStorage)
        with open(save_path, "r", encoding="utf-8") as fh:
            from werkzeug.datastructures import FileStorage
            fake_storage = FileStorage(stream=StringIO(fh.read()), filename=filename)
            index_csv_to_elasticsearch(fake_storage)

        # Incrémenter un compteur global dans Redis
        try:
            redis_client.incr("uploads:count")
        except Exception:
            # On ignore les erreurs Redis pour ne pas casser l'upload
            pass

        flash(f"Fichier {filename} uploadé et indexé avec succès.")
        return redirect(url_for("upload_file"))

    return render_template("upload.html")


@app.route("/stats")
@login_required
def stats():
    try:
        uploads_count = int(redis_client.get("uploads:count") or 0)
    except Exception:
        uploads_count = -1
    return render_template("stats.html", uploads_count=uploads_count)


# --- Liste des fichiers présents dans /logs ---
@app.route("/files")
@login_required
def list_files():
    files = []
    folder = app.config["UPLOAD_FOLDER"]

    if os.path.isdir(folder):
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append({
                    "name": name,
                    "size": size
                })

    files = sorted(files, key=lambda f: f["name"])
    return render_template("files.html", files=files)


# --- Historique des uploads depuis MongoDB ---
@app.route("/uploads")
@login_required
def list_uploads():
    docs = uploads_collection.find().sort("uploaded_at", -1)

    uploads = []
    for d in docs:
        uploads.append({
            "filename": d.get("filename"),
            "size": d.get("size"),
            "uploaded_at": d.get("uploaded_at"),
            "source": d.get("source", "webapp"),
        })

    return render_template("uploads.html", uploads=uploads)


# --- Recherche de logs dans Elasticsearch (avec filtres) ---
@app.route("/search", methods=["GET", "POST"])
@login_required
def search_logs():
    results = []
    query_text = ""
    action_filter = ""
    from_time = ""
    to_time = ""

    if request.method == "POST":
        query_text = request.form.get("q", "").strip()
        action_filter = request.form.get("action", "").strip()
        from_time = request.form.get("from_time", "").strip()
        to_time = request.form.get("to_time", "").strip()

        must_clauses = []
        filter_clauses = []

        if query_text:
            must_clauses.append({
                "multi_match": {
                    "query": query_text,
                    "fields": ["username", "ip", "country", "action", "message"]
                }
            })

        if action_filter:
            filter_clauses.append({
                "term": {"action.keyword": action_filter}
            })

        if from_time or to_time:
            range_body = {}
            if from_time:
                range_body["gte"] = from_time
            if to_time:
                range_body["lte"] = to_time
            filter_clauses.append({
                "range": {
                    "@timestamp": range_body
                }
            })

        body = {
            "size": 50,
            "query": {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            },
            "sort": [
                {"@timestamp": {"order": "desc"}}
            ]
        }

        resp = es.search(index=INDEX_NAME, body=body)
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            results.append({
                "timestamp": src.get("@timestamp", src.get("timestamp")),
                "level": src.get("level"),
                "action": src.get("action"),
                "username": src.get("username"),
                "ip": src.get("ip"),
                "country": src.get("country"),
                "message": src.get("message")
            })

    return render_template(
        "search.html",
        query=query_text,
        results=results,
        action=action_filter,
        from_time=from_time,
        to_time=to_time
    )


# --- Liste des alertes stockées dans MongoDB ---
@app.route("/alerts")
@login_required
def list_alerts():
    docs = alerts_collection.find().sort("created_at", -1)

    alerts = []
    for d in docs:
        alerts.append({
            "type": d.get("type"),
            "ip": d.get("ip"),
            "failures": d.get("failures"),
            "window": d.get("window"),
            "created_at": d.get("created_at"),
        })

    return render_template("alerts.html", alerts=alerts)


# --- Healthcheck global ---
@app.route("/health")
def health():
    status = {"webapp": "ok"}

    # Check Elasticsearch
    try:
        es.info()
        status["elasticsearch"] = "ok"
    except Exception as e:
        status["elasticsearch"] = f"error: {e}"

    # Check MongoDB
    try:
        mongo_client.admin.command("ping")
        status["mongodb"] = "ok"
    except Exception as e:
        status["mongodb"] = f"error: {e}"

    # Check Redis
    try:
        redis_client.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"

    http_code = 200 if all(v == "ok" for v in status.values()) else 500
    return jsonify(status), http_code


# --- Génération des alertes (brute force simple) ---
@app.route("/alerts/run")
@role_required("admin")
def run_alerts():
    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"action.keyword": "LOGIN_FAILED"}},
                    {
                        "range": {
                            "@timestamp": {
                                "gte": "now-30d",
                                "lte": "now"
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "by_ip": {
                "terms": {
                    "field": "ip.keyword",
                    "size": 50
                }
            }
        }
    }

    resp = es.search(index=INDEX_NAME, body=body)

    created = 0
    for bucket in resp["aggregations"]["by_ip"]["buckets"]:
        ip = bucket["key"]
        count_fail = bucket["doc_count"]

        if count_fail >= 5:
            alert_doc = {
                "type": "BRUTE_FORCE_SUSPECT",
                "ip": ip,
                "failures": int(count_fail),
                "window": "last_24h",
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            }

            # 1) Indexation dans Elasticsearch (index security-alerts)
            es.index(index="security-alerts", document=alert_doc)

            # 2) Enregistrement MongoDB (Mongo ajoutera _id)
            alerts_collection.insert_one(alert_doc)

            created += 1

    return f"{created} alertes créées"


# --- Authentification ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            flash(f"Connecté en tant que {username} ({user['role']}).")
            return redirect(url_for("index"))
        else:
            flash("Identifiants invalides.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté.")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
