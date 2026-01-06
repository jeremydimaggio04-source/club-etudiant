from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import datetime
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = "1234"

# ----------------------------------------
# UPLOAD CONFIG
# ----------------------------------------
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
ALLOWED_EXT = {"jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ----------------------------------------
# DATABASE
# ----------------------------------------
def get_db_connection():
    conn = sqlite3.connect("club.db")
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------------
# FLASH TOASTS
# ----------------------------------------
def flash_message(text, type="success"):
    if "flash_messages" not in session:
        session["flash_messages"] = []
    session["flash_messages"].append({"text": text, "type": type})

# ----------------------------------------
# LOGIN REQUIRED
# ----------------------------------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            flash_message("Veuillez vous connecter", "error")
            return redirect("/login")
        return f(*args, **kwargs)
    return wrap

# ----------------------------------------
# THEME TOGGLE
# ----------------------------------------
@app.route("/toggle_theme", methods=["POST"])
def toggle_theme():
    session["theme"] = "dark" if session.get("theme", "light") == "light" else "light"
    return redirect(request.referrer or "/")

# ----------------------------------------
# LOGIN
# ----------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM membres WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            flash_message("Connexion réussie ! Bienvenue 👋", "success")
            return redirect("/")
        else:
            flash_message("Identifiants incorrects", "error")
            return redirect("/login")

    return render_template("login.html")

# ----------------------------------------
# REGISTER
# ----------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nom = request.form["nom"]
        prenom = request.form["prenom"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        exists = conn.execute("SELECT * FROM membres WHERE email = ?", (email,)).fetchone()

        if exists:
            conn.close()
            flash_message("Cet email est déjà utilisé.", "error")
            return redirect("/register")

        conn.execute("""
            INSERT INTO membres (nom, prenom, email, password, date_inscription, active, role, photo)
            VALUES (?, ?, ?, ?, ?, 1, 'membre', 'default.png')
        """, (nom, prenom, email, password, datetime.date.today().isoformat()))

        conn.commit()
        conn.close()

        flash_message("Compte créé avec succès !", "success")
        return redirect("/login")

    return render_template("register.html")

# ----------------------------------------
# LOGOUT
# ----------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash_message("Déconnecté avec succès", "info")
    return redirect("/login")

# ----------------------------------------
# HOME (OFFICIEL - UN SEUL)
# ----------------------------------------
@app.route("/")
@login_required
def home():
    conn = get_db_connection()
    club = conn.execute("SELECT * FROM club LIMIT 1").fetchone()
    conn.close()
    return render_template("index.html", club=club)

# ----------------------------------------
# DASHBOARD
# ----------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()

    count_membres = conn.execute("SELECT COUNT(*) FROM membres WHERE active = 1").fetchone()[0]
    count_events = conn.execute("SELECT COUNT(*) FROM evenements").fetchone()[0]
    count_participations = conn.execute("SELECT COUNT(*) FROM participations").fetchone()[0]

    last_membres = conn.execute("""
        SELECT prenom, nom, email, date_inscription
        FROM membres WHERE active = 1
        ORDER BY id DESC LIMIT 5
    """).fetchall()

    last_events = conn.execute("""
        SELECT titre, date, lieu
        FROM evenements
        ORDER BY id DESC LIMIT 5
    """).fetchall()

    conn.close()

    return render_template("dashboard.html",
                           count_membres=count_membres,
                           count_events=count_events,
                           count_participations=count_participations,
                           last_membres=last_membres,
                           last_events=last_events)

# ----------------------------------------
# API DASHBOARD
# ----------------------------------------
@app.route("/api/dashboard")
@login_required
def api_dashboard():
    conn = get_db_connection()

    membres_par_mois = conn.execute("""
        SELECT substr(date_inscription, 1, 7) AS mois, COUNT(*)
        FROM membres
        GROUP BY mois
    """).fetchall()

    participations = conn.execute("""
        SELECT evenements.titre, COUNT(participations.id)
        FROM evenements
        LEFT JOIN participations ON participations.id_evenement = evenements.id
        GROUP BY evenements.id
    """).fetchall()

    conn.close()

    return jsonify({
        "membres_mois": {row[0]: row[1] for row in membres_par_mois},
        "participations": {row[0]: row[1] for row in participations}
    })

# ----------------------------------------
# PROFIL
# ----------------------------------------
@app.route("/profil")
@login_required
def profil():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM membres WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("profil.html", user=user)

# ----------------------------------------
# CHANGE PASSWORD
# ----------------------------------------
@app.route("/profil/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old = request.form["old_password"]
        new = request.form["new_password"]

        conn = get_db_connection()
        user = conn.execute("SELECT password FROM membres WHERE id = ?", (session["user_id"],)).fetchone()

        if user["password"] != old:
            flash_message("Ancien mot de passe incorrect", "error")
            conn.close()
            return redirect("/profil/password")

        conn.execute("UPDATE membres SET password = ? WHERE id = ?", (new, session["user_id"]))
        conn.commit()
        conn.close()

        flash_message("Mot de passe modifié", "success")
        return redirect("/profil")

    return render_template("password.html")

# ----------------------------------------
# MEMBRES (CRUD)
# ----------------------------------------
@app.route("/membres")
@login_required
def membres():
    conn = get_db_connection()
    membres = conn.execute("SELECT * FROM membres WHERE active = 1").fetchall()
    conn.close()
    return render_template("membres.html", membres=membres)

@app.route("/membres/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_membre():
    if request.method == "POST":
        nom = request.form["nom"]
        prenom = request.form["prenom"]
        email = request.form["email"]
        password = request.form["password"]

        photo = "default.png"

        if "photo" in request.files:
            file = request.files["photo"]
            if file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                photo = filename

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO membres (nom, prenom, email, password, date_inscription, active, role, photo)
            VALUES (?, ?, ?, ?, ?, 1, 'membre', ?)
        """, (nom, prenom, email, password, datetime.date.today().isoformat(), photo))

        conn.commit()
        conn.close()

        flash_message("Membre ajouté !")
        return redirect("/membres")

    return render_template("ajouter_membre.html")

@app.route("/membres/modifier/<int:id>", methods=["GET", "POST"])
@login_required
def modifier_membre(id):
    conn = get_db_connection()

    if request.method == "POST":
        conn.execute("""
            UPDATE membres SET nom = ?, prenom = ?, email = ?
            WHERE id = ?
        """, (request.form["nom"], request.form["prenom"], request.form["email"], id))

        if "photo" in request.files:
            file = request.files["photo"]
            if file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                conn.execute("UPDATE membres SET photo = ? WHERE id = ?", (filename, id))

        conn.commit()
        conn.close()

        flash_message("Membre modifié")
        return redirect("/membres")

    membre = conn.execute("SELECT * FROM membres WHERE id = ?", (id,)).fetchone()
    conn.close()

    return render_template("modifier_membre.html", membre=membre)

@app.route("/membres/supprimer/<int:id>")
@login_required
def supprimer_membre(id):
    conn = get_db_connection()
    conn.execute("UPDATE membres SET active = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash_message("Membre supprimé")
    return redirect("/membres")

# ----------------------------------------
# EVENEMENTS
# ----------------------------------------
@app.route("/evenements")
@login_required
def evenements():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM evenements").fetchall()
    conn.close()
    return render_template("evenements.html", events=events)

@app.route("/evenements/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_evenement():
    if request.method == "POST":
        titre = request.form["titre"]
        date = request.form["date"]
        lieu = request.form["lieu"]
        description = request.form["description"]

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO evenements (titre, date, lieu, description)
            VALUES (?, ?, ?, ?)
        """, (titre, date, lieu, description))
        conn.commit()
        conn.close()

        flash_message("Événement créé")
        return redirect("/evenements")

    return render_template("ajouter_evenement.html")

@app.route("/evenements/<int:id>")
@login_required
def details_evenement(id):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM evenements WHERE id = ?", (id,)).fetchone()
    participants = conn.execute("""
        SELECT membres.prenom, membres.nom
        FROM participations
        JOIN membres ON participations.id_membre = membres.id
        WHERE id_evenement = ?
    """, (id,)).fetchall()
    conn.close()

    return render_template("details_evenement.html",
                           event=event,
                           participants=participants)

@app.route("/evenements/<int:id>/inscrire", methods=["GET", "POST"])
@login_required
def inscrire_membre_evenement(id):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM evenements WHERE id = ?", (id,)).fetchone()
    membres = conn.execute("SELECT * FROM membres WHERE active = 1").fetchall()

    if request.method == "POST":
        id_membre = request.form["id_membre"]
        conn.execute("""
            INSERT INTO participations (id_membre, id_evenement)
            VALUES (?, ?)
        """, (id_membre, id))
        conn.commit()
        conn.close()

        flash_message("Inscription ajoutée")
        return redirect(f"/evenements/{id}")

    conn.close()
    return render_template("inscrire_membre.html", event=event, membres=membres)

@app.route("/evenements/supprimer/<int:id>")
@login_required
def supprimer_evenement(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM participations WHERE id_evenement = ?", (id,))
    conn.execute("DELETE FROM evenements WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash_message("Événement supprimé")
    return redirect("/evenements")

# ----------------------------------------
# CALENDRIER
# ----------------------------------------
@app.route("/calendar")
@login_required
def calendar():
    return render_template("calendar.html")

@app.route("/api/events")
@login_required
def api_events():
    conn = get_db_connection()
    rows = conn.execute("SELECT id, titre, date FROM evenements").fetchall()
    conn.close()
    return jsonify([{"id": e["id"], "title": e["titre"], "start": e["date"]} for e in rows])

# ----------------------------------------
# EDIT CLUB (ADMIN ONLY)
# ----------------------------------------
@app.route("/club/edit", methods=["GET", "POST"])
@login_required
def edit_club():

    # 🔒 Sécurité : accès réservé uniquement aux admins
    if session.get("role") != "admin":
        flash_message("Accès réservé aux administrateurs.", "error")
        return redirect("/")

    conn = get_db_connection()

    if request.method == "POST":
        nom = request.form["nom"]
        description = request.form["description"]

        conn.execute("UPDATE club SET nom = ?, description = ?", (nom, description))
        conn.commit()
        conn.close()

        flash_message("Club mis à jour !")
        return redirect("/")

    club = conn.execute("SELECT * FROM club LIMIT 1").fetchone()
    conn.close()

    return render_template("edit_club.html", club=club)

# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
