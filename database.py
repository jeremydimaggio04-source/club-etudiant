import sqlite3
import datetime
import os

DB_NAME = "club.db"

# ---------------------------------------------------
# Suppression ancienne base (pour repartir propre)
# ---------------------------------------------------
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print("Ancienne base supprimée, recréation en cours...")

# ---------------------------------------------------
# Création nouvelle base
# ---------------------------------------------------
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# ---------------------------------------------------
# TABLE MEMBRES
# ---------------------------------------------------
cursor.execute("""
CREATE TABLE membres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'membre',
    date_inscription TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
""")

# ---------------------------------------------------
# TABLE EVENEMENTS
# ---------------------------------------------------
cursor.execute("""
CREATE TABLE evenements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    date TEXT NOT NULL,
    lieu TEXT NOT NULL,
    description TEXT
);
""")

# ---------------------------------------------------
# TABLE PARTICIPATIONS
# ---------------------------------------------------
cursor.execute("""
CREATE TABLE participations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_membre INTEGER NOT NULL,
    id_evenement INTEGER NOT NULL,
    FOREIGN KEY(id_membre) REFERENCES membres(id),
    FOREIGN KEY(id_evenement) REFERENCES evenements(id)
);
""")

# ---------------------------------------------------
# Ajout d’un ADMIN par défaut
# ---------------------------------------------------
cursor.execute("""
INSERT INTO membres (nom, prenom, email, password, role, date_inscription, active)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    "Admin",
    "Super",
    "admin@club.com",
    "admin",        # mot de passe admin
    "admin",        # rôle admin
    datetime.date.today().isoformat(),
    1
))

conn.commit()
conn.close()

print("Base de données initialisée avec succès !")
print("Compte administrateur : admin@club.com / admin")

ALTER TABLE membres ADD COLUMN photo TEXT DEFAULT 'default.png';
