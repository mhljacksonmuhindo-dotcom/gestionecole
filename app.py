
import hmac
import os
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import click
from flask import Flask, abort, g, render_template, redirect, url_for, flash, request, session
from mysql.connector import Error
from database import obtenir_connexion
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
environment = os.environ.get("APP_ENV", "development").lower()
configured_secret = os.environ.get("FLASK_SECRET_KEY")
if environment == "production" and not configured_secret:
    raise RuntimeError("FLASK_SECRET_KEY doit être définie en production.")
app.config.update(
    SECRET_KEY=configured_secret or secrets.token_hex(32),
    PASSWORD_MIN_LENGTH=7 if environment == "development" else 12,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=environment == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)


MODULES = {
    "ecoles": {
        "titre": "Écoles",
        "template": "ecoles/liste.html",
        "variable": "ecoles",
    },
    "annees_scolaires": {
        "titre": "Années scolaires",
        "template": "annees_scolaires/liste.html",
        "variable": "annees",
    },
    "classes": {
        "titre": "Classes",
        "template": "classes/liste.html",
        "variable": "classes",
    },
    "eleves": {
        "titre": "Élèves et inscriptions",
        "template": "eleves/liste.html",
        "variable": "eleves",
    },
    "enseignants": {
        "titre": "Enseignants",
        "template": "enseignants/liste.html",
        "variable": "enseignants",
    },
    "presences": {
        "titre": "Présences des enseignants",
        "template": "presences/liste.html",
        "variable": "presences",
    },
    "frais": {
        "titre": "Frais scolaires",
        "template": "finances/frais.html",
        "variable": "types_frais",
    },
    "paiements_eleves": {
        "titre": "Paiements des élèves",
        "template": "finances/paiements_eleves.html",
        "variable": "paiements",
    },
    "repartitions": {
        "titre": "Répartitions financières",
        "template": "finances/repartitions.html",
        "variable": "repartitions",
    },
    "remunerations": {
        "titre": "Rémunérations des enseignants",
        "template": "finances/remunerations.html",
        "variable": "remunerations",
    },
    "paiements_enseignants": {
        "titre": "Paiements des enseignants",
        "template": "finances/paiements_enseignants.html",
        "variable": "paiements_enseignants",
    },
    "notifications": {
        "titre": "Notifications",
        "template": "notifications/liste.html",
        "variable": "notifications",
    },
    "rapports": {
        "titre": "Rapports",
        "template": "rapports/index.html",
        "variable": None,
    },
    "utilisateurs": {
        "titre": "Utilisateurs",
        "template": "utilisateurs/liste.html",
        "variable": "utilisateurs",
    },
    "journal": {
        "titre": "Journal d'activités",
        "template": "journal/liste.html",
        "variable": "activites",
    },
}

TABLES_BY_MODULE = {
    "ecoles": "ecoles",
    "annees_scolaires": "annees_scolaires",
    "classes": "classes",
    "eleves": "eleves",
    "enseignants": "enseignants",
    "presences": "presences_enseignants",
    "frais": "types_frais",
    "paiements_eleves": "paiements_eleves",
    "repartitions": "repartitions_paiements",
    "remunerations": "remunerations_enseignants",
    "paiements_enseignants": "paiements_enseignants",
    "notifications": "notifications",
    "utilisateurs": "utilisateurs",
    "journal": "journal",
}


def trouver_utilisateur(identifiant):
    connexion = obtenir_connexion()
    if connexion is None:
        raise RuntimeError("La base de données est indisponible.")

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT id, ecole_id, nom, postnom, prenom, nom_utilisateur,
                   email, mot_de_passe, role, statut
            FROM utilisateurs
            WHERE nom_utilisateur = %s OR email = %s
            LIMIT 1
            """,
            (identifiant, identifiant),
        )
        return cast(dict[str, Any] | None, curseur.fetchone())
    except Error as erreur:
        app.logger.exception("Recherche du compte utilisateur impossible.")
        raise RuntimeError("La base de données est indisponible.") from erreur
    finally:
        connexion.close()


def charger_utilisateur_connecte(utilisateur_id):
    connexion = obtenir_connexion()
    if connexion is None:
        raise RuntimeError("La base de données est indisponible.")

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
                 SELECT u.id, u.ecole_id, u.nom, u.postnom, u.prenom, u.role, u.statut,
                     e.statut AS statut_ecole
                 FROM utilisateurs u
                 INNER JOIN ecoles e ON e.id = u.ecole_id
                 WHERE u.id = %s
            LIMIT 1
            """,
            (utilisateur_id,),
        )
        return cast(dict[str, Any] | None, curseur.fetchone())
    except Error as erreur:
        app.logger.exception("Vérification du compte connecté impossible.")
        raise RuntimeError("La base de données est indisponible.") from erreur
    finally:
        connexion.close()


def enregistrer_derniere_connexion(utilisateur_id):
    connexion = obtenir_connexion()
    if connexion is None:
        return False

    try:
        curseur = connexion.cursor()
        curseur.execute(
            "UPDATE utilisateurs SET derniere_connexion = NOW() WHERE id = %s",
            (utilisateur_id,),
        )
        connexion.commit()
        return True
    except Error:
        connexion.rollback()
        app.logger.exception("Mise à jour de la date de connexion impossible.")
        return False
    finally:
        connexion.close()


def obtenir_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def injecter_contexte_securite():
    return {
        "csrf_token": obtenir_csrf_token,
        "current_user": getattr(g, "current_user", None),
        "password_min_length": app.config["PASSWORD_MIN_LENGTH"],
    }


@app.before_request
def proteger_requetes():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token_session = session.get("_csrf_token", "")
        token_formulaire = request.form.get("_csrf_token", "")
        if not token_session or not hmac.compare_digest(token_session, token_formulaire):
            abort(400)

    if request.endpoint in {"connexion", "deconnexion", "sante", "static", None}:
        return None

    utilisateur_id = session.get("user_id")
    if not utilisateur_id:
        return redirect(url_for("connexion"))

    try:
        utilisateur = charger_utilisateur_connecte(utilisateur_id)
    except RuntimeError:
        abort(503)

    if not utilisateur or utilisateur.get("statut") != "actif" or utilisateur.get("statut_ecole") == "inactive":
        session.clear()
        return redirect(url_for("connexion"))

    g.current_user = utilisateur
    if utilisateur.get("role") == "administrateur":
        return None
    if utilisateur.get("role") == "caissier":
        modules_autorises = {"eleves", "paiements_eleves"}
        if request.endpoint in {"accueil", "dashboard"}:
            return None
        view_args = request.view_args or {}
        if request.endpoint == "page_module" and view_args.get("module") in modules_autorises:
            return None
        if request.endpoint in {"formulaire_paiement_eleve", "recu_paiement", "detail_eleve"}:
            return None
        abort(403)
    if utilisateur.get("role") == "enseignant":
        if request.endpoint in {"accueil", "dashboard", "notifications_enseignant", "espace_enseignant"}:
            return None
        if request.endpoint == "marquer_notification_lue":
            return None
    abort(403)


def verifier_connexion_base():
    """Vérifie que MySQL répond sans modifier aucune donnée."""
    connexion = obtenir_connexion()

    if connexion is None:
        return False

    try:
        curseur = connexion.cursor()
        curseur.execute("SELECT 1")
        curseur.fetchone()
        curseur.close()
        return True
    except Exception:
        app.logger.exception("Vérification MySQL impossible.")
        return False
    finally:
        connexion.close()


def table_existe(nom_table):
    connexion = obtenir_connexion()
    if connexion is None:
        return False

    try:
        curseur = connexion.cursor()
        curseur.execute("SHOW TABLES LIKE %s", (nom_table,))
        return curseur.fetchone() is not None
    except Exception:
        app.logger.exception("Contrôle de table MySQL impossible pour %s.", nom_table)
        return False
    finally:
        connexion.close()


def colonnes_table(nom_table):
    connexion = obtenir_connexion()
    if connexion is None:
        return []

    try:
        curseur = connexion.cursor()
        curseur.execute(f"SHOW COLUMNS FROM {nom_table}")
        lignes = cast(list[tuple[Any, ...]], curseur.fetchall())
        colonnes = [ligne[0] for ligne in lignes]
        return colonnes
    except Exception:
        app.logger.exception("Lecture des colonnes MySQL impossible pour %s.", nom_table)
        return []
    finally:
        connexion.close()


def compte_table(nom_table):
    if not table_existe(nom_table):
        return "—"

    connexion = obtenir_connexion()
    if connexion is None:
        return "—"

    try:
        curseur = connexion.cursor()
        curseur.execute(f"SELECT COUNT(*) FROM {nom_table}")
        ligne = curseur.fetchone()
        if ligne is None:
            return "—"
        total = cast(tuple[Any, ...], ligne)[0]
        return int(total)
    except Exception:
        app.logger.exception("Impossible de compter les enregistrements de %s.", nom_table)
        return "—"
    finally:
        connexion.close()


def statistiques_dashboard(ecole_id: int) -> dict[str, Any]:
    connexion = obtenir_connexion()
    if connexion is None:
        return {
            "eleves": "—", "paiements_mois": "—", "presences": "—",
            "remunerations": "—", "ecoles": "—", "classes": "—", "devise": "",
        }

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT e.devise,
                (SELECT COUNT(*) FROM inscriptions i
                 INNER JOIN eleves el ON el.id = i.eleve_id
                 INNER JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
                 WHERE el.ecole_id = e.id AND i.statut = 'inscrit' AND a.statut = 'en_cours') AS eleves,
                (SELECT COALESCE(SUM(p.montant_paye), 0) FROM paiements_eleves p
                 INNER JOIN inscriptions i ON i.id = p.inscription_id
                 INNER JOIN eleves el ON el.id = i.eleve_id
                 WHERE el.ecole_id = e.id AND p.statut = 'valide'
                   AND YEAR(p.date_paiement) = YEAR(CURRENT_DATE())
                   AND MONTH(p.date_paiement) = MONTH(CURRENT_DATE())) AS paiements_mois,
                (SELECT COUNT(*) FROM presences_enseignants p
                 INNER JOIN enseignants ens ON ens.id = p.enseignant_id
                 WHERE ens.ecole_id = e.id AND p.date_presence = CURRENT_DATE()) AS presences,
                (SELECT COUNT(*) FROM classes c
                 INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
                 WHERE c.ecole_id = e.id AND c.statut = 'active' AND a.statut = 'en_cours') AS classes,
                (SELECT COUNT(*) FROM remunerations_enseignants r
                 INNER JOIN enseignants ens ON ens.id = r.enseignant_id
                 WHERE ens.ecole_id = e.id AND r.statut = 'validee') AS remunerations
            FROM ecoles e WHERE e.id = %s AND e.statut = 'active'
            LIMIT 1
            """,
            (ecole_id,),
        )
        statistiques = cast(dict[str, Any] | None, curseur.fetchone())
        if statistiques is None:
            return {
                "eleves": 0, "paiements_mois": 0, "presences": 0,
                "remunerations": 0, "ecoles": 0, "classes": 0, "devise": "",
            }
        statistiques["ecoles"] = 1
        return statistiques
    except Exception:
        app.logger.exception("Chargement des statistiques du tableau de bord impossible.")
        return {
            "eleves": "—", "paiements_mois": "—", "presences": "—",
            "remunerations": "—", "ecoles": "—", "classes": "—", "devise": "",
        }
    finally:
        connexion.close()


def charger_encaissements_mensuels(ecole_id: int, annee_scolaire_id: int | None = None) -> list[dict[str, Any]]:
    connexion = obtenir_connexion()
    if connexion is None:
        return []

    try:
        curseur = connexion.cursor(dictionary=True)
        if annee_scolaire_id is None:
            curseur.execute(
                """
                SELECT id
                FROM annees_scolaires
                WHERE ecole_id = %s AND statut = 'en_cours'
                ORDER BY date_debut DESC
                LIMIT 1
                """,
                (ecole_id,),
            )
            annee = cast(dict[str, Any] | None, curseur.fetchone())
            if annee is None:
                return []
            annee_scolaire_id = int(annee["id"])

        curseur.execute(
            """
            SELECT MONTH(p.date_paiement) AS mois_num,
                   CASE MONTH(p.date_paiement)
                       WHEN 1 THEN 'Jan' WHEN 2 THEN 'Fév' WHEN 3 THEN 'Mars'
                       WHEN 4 THEN 'Avr' WHEN 5 THEN 'Mai' WHEN 6 THEN 'Juin'
                       WHEN 7 THEN 'Juil' WHEN 8 THEN 'Août' WHEN 9 THEN 'Sept'
                       WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN 12 THEN 'Déc'
                   END AS nom,
                   SUM(p.montant_paye) AS montant
            FROM paiements_eleves p
            INNER JOIN inscriptions i ON i.id = p.inscription_id
            INNER JOIN eleves e ON e.id = i.eleve_id
            WHERE e.ecole_id = %s
              AND i.annee_scolaire_id = %s
              AND p.statut = 'valide'
            GROUP BY MONTH(p.date_paiement), CASE MONTH(p.date_paiement)
                       WHEN 1 THEN 'Jan' WHEN 2 THEN 'Fév' WHEN 3 THEN 'Mars'
                       WHEN 4 THEN 'Avr' WHEN 5 THEN 'Mai' WHEN 6 THEN 'Juin'
                       WHEN 7 THEN 'Juil' WHEN 8 THEN 'Août' WHEN 9 THEN 'Sept'
                       WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN 12 THEN 'Déc'
                   END
            ORDER BY MONTH(p.date_paiement)
            """,
            (ecole_id, annee_scolaire_id),
        )
        donnees = cast(list[dict[str, Any]], curseur.fetchall())
        if not donnees:
            return []

        montants = [Decimal(str(donnee.get("montant") or 0)) for donnee in donnees]
        montant_max = max(montants) if montants else Decimal("0")
        if montant_max <= 0:
            return []

        resultats: list[dict[str, Any]] = []
        for donnee in donnees:
            montant = Decimal(str(donnee.get("montant") or 0))
            pourcentage = 100.0 if montant_max == 0 else float((montant / montant_max) * 100)
            resultats.append({
                "nom": donnee.get("nom") or "",
                "montant": float(montant),
                "pourcentage": round(pourcentage, 1),
            })
        return resultats
    except Exception:
        app.logger.exception("Chargement des encaissements mensuels impossible.")
        return []
    finally:
        connexion.close()


def charger_table(nom_table) -> tuple[list[dict[str, Any]], str]:
    if not table_existe(nom_table):
        return [], "Aucune donnée n'est disponible tant que la table MySQL n'est pas validée."

    connexion = obtenir_connexion()
    if connexion is None:
        return [], "La connexion MySQL est indisponible pour le moment."

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(f"SELECT * FROM {nom_table} LIMIT 50")
        donnees = cast(list[dict[str, Any]], curseur.fetchall())
        return donnees, ""
    except Exception:
        app.logger.exception("Lecture de la table %s impossible.", nom_table)
        return [], "Le chargement des données a été suspendu après vérification du schéma MySQL."
    finally:
        connexion.close()


def charger_module(module: str, ecole_id: int | None = None) -> tuple[list[dict[str, Any]], str]:
    if module == "eleves":
        return charger_eleves(ecole_id, request.args.get("q", "").strip())
    if ecole_id is None:
        return [], "Aucun établissement n'est associé au compte connecté."
    if module == "enseignants":
        return charger_enseignants(ecole_id, request.args.get("q", "").strip())

    requetes = {
        "annees_scolaires": (
            "SELECT * FROM annees_scolaires WHERE ecole_id = %s ORDER BY date_debut DESC LIMIT 100",
            (ecole_id,),
        ),
        "classes": (
            """
            SELECT c.*, a.libelle AS annee_scolaire, COUNT(i.id) AS effectif
            FROM classes c
            INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
            LEFT JOIN inscriptions i ON i.classe_id = c.id AND i.statut = 'inscrit'
            WHERE c.ecole_id = %s
            GROUP BY c.id, a.libelle
            ORDER BY a.date_debut DESC, c.niveau, c.nom LIMIT 100
            """,
            (ecole_id,),
        ),
        "enseignants": (
            """
            SELECT e.*, CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS nom_complet,
                   c.nom AS classe, a.libelle AS annee_scolaire, af.fonction
            FROM enseignants e
            LEFT JOIN affectations_enseignants af ON af.id = (
                SELECT af2.id FROM affectations_enseignants af2
                WHERE af2.enseignant_id = e.id
                ORDER BY af2.date_debut DESC, af2.id DESC LIMIT 1
            )
            LEFT JOIN classes c ON c.id = af.classe_id
            LEFT JOIN annees_scolaires a ON a.id = af.annee_scolaire_id
            WHERE e.ecole_id = %s ORDER BY e.nom, e.prenom LIMIT 100
            """,
            (ecole_id,),
        ),
        "presences": (
            """
            SELECT p.*, CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS enseignant,
                   p.justification AS observation
            FROM presences_enseignants p
            INNER JOIN enseignants e ON e.id = p.enseignant_id
            WHERE e.ecole_id = %s
            ORDER BY p.date_presence DESC, p.id DESC LIMIT 100
            """,
            (ecole_id,),
        ),
        "frais": (
            "SELECT * FROM types_frais WHERE ecole_id = %s ORDER BY nom LIMIT 100",
            (ecole_id,),
        ),
        "paiements_eleves": (
            """
             SELECT p.*, p.montant_paye AS montant,
                 CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS eleve,
                 e.matricule, c.nom AS classe, f.nom AS type_frais,
                 CONCAT_WS(' ', u.nom, u.postnom, u.prenom) AS caissier,
                 ec.devise
            FROM paiements_eleves p
            INNER JOIN inscriptions i ON i.id = p.inscription_id
            INNER JOIN eleves e ON e.id = i.eleve_id
             INNER JOIN classes c ON c.id = i.classe_id
            INNER JOIN types_frais f ON f.id = p.type_frais_id
             INNER JOIN ecoles ec ON ec.id = e.ecole_id
            LEFT JOIN utilisateurs u ON u.id = p.encaisse_par
            WHERE e.ecole_id = %s
            ORDER BY p.date_paiement DESC, p.id DESC LIMIT 100
            """,
            (ecole_id,),
        ),
        "repartitions": (
            """
             SELECT r.date_repartition AS date, p.numero_recu AS paiement,
                 'Hiérarchie' AS categorie, r.pourcentage_hierarchie AS pourcentage,
                 r.montant_hierarchie AS montant, ec.devise
             FROM repartitions_paiements r
            INNER JOIN paiements_eleves p ON p.id = r.paiement_id
            INNER JOIN inscriptions i ON i.id = p.inscription_id
            INNER JOIN eleves e ON e.id = i.eleve_id
             INNER JOIN ecoles ec ON ec.id = e.ecole_id
             WHERE e.ecole_id = %s
             UNION ALL
             SELECT r.date_repartition, p.numero_recu, 'Primes enseignants',
                 r.pourcentage_prime_enseignants, r.montant_prime_enseignants, ec.devise
             FROM repartitions_paiements r
             INNER JOIN paiements_eleves p ON p.id = r.paiement_id
             INNER JOIN inscriptions i ON i.id = p.inscription_id
             INNER JOIN eleves e ON e.id = i.eleve_id
             INNER JOIN ecoles ec ON ec.id = e.ecole_id
             WHERE e.ecole_id = %s
             UNION ALL
             SELECT r.date_repartition, p.numero_recu, 'Promoteur',
                 r.pourcentage_promoteur, r.montant_promoteur, ec.devise
             FROM repartitions_paiements r
             INNER JOIN paiements_eleves p ON p.id = r.paiement_id
             INNER JOIN inscriptions i ON i.id = p.inscription_id
             INNER JOIN eleves e ON e.id = i.eleve_id
             INNER JOIN ecoles ec ON ec.id = e.ecole_id
             WHERE e.ecole_id = %s
             UNION ALL
             SELECT r.date_repartition, p.numero_recu, 'Fonctionnement',
                 r.pourcentage_fonctionnement, r.montant_fonctionnement, ec.devise
             FROM repartitions_paiements r
             INNER JOIN paiements_eleves p ON p.id = r.paiement_id
             INNER JOIN inscriptions i ON i.id = p.inscription_id
             INNER JOIN eleves e ON e.id = i.eleve_id
             INNER JOIN ecoles ec ON ec.id = e.ecole_id
             WHERE e.ecole_id = %s
             ORDER BY date DESC LIMIT 400
            """,
             (ecole_id, ecole_id, ecole_id, ecole_id),
        ),
        "remunerations": (
            """
            SELECT r.*, CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS enseignant, ec.devise
            FROM remunerations_enseignants r
            INNER JOIN enseignants e ON e.id = r.enseignant_id
            INNER JOIN ecoles ec ON ec.id = e.ecole_id
            WHERE e.ecole_id = %s
            ORDER BY r.annee DESC, r.mois DESC, r.id DESC LIMIT 100
            """,
            (ecole_id,),
        ),
        "paiements_enseignants": (
            """
            SELECT p.*, p.montant_paye AS montant,
                   p.reference_paiement AS reference,
                   CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS enseignant,
                   r.mois, r.annee, ec.devise
            FROM paiements_enseignants p
            INNER JOIN remunerations_enseignants r ON r.id = p.remuneration_id
            INNER JOIN enseignants e ON e.id = r.enseignant_id
            INNER JOIN ecoles ec ON ec.id = e.ecole_id
            WHERE e.ecole_id = %s
            ORDER BY p.date_paiement DESC, p.id DESC LIMIT 100
            """,
            (ecole_id,),
        ),
        "utilisateurs": (
            """
            SELECT id, CONCAT_WS(' ', nom, postnom, prenom) AS nom_complet,
                   nom_utilisateur AS identifiant, role, statut
            FROM utilisateurs WHERE ecole_id = %s ORDER BY nom, prenom LIMIT 100
            """,
            (ecole_id,),
        ),
        "journal": (
            """
            SELECT j.id, j.action, j.table_concernee, j.enregistrement_id,
                   j.description, j.adresse_ip, j.date_action,
                   CONCAT_WS(' ', u.nom, u.postnom, u.prenom) AS utilisateur
            FROM journal_activites j
            INNER JOIN utilisateurs u ON u.id = j.utilisateur_id
            WHERE u.ecole_id = %s
            ORDER BY j.date_action DESC, j.id DESC LIMIT 200
            """,
            (ecole_id,),
        ),
    }
    requete_et_parametres = requetes.get(module)
    if module == "notifications":
        connexion = obtenir_connexion()
        if connexion is None:
            return [], "La connexion MySQL est indisponible pour le moment."
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                """
                SELECT n.id, n.titre, n.message, n.type, n.date_creation,
                       COUNT(d.id) AS nombre_destinataires
                FROM notifications n
                LEFT JOIN destinataires_notifications d ON d.notification_id = n.id
                WHERE n.ecole_id = %s
                GROUP BY n.id
                ORDER BY n.date_creation DESC LIMIT 100
                """,
                (ecole_id,),
            )
            return cast(list[dict[str, Any]], curseur.fetchall()), ""
        except Exception:
            app.logger.exception("Chargement des notifications impossible.")
            return [], "Le chargement des notifications a échoué."
        finally:
            connexion.close()
    if module == "ecoles":
        connexion = obtenir_connexion()
        if connexion is None:
            return [], "La connexion MySQL est indisponible pour le moment."
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT * FROM ecoles WHERE id = %s LIMIT 1",
                (ecole_id,),
            )
            ecole = cast(dict[str, Any] | None, curseur.fetchone())
            return ([ecole] if ecole else []), ""
        except Exception:
            app.logger.exception("Chargement de l'école impossible.")
            return [], "Le chargement de l'école a échoué."
        finally:
            connexion.close()
    if requete_et_parametres is None:
        return [], "Le module ne possède pas de source de données configurée."

    connexion = obtenir_connexion()
    if connexion is None:
        return [], "La connexion MySQL est indisponible pour le moment."
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(*requete_et_parametres)
        return cast(list[dict[str, Any]], curseur.fetchall()), ""
    except Exception:
        app.logger.exception("Chargement MySQL du module %s impossible.", module)
        return [], "Le chargement des données a échoué."
    finally:
        connexion.close()


def charger_eleves(ecole_id: int | None, recherche: str = "") -> tuple[list[dict[str, Any]], str]:
    if ecole_id is None:
        return [], "Aucun établissement n'est associé au compte connecté."

    connexion = obtenir_connexion()
    if connexion is None:
        return [], "La connexion MySQL est indisponible pour le moment."

    try:
        curseur = connexion.cursor(dictionary=True)
        requete = """
                SELECT e.id, e.matricule, e.nom, e.postnom, e.prenom,
                       CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS nom_complet,
                       e.sexe, e.statut, c.nom AS classe, a.libelle AS annee_scolaire,
                       i.statut AS statut_inscription
                FROM eleves e
                LEFT JOIN inscriptions i ON i.id = (
                    SELECT i2.id FROM inscriptions i2
                    WHERE i2.eleve_id = e.id
                    ORDER BY i2.date_creation DESC, i2.id DESC LIMIT 1
                )
                LEFT JOIN classes c ON c.id = i.classe_id
                LEFT JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
                WHERE e.ecole_id = %s
            """
        parametres: tuple[Any, ...] = (ecole_id,)
        if recherche:
            motif = f"%{recherche}%"
            requete += " AND (e.matricule LIKE %s OR e.nom LIKE %s OR e.postnom LIKE %s OR e.prenom LIKE %s)"
            parametres += (motif, motif, motif, motif)
        requete += " ORDER BY e.nom, e.postnom, e.prenom LIMIT 100"
        curseur.execute(requete, parametres)
        eleves = cast(list[dict[str, Any]], curseur.fetchall())
        return eleves, ""
    except Exception:
        app.logger.exception("Chargement des dossiers élèves impossible.")
        return [], "Le chargement des élèves a échoué."
    finally:
        connexion.close()


def charger_enseignants(ecole_id: int, recherche: str = "") -> tuple[list[dict[str, Any]], str]:
    connexion = obtenir_connexion()
    if connexion is None:
        return [], "La connexion MySQL est indisponible pour le moment."
    try:
        curseur = connexion.cursor(dictionary=True)
        motif = f"%{recherche}%"
        curseur.execute(
            """
            SELECT e.*, CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS nom_complet,
                   c.nom AS classe, a.libelle AS annee_scolaire, af.fonction
            FROM enseignants e
            LEFT JOIN affectations_enseignants af ON af.id = (
                SELECT af2.id FROM affectations_enseignants af2
                WHERE af2.enseignant_id = e.id
                ORDER BY af2.date_debut DESC, af2.id DESC LIMIT 1
            )
            LEFT JOIN classes c ON c.id = af.classe_id
            LEFT JOIN annees_scolaires a ON a.id = af.annee_scolaire_id
            WHERE e.ecole_id = %s AND (%s = '' OR e.matricule LIKE %s
                  OR e.nom LIKE %s OR e.postnom LIKE %s OR e.prenom LIKE %s)
            ORDER BY e.nom, e.prenom LIMIT 100
            """,
            (ecole_id, recherche, motif, motif, motif, motif),
        )
        return cast(list[dict[str, Any]], curseur.fetchall()), ""
    except Exception:
        app.logger.exception("Recherche des enseignants impossible.")
        return [], "Le chargement des enseignants a échoué."
    finally:
        connexion.close()


def charger_classes_inscription(ecole_id: int) -> tuple[list[dict[str, Any]], str]:
    connexion = obtenir_connexion()
    if connexion is None:
        return [], "La connexion MySQL est indisponible pour le moment."

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
                SELECT c.id, c.nom, c.niveau, c.annee_scolaire_id, a.libelle AS annee_scolaire
                FROM classes c
                INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
                WHERE c.ecole_id = %s AND c.statut = 'active' AND a.statut = 'en_cours'
                ORDER BY a.date_debut DESC, c.niveau, c.nom
            """,
            (ecole_id,),
        )
        return cast(list[dict[str, Any]], curseur.fetchall()), ""
    except Exception:
        app.logger.exception("Chargement des classes d'inscription impossible.")
        return [], "Les classes de l'année en cours n'ont pas pu être chargées."
    finally:
        connexion.close()


def charger_references_paiement(ecole_id: int, recherche: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connexion = obtenir_connexion()
    if connexion is None:
        return [], []
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT i.id AS inscription_id, e.id AS eleve_id, e.matricule,
                   CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS eleve,
                   c.nom AS classe, a.libelle AS annee_scolaire
            FROM inscriptions i
            INNER JOIN eleves e ON e.id = i.eleve_id
            INNER JOIN classes c ON c.id = i.classe_id
            INNER JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
            WHERE e.ecole_id = %s AND i.statut = 'inscrit'
              AND e.statut = 'actif' AND a.statut = 'en_cours'
              AND c.statut = 'active'
              AND (%s = '' OR e.matricule LIKE %s OR e.nom LIKE %s
                   OR e.postnom LIKE %s OR e.prenom LIKE %s)
            ORDER BY e.nom, e.postnom, e.prenom LIMIT 100
            """,
            (ecole_id, recherche, f"%{recherche}%", f"%{recherche}%", f"%{recherche}%", f"%{recherche}%"),
        )
        inscriptions = cast(list[dict[str, Any]], curseur.fetchall())
        curseur.execute(
            """
            SELECT f.id, f.nom, f.montant, f.obligatoire, f.annee_scolaire_id,
                   a.libelle AS annee_scolaire
            FROM types_frais f
            INNER JOIN annees_scolaires a ON a.id = f.annee_scolaire_id
            WHERE f.ecole_id = %s AND f.statut = 'actif' AND a.statut = 'en_cours'
            ORDER BY f.nom
            """,
            (ecole_id,),
        )
        frais = cast(list[dict[str, Any]], curseur.fetchall())
        return inscriptions, frais
    except Exception:
        app.logger.exception("Chargement des références de paiement impossible.")
        return [], []
    finally:
        connexion.close()


def enregistrer_donnees_table(nom_table, donnees):
    if not table_existe(nom_table):
        return False, f"La table '{nom_table}' n'est pas encore disponible dans MySQL."

    colonnes = colonnes_table(nom_table)
    if not colonnes:
        return False, "La structure de la table n'a pas pu être vérifiée."

    donnees_nettoyees = {cle: valeur for cle, valeur in donnees.items() if cle in colonnes}
    if not donnees_nettoyees:
        return False, "Aucune colonne compatible n'a été trouvée pour cet enregistrement."

    cles = list(donnees_nettoyees.keys())
    valeurs = tuple(donnees_nettoyees[cle] for cle in cles)
    placeholders = ", ".join(["%s"] * len(cles))

    connexion = obtenir_connexion()
    if connexion is None:
        return False, "La connexion MySQL est indisponible pour enregistrer les données."

    try:
        curseur = connexion.cursor()
        curseur.execute(
            f"INSERT INTO {nom_table} ({', '.join(cles)}) VALUES ({placeholders})",
            valeurs,
        )
        connexion.commit()
        return True, "Enregistrement validé." 
    except Error as erreur:
        connexion.rollback()
        app.logger.exception("Échec de l'enregistrement MySQL dans %s.", nom_table)
        return False, f"L'enregistrement a échoué: {erreur}"
    finally:
        connexion.close()


@app.route("/")
def accueil():
    if g.current_user.get("role") == "caissier":
        return redirect(url_for("page_module", module="paiements_eleves"))
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if g.current_user["role"] == "caissier":
        return redirect(url_for("page_module", module="paiements_eleves"))
    if g.current_user["role"] == "enseignant":
        return redirect(url_for("espace_enseignant"))

    annee_scolaire_id = request.args.get("annee_scolaire_id", type=int)
    statistiques = statistiques_dashboard(g.current_user["ecole_id"])
    encaissements_mensuels = charger_encaissements_mensuels(g.current_user["ecole_id"], annee_scolaire_id)

    return render_template(
        "dashboard.html",
        statistiques=statistiques,
        current_user=g.current_user,
        annee_scolaire=None,
        encaissements_mensuels=encaissements_mensuels,
        notifications=[],
        derniers_paiements=[],
    )


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        identifiant = (request.form.get("identifiant") or "").strip()
        mot_de_passe = request.form.get("mot_de_passe") or ""

        if not identifiant or not mot_de_passe:
            flash("Veuillez remplir les identifiants avant de soumettre le formulaire.", "danger")
            return render_template("auth/connexion.html")

        try:
            utilisateur = trouver_utilisateur(identifiant)
        except RuntimeError:
            app.logger.exception("La base de données est indisponible pendant la connexion.")
            flash("La connexion est temporairement indisponible.", "danger")
            return render_template("auth/connexion.html"), 503

        mot_de_passe_valide = False
        if utilisateur and utilisateur.get("statut") == "actif":
            try:
                mot_de_passe_valide = check_password_hash(
                    utilisateur.get("mot_de_passe", ""), mot_de_passe
                )
            except (TypeError, ValueError):
                mot_de_passe_valide = False

        if not utilisateur or not mot_de_passe_valide:
            flash("Identifiant ou mot de passe incorrect.", "danger")
            return render_template("auth/connexion.html")

        if not enregistrer_derniere_connexion(utilisateur["id"]):
            flash("La connexion est temporairement indisponible.", "danger")
            return render_template("auth/connexion.html"), 503

        session.clear()
        session.permanent = True
        session["user_id"] = int(utilisateur["id"])
        session["_csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("dashboard"))

    return render_template("auth/connexion.html")


@app.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("connexion"))


@app.route("/module/<module>")
def page_module(module):
    configuration = MODULES.get(module)

    if configuration is None:
        return render_template("erreurs/404.html"), 404

    contexte = {
        "titre": configuration["titre"],
        "description": f"Consultez et gérez les informations de {configuration['titre'].lower()} de l'établissement.",
    }

    table_name = TABLES_BY_MODULE.get(module)
    variable = configuration["variable"]

    if variable and table_name:
        donnees, message = charger_module(module, g.current_user["ecole_id"])
        contexte[variable] = donnees
        contexte["db_message"] = message
    if module == "repartitions":
        contexte["regles_financieres"] = charger_regles_financieres(g.current_user["ecole_id"])

    if module == "rapports":
        connexion = obtenir_connexion()
        if connexion is None:
            contexte["synthese"] = {cle: "—" for cle in (
                "ecoles", "annees_scolaires", "classes", "eleves", "enseignants",
                "paiements_eleves", "presences", "remunerations",
            )}
            contexte["db_message"] = "La connexion MySQL est indisponible pour calculer les rapports."
        else:
            try:
                curseur = connexion.cursor(dictionary=True)
                curseur.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM ecoles WHERE id = %s) AS ecoles,
                      (SELECT COUNT(*) FROM annees_scolaires WHERE ecole_id = %s) AS annees_scolaires,
                      (SELECT COUNT(*) FROM classes WHERE ecole_id = %s) AS classes,
                      (SELECT COUNT(*) FROM inscriptions i
                       INNER JOIN eleves e ON e.id = i.eleve_id
                       WHERE e.ecole_id = %s AND i.statut = 'inscrit') AS eleves,
                      (SELECT COUNT(*) FROM enseignants WHERE ecole_id = %s) AS enseignants,
                      (SELECT COUNT(*) FROM paiements_eleves p
                       INNER JOIN inscriptions i ON i.id = p.inscription_id
                       INNER JOIN eleves e ON e.id = i.eleve_id
                       WHERE e.ecole_id = %s AND p.statut = 'valide') AS paiements_eleves,
                      (SELECT COUNT(*) FROM presences_enseignants p
                       INNER JOIN enseignants e ON e.id = p.enseignant_id
                       WHERE e.ecole_id = %s) AS presences,
                      (SELECT COUNT(*) FROM remunerations_enseignants r
                       INNER JOIN enseignants e ON e.id = r.enseignant_id
                       WHERE e.ecole_id = %s) AS remunerations
                    """,
                    (g.current_user["ecole_id"],) * 8,
                )
                contexte["synthese"] = cast(dict[str, Any] | None, curseur.fetchone()) or {}
            except Exception:
                app.logger.exception("Calcul des rapports impossible.")
                contexte["synthese"] = {cle: "—" for cle in (
                    "ecoles", "annees_scolaires", "classes", "eleves", "enseignants",
                    "paiements_eleves", "presences", "remunerations",
                )}
                contexte["db_message"] = "Les rapports n'ont pas pu être calculés."
            finally:
                connexion.close()

    return render_template(configuration["template"], **contexte)


@app.route("/ecoles/nouvelle", methods=["GET", "POST"])
def formulaire_ecole():
    if request.method == "GET":
        return render_template("ecoles/formulaire.html")

    nom = (request.form.get("nom") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    telephone = (request.form.get("telephone") or "").strip() or None
    adresse = (request.form.get("adresse") or "").strip() or None
    directeur = (request.form.get("directeur") or "").strip() or None
    devise = (request.form.get("devise") or "USD").strip()
    if not nom or len(nom) > 150 or len(email or "") > 150 or len(telephone or "") > 30:
        flash("Le nom de l'école est obligatoire; vérifiez aussi les limites de contact.", "danger")
        return render_template("ecoles/formulaire.html"), 400
    if email:
        from email.utils import parseaddr
        if parseaddr(email)[1] != email or "@" not in email:
            flash("L'adresse e-mail n'est pas valide.", "danger")
            return render_template("ecoles/formulaire.html"), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("ecoles/formulaire.html"), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor()
        curseur.execute(
            "INSERT INTO ecoles (nom, adresse, telephone, email, directeur, devise, statut) VALUES (%s, %s, %s, %s, %s, %s, 'active')",
            (nom, adresse, telephone, email, directeur, devise),
        )
        ecole_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "création", "ecoles", ecole_id,
             f"Création de l'école {nom}.", request.remote_addr),
        )
        connexion.commit()
        flash("L'école a été enregistrée.", "success")
        return redirect(url_for("page_module", module="ecoles"))
    except Error:
        connexion.rollback()
        app.logger.exception("Création de l'école impossible.")
        flash("L'école n'a pas été enregistrée.", "danger")
        return render_template("ecoles/formulaire.html"), 400
    finally:
        connexion.close()


@app.route("/ecoles/<int:ecole_id>/statut", methods=["POST"])
def changer_statut_ecole(ecole_id):
    statut = (request.form.get("statut") or "").strip()
    if statut not in {"active", "inactive"}:
        abort(400)
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        connexion.start_transaction()
        curseur = connexion.cursor()
        curseur.execute("UPDATE ecoles SET statut = %s WHERE id = %s", (statut, ecole_id))
        if curseur.rowcount != 1:
            connexion.rollback()
            abort(404)
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "modification", "ecoles", ecole_id,
             f"Statut de l'école modifié en {statut}.", request.remote_addr),
        )
        connexion.commit()
        flash("Le statut de l'école a été modifié.", "success")
    except Error:
        connexion.rollback()
        app.logger.exception("Changement de statut de l'école impossible.")
        flash("Le statut n'a pas été modifié.", "danger")
    finally:
        connexion.close()
    return redirect(url_for("page_module", module="ecoles"))


def charger_annees_ecole(ecole_id: int) -> list[dict[str, Any]]:
    connexion = obtenir_connexion()
    if connexion is None:
        return []
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, libelle, statut FROM annees_scolaires WHERE ecole_id = %s ORDER BY date_debut DESC",
            (ecole_id,),
        )
        return cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Chargement des années scolaires impossible.")
        return []
    finally:
        connexion.close()


def charger_regles_financieres(ecole_id: int) -> list[dict[str, Any]]:
    connexion = obtenir_connexion()
    if connexion is None:
        return []
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT r.*, a.libelle AS annee_scolaire
            FROM regles_financieres r
            INNER JOIN annees_scolaires a ON a.id = r.annee_scolaire_id
            WHERE r.ecole_id = %s
            ORDER BY r.date_effet DESC, r.id DESC
            LIMIT 100
            """,
            (ecole_id,),
        )
        return cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Chargement des règles financières impossible.")
        return []
    finally:
        connexion.close()


@app.route("/annees-scolaires/nouveau", methods=["GET", "POST"])
def formulaire_annee_scolaire():
    if request.method == "POST":
        libelle = (request.form.get("libelle") or "").strip()
        date_debut = (request.form.get("date_debut") or "").strip()
        date_fin = (request.form.get("date_fin") or "").strip()
        statut = (request.form.get("statut") or "en_preparation").strip()
        try:
            debut = date.fromisoformat(date_debut)
            fin = date.fromisoformat(date_fin)
        except ValueError:
            flash("Saisissez des dates de début et de fin valides.", "danger")
            return render_template("annees_scolaires/formulaire.html"), 400

        if not libelle or len(libelle) > 20 or fin <= debut:
            flash("Le libellé est obligatoire et la date de fin doit suivre la date de début.", "danger")
            return render_template("annees_scolaires/formulaire.html"), 400
        if statut not in {"en_preparation", "en_cours"}:
            flash("Le statut initial doit être en préparation ou en cours.", "danger")
            return render_template("annees_scolaires/formulaire.html"), 400

        connexion = obtenir_connexion()
        if connexion is None:
            flash("La connexion MySQL est indisponible.", "danger")
            return render_template("annees_scolaires/formulaire.html"), 503
        try:
            curseur = connexion.cursor()
            curseur.execute(
                """
                INSERT INTO annees_scolaires (ecole_id, libelle, date_debut, date_fin, statut)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (g.current_user["ecole_id"], libelle, debut, fin, statut),
            )
            annee_id = curseur.lastrowid
            curseur.execute(
                """
                INSERT INTO journal_activites
                    (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (g.current_user["id"], "création", "annees_scolaires", annee_id,
                 f"Création de l'année scolaire {libelle}.", request.remote_addr),
            )
            connexion.commit()
            flash("L'année scolaire a été enregistrée.", "success")
            return redirect(url_for("page_module", module="annees_scolaires"))
        except Error as erreur:
            connexion.rollback()
            app.logger.exception("Création de l'année scolaire impossible.")
            if getattr(erreur, "errno", None) == 1062:
                flash("Ce libellé existe déjà pour l'établissement.", "danger")
            else:
                flash("L'année scolaire n'a pas pu être enregistrée.", "danger")
            return render_template("annees_scolaires/formulaire.html"), 400
        finally:
            connexion.close()

    return render_template("annees_scolaires/formulaire.html")


@app.route("/annees-scolaires/<int:annee_id>/statut", methods=["POST"])
def changer_statut_annee(annee_id):
    statut = (request.form.get("statut") or "").strip()
    if statut not in {"en_preparation", "en_cours", "terminee"}:
        abort(400)
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, statut, libelle FROM annees_scolaires WHERE id = %s AND ecole_id = %s LIMIT 1 FOR UPDATE",
            (annee_id, g.current_user["ecole_id"]),
        )
        annee = cast(dict[str, Any] | None, curseur.fetchone())
        if not annee:
            connexion.rollback()
            abort(404)
        if statut == "en_cours":
            curseur.execute(
                "SELECT id FROM annees_scolaires WHERE ecole_id = %s AND statut = 'en_cours' AND id <> %s LIMIT 1 FOR UPDATE",
                (g.current_user["ecole_id"], annee_id),
            )
            if curseur.fetchone():
                connexion.rollback()
                flash("Clôturez d'abord l'année actuellement en cours.", "danger")
                return redirect(url_for("page_module", module="annees_scolaires")), 409
        curseur.execute("UPDATE annees_scolaires SET statut = %s WHERE id = %s", (statut, annee_id))
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "modification", "annees_scolaires", annee_id,
             f"Statut de l'année {annee['libelle']} modifié en {statut}.", request.remote_addr),
        )
        connexion.commit()
        flash("Le statut de l'année scolaire a été modifié.", "success")
    except Error:
        connexion.rollback()
        app.logger.exception("Modification du statut d'année scolaire impossible.")
        flash("Le statut de l'année n'a pas été modifié.", "danger")
    finally:
        connexion.close()
    return redirect(url_for("page_module", module="annees_scolaires"))


@app.route("/classes/nouveau", methods=["GET", "POST"])
def formulaire_classe():
    annees = charger_annees_ecole(g.current_user["ecole_id"])
    niveaux_autorises = {
        "1ere_primaire", "2eme_primaire", "3eme_primaire",
        "4eme_primaire", "5eme_primaire", "6eme_primaire", "autre",
    }
    if request.method == "POST":
        nom = (request.form.get("nom") or "").strip()
        niveau = (request.form.get("niveau") or "").strip()
        annee_id = request.form.get("annee_scolaire_id", type=int)
        capacite = request.form.get("capacite", type=int, default=50)
        if not nom or len(nom) > 100 or niveau not in niveaux_autorises:
            flash("Saisissez un nom de classe et un niveau valides.", "danger")
            return render_template("classes/formulaire.html", annees=annees), 400
        if not annee_id or capacite < 1:
            flash("Sélectionnez une année scolaire et une capacité positive.", "danger")
            return render_template("classes/formulaire.html", annees=annees), 400

        connexion = obtenir_connexion()
        if connexion is None:
            flash("La connexion MySQL est indisponible.", "danger")
            return render_template("classes/formulaire.html", annees=annees), 503
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT id, statut FROM annees_scolaires WHERE id = %s AND ecole_id = %s LIMIT 1",
                (annee_id, g.current_user["ecole_id"]),
            )
            annee = cast(dict[str, Any] | None, curseur.fetchone())
            if not annee or annee["statut"] == "terminee":
                connexion.rollback()
                flash("L'année sélectionnée n'est pas disponible pour votre établissement.", "danger")
                return render_template("classes/formulaire.html", annees=annees), 400

            curseur.execute(
                """
                INSERT INTO classes (ecole_id, annee_scolaire_id, nom, niveau, capacite, statut)
                VALUES (%s, %s, %s, %s, %s, 'active')
                """,
                (g.current_user["ecole_id"], annee_id, nom, niveau, capacite),
            )
            classe_id = curseur.lastrowid
            curseur.execute(
                """
                INSERT INTO journal_activites
                    (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (g.current_user["id"], "création", "classes", classe_id,
                 f"Création de la classe {nom}.", request.remote_addr),
            )
            connexion.commit()
            flash("La classe a été enregistrée.", "success")
            return redirect(url_for("page_module", module="classes"))
        except Error as erreur:
            connexion.rollback()
            app.logger.exception("Création de la classe impossible.")
            if getattr(erreur, "errno", None) == 1062:
                flash("Ce nom de classe existe déjà pour cette année.", "danger")
            else:
                flash("La classe n'a pas pu être enregistrée.", "danger")
            return render_template("classes/formulaire.html", annees=annees), 400
        finally:
            connexion.close()

    return render_template("classes/formulaire.html", annees=annees)


@app.route("/frais/nouveau", methods=["GET", "POST"])
def formulaire_frais():
    annees = charger_annees_ecole(g.current_user["ecole_id"])
    contexte = {"annees": annees}
    if request.method == "GET":
        return render_template("finances/formulaire_frais.html", **contexte)

    nom = (request.form.get("nom") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    annee_id = request.form.get("annee_scolaire_id", type=int)
    try:
        montant = Decimal((request.form.get("montant") or "").strip().replace(",", "."))
    except InvalidOperation:
        montant = Decimal("-1")
    date_limite_brute = (request.form.get("date_limite") or "").strip()
    try:
        date_limite = date.fromisoformat(date_limite_brute) if date_limite_brute else None
    except ValueError:
        date_limite = False

    if not nom or len(nom) > 100 or not annee_id:
        flash("Le nom du frais et l'année scolaire sont obligatoires.", "danger")
        return render_template("finances/formulaire_frais.html", **contexte), 400
    if not montant.is_finite() or montant < 0 or montant > Decimal("9999999999.99"):
        flash("Saisissez un montant valide et positif ou nul.", "danger")
        return render_template("finances/formulaire_frais.html", **contexte), 400
    if date_limite is False:
        flash("La date limite n'est pas valide.", "danger")
        return render_template("finances/formulaire_frais.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("finances/formulaire_frais.html", **contexte), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, statut FROM annees_scolaires WHERE id = %s AND ecole_id = %s LIMIT 1 FOR UPDATE",
            (annee_id, g.current_user["ecole_id"]),
        )
        annee = cast(dict[str, Any] | None, curseur.fetchone())
        if not annee or annee["statut"] == "terminee":
            connexion.rollback()
            flash("L'année scolaire est introuvable ou clôturée.", "danger")
            return render_template("finances/formulaire_frais.html", **contexte), 400
        curseur.execute(
            """
            INSERT INTO types_frais
                (ecole_id, annee_scolaire_id, nom, description, montant, obligatoire, date_limite, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'actif')
            """,
            (g.current_user["ecole_id"], annee_id, nom, description, montant.quantize(Decimal("0.01")),
             1 if request.form.get("obligatoire") == "on" else 0, date_limite),
        )
        frais_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "création", "types_frais", frais_id,
             f"Création du type de frais {nom}.", request.remote_addr),
        )
        connexion.commit()
        flash("Le type de frais a été enregistré.", "success")
        return redirect(url_for("page_module", module="frais"))
    except Error as erreur:
        connexion.rollback()
        app.logger.exception("Création du type de frais impossible.")
        flash("Le type de frais n'a pas été enregistré. Vérifiez l'année et les données.", "danger")
        return render_template("finances/formulaire_frais.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/regles-financieres/nouveau", methods=["GET", "POST"])
def formulaire_regle_financiere():
    annees = charger_annees_ecole(g.current_user["ecole_id"])
    contexte = {"annees": annees}
    if request.method == "GET":
        return render_template("finances/formulaire_regle.html", **contexte)

    nom = (request.form.get("nom") or "").strip()
    annee_id = request.form.get("annee_scolaire_id", type=int)
    try:
        pourcentages = tuple(Decimal((request.form.get(champ) or "").strip()) for champ in (
            "pourcentage_hierarchie", "pourcentage_prime_enseignants",
            "pourcentage_promoteur", "pourcentage_fonctionnement",
        ))
        date_effet = date.fromisoformat(request.form.get("date_effet", ""))
        date_fin_brute = (request.form.get("date_fin") or "").strip()
        date_fin = date.fromisoformat(date_fin_brute) if date_fin_brute else None
    except (InvalidOperation, ValueError):
        flash("Vérifiez les pourcentages et les dates de validité.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400

    if not nom or len(nom) > 100 or not annee_id:
        flash("Le nom de la règle et l'année scolaire sont obligatoires.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400
    if any(not valeur.is_finite() or valeur < 0 or valeur > 100 for valeur in pourcentages):
        flash("Chaque pourcentage doit être compris entre 0 et 100.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400
    if sum(pourcentages) != Decimal("100.00"):
        flash("La somme des quatre pourcentages doit être exactement égale à 100 %.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400
    if date_fin is not None and date_fin < date_effet:
        flash("La date de fin ne peut pas précéder la date d'effet.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, statut FROM annees_scolaires WHERE id = %s AND ecole_id = %s LIMIT 1 FOR UPDATE",
            (annee_id, g.current_user["ecole_id"]),
        )
        annee = cast(dict[str, Any] | None, curseur.fetchone())
        if not annee or annee["statut"] == "terminee":
            connexion.rollback()
            flash("L'année sélectionnée est introuvable ou clôturée.", "danger")
            return render_template("finances/formulaire_regle.html", **contexte), 400

        curseur.execute(
            """
            SELECT id FROM regles_financieres
            WHERE ecole_id = %s AND annee_scolaire_id = %s AND actif = 1
              AND (%s IS NULL OR date_effet <= %s)
              AND (date_fin IS NULL OR date_fin >= %s)
            LIMIT 1 FOR UPDATE
            """,
            (g.current_user["ecole_id"], annee_id, date_fin, date_fin or date_effet, date_effet),
        )
        chevauchement = curseur.fetchone()
        if chevauchement:
            connexion.rollback()
            flash("Une règle active existe déjà sur une partie de cette période.", "danger")
            return render_template("finances/formulaire_regle.html", **contexte), 409

        curseur.execute(
            """
            INSERT INTO regles_financieres
                (ecole_id, annee_scolaire_id, nom, pourcentage_hierarchie,
                 pourcentage_prime_enseignants, pourcentage_promoteur,
                 pourcentage_fonctionnement, date_effet, date_fin, actif, cree_par)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
            """,
            (g.current_user["ecole_id"], annee_id, nom, *pourcentages,
             date_effet, date_fin, g.current_user["id"]),
        )
        regle_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "création", "regles_financieres", regle_id,
             f"Création de la règle financière {nom}.", request.remote_addr),
        )
        connexion.commit()
        flash("La règle financière a été enregistrée.", "success")
        return redirect(url_for("page_module", module="repartitions"))
    except Error:
        connexion.rollback()
        app.logger.exception("Création de la règle financière impossible.")
        flash("La règle n'a pas été enregistrée.", "danger")
        return render_template("finances/formulaire_regle.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/presences/nouvelle", methods=["GET", "POST"])
def formulaire_presence():
    annees = [annee for annee in charger_annees_ecole(g.current_user["ecole_id"]) if annee["statut"] == "en_cours"]
    enseignants = []
    connexion = obtenir_connexion()
    if connexion is not None:
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT id, matricule, CONCAT_WS(' ', nom, postnom, prenom) AS nom_complet FROM enseignants WHERE ecole_id = %s AND statut = 'actif' ORDER BY nom, prenom",
                (g.current_user["ecole_id"],),
            )
            enseignants = cast(list[dict[str, Any]], curseur.fetchall())
        except Exception:
            app.logger.exception("Chargement des enseignants pour la présence impossible.")
        finally:
            connexion.close()

    contexte = {"annees": annees, "enseignants": enseignants}
    if request.method == "GET":
        return render_template("presences/formulaire.html", **contexte)

    enseignant_id = request.form.get("enseignant_id", type=int)
    annee_id = request.form.get("annee_scolaire_id", type=int)
    date_presence = (request.form.get("date_presence") or "").strip()
    statut = (request.form.get("statut") or "").strip()
    heure_arrivee = (request.form.get("heure_arrivee") or "").strip() or None
    heure_depart = (request.form.get("heure_depart") or "").strip() or None
    justification = (request.form.get("justification") or "").strip() or None

    statuts = {"present", "absent", "retard", "permission", "maladie"}
    try:
        jour = date.fromisoformat(date_presence)
    except ValueError:
        jour = None
    if not enseignant_id or not annee_id or jour is None or statut not in statuts:
        flash("Sélectionnez un enseignant, une année en cours, une date et un statut valides.", "danger")
        return render_template("presences/formulaire.html", **contexte), 400
    if (heure_arrivee and len(heure_arrivee) != 8) or (heure_depart and len(heure_depart) != 8):
        flash("Les heures doivent être saisies au format HH:MM.", "danger")
        return render_template("presences/formulaire.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("presences/formulaire.html", **contexte), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id FROM enseignants WHERE id = %s AND ecole_id = %s AND statut = 'actif' LIMIT 1 FOR UPDATE",
            (enseignant_id, g.current_user["ecole_id"]),
        )
        enseignant = curseur.fetchone()
        curseur.execute(
            "SELECT id FROM annees_scolaires WHERE id = %s AND ecole_id = %s AND statut = 'en_cours' LIMIT 1 FOR UPDATE",
            (annee_id, g.current_user["ecole_id"]),
        )
        annee = curseur.fetchone()
        if not enseignant or not annee:
            connexion.rollback()
            flash("L'enseignant ou l'année scolaire n'est pas disponible pour cet établissement.", "danger")
            return render_template("presences/formulaire.html", **contexte), 400

        curseur.execute(
            "SELECT id FROM presences_enseignants WHERE enseignant_id = %s AND date_presence = %s LIMIT 1 FOR UPDATE",
            (enseignant_id, jour),
        )
        if curseur.fetchone():
            connexion.rollback()
            flash("Une présence est déjà enregistrée pour cet enseignant à cette date.", "danger")
            return render_template("presences/formulaire.html", **contexte), 409

        curseur.execute(
            """
            INSERT INTO presences_enseignants
                (enseignant_id, annee_scolaire_id, date_presence, statut,
                 heure_arrivee, heure_depart, justification, enregistre_par)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (enseignant_id, annee_id, jour, statut, heure_arrivee, heure_depart,
             justification, g.current_user["id"]),
        )
        presence_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "création", "presences_enseignants", presence_id,
             f"Présence enregistrée pour le {jour.isoformat()}.", request.remote_addr),
        )
        connexion.commit()
        flash("La présence a été enregistrée.", "success")
        return redirect(url_for("page_module", module="presences"))
    except Error:
        connexion.rollback()
        app.logger.exception("Enregistrement de présence impossible.")
        flash("La présence n'a pas été enregistrée.", "danger")
        return render_template("presences/formulaire.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/notifications/nouvelle", methods=["GET", "POST"])
def formulaire_notification():
    connexion = obtenir_connexion()
    enseignants = []
    if connexion is not None:
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT id, utilisateur_id, matricule, CONCAT_WS(' ', nom, postnom, prenom) AS nom_complet FROM enseignants WHERE ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NOT NULL ORDER BY nom, prenom",
                (g.current_user["ecole_id"],),
            )
            enseignants = cast(list[dict[str, Any]], curseur.fetchall())
        except Exception:
            app.logger.exception("Chargement des destinataires de notification impossible.")
        finally:
            connexion.close()

    contexte = {"enseignants": enseignants}
    if request.method == "GET":
        return render_template("notifications/formulaire.html", **contexte)

    titre = (request.form.get("titre") or "").strip()
    message = (request.form.get("message") or "").strip()
    type_notification = (request.form.get("type") or "information").strip()
    destinataire = (request.form.get("destinataire") or "").strip()
    if not titre or len(titre) > 180 or not message or type_notification not in {
        "information", "alerte", "paiement", "rappel"
    }:
        flash("Complétez le titre, le message et un type valide.", "danger")
        return render_template("notifications/formulaire.html", **contexte), 400
    if destinataire != "tous" and not destinataire.isdigit():
        flash("Sélectionnez un enseignant valide ou l'envoi à tous.", "danger")
        return render_template("notifications/formulaire.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("notifications/formulaire.html", **contexte), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id FROM ecoles WHERE id = %s AND statut = 'active' LIMIT 1 FOR UPDATE",
            (g.current_user["ecole_id"],),
        )
        if not curseur.fetchone():
            connexion.rollback()
            flash("L'établissement du compte n'est pas actif.", "danger")
            return render_template("notifications/formulaire.html", **contexte), 400

        if destinataire == "tous":
            curseur.execute(
                "SELECT utilisateur_id FROM enseignants WHERE ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NOT NULL FOR UPDATE",
                (g.current_user["ecole_id"],),
            )
            utilisateur_ids = [ligne["utilisateur_id"] for ligne in cast(list[dict[str, Any]], curseur.fetchall())]
        else:
            curseur.execute(
                "SELECT utilisateur_id FROM enseignants WHERE id = %s AND ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NOT NULL LIMIT 1 FOR UPDATE",
                (int(destinataire), g.current_user["ecole_id"]),
            )
            enseignant = cast(dict[str, Any] | None, curseur.fetchone())
            utilisateur_ids = [enseignant["utilisateur_id"]] if enseignant else []
        if not utilisateur_ids:
            connexion.rollback()
            flash("Aucun compte enseignant destinataire valide n'a été trouvé.", "danger")
            return render_template("notifications/formulaire.html", **contexte), 400

        curseur.execute(
            "INSERT INTO notifications (ecole_id, titre, message, type, cree_par) VALUES (%s, %s, %s, %s, %s)",
            (g.current_user["ecole_id"], titre, message, type_notification, g.current_user["id"]),
        )
        notification_id = curseur.lastrowid
        curseur.executemany(
            "INSERT INTO destinataires_notifications (notification_id, utilisateur_id, lu) VALUES (%s, %s, 0)",
            [(notification_id, utilisateur_id) for utilisateur_id in utilisateur_ids],
        )
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "envoi", "notifications", notification_id,
             f"Notification envoyée à {len(utilisateur_ids)} enseignant(s).", request.remote_addr),
        )
        connexion.commit()
        flash("La notification a été envoyée.", "success")
        return redirect(url_for("page_module", module="notifications"))
    except Error:
        connexion.rollback()
        app.logger.exception("Envoi de notification impossible.")
        flash("La notification n'a pas été envoyée.", "danger")
        return render_template("notifications/formulaire.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/espace-enseignant")
def espace_enseignant():
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT id, matricule, nom, postnom, prenom, sexe, telephone, email,
                   adresse, specialite, date_engagement, statut
            FROM enseignants
            WHERE utilisateur_id = %s AND ecole_id = %s
            LIMIT 1
            """,
            (g.current_user["id"], g.current_user["ecole_id"]),
        )
        enseignant = cast(dict[str, Any] | None, curseur.fetchone())
        affectations: list[dict[str, Any]] = []
        eleves_classe: list[dict[str, Any]] = []
        presences: list[dict[str, Any]] = []
        remunerations: list[dict[str, Any]] = []
        paiements: list[dict[str, Any]] = []
        if enseignant:
            curseur.execute(
                """
                SELECT af.fonction, af.date_debut, af.date_fin, af.statut,
                       c.nom AS classe, c.niveau, a.libelle AS annee_scolaire
                FROM affectations_enseignants af
                INNER JOIN classes c ON c.id = af.classe_id
                INNER JOIN annees_scolaires a ON a.id = af.annee_scolaire_id
                WHERE af.enseignant_id = %s AND a.ecole_id = %s
                ORDER BY af.date_debut DESC, af.id DESC
                LIMIT 100
                """,
                (enseignant["id"], g.current_user["ecole_id"]),
            )
            affectations = cast(list[dict[str, Any]], curseur.fetchall())
            curseur.execute(
                """
                SELECT DISTINCT el.id, el.matricule,
                       CONCAT_WS(' ', el.nom, el.postnom, el.prenom) AS nom_complet,
                       el.sexe, c.nom AS classe, a.libelle AS annee_scolaire
                FROM affectations_enseignants af
                INNER JOIN classes c ON c.id = af.classe_id
                INNER JOIN annees_scolaires a ON a.id = af.annee_scolaire_id
                INNER JOIN inscriptions i ON i.classe_id = c.id
                    AND i.annee_scolaire_id = a.id AND i.statut = 'inscrit'
                INNER JOIN eleves el ON el.id = i.eleve_id AND el.ecole_id = a.ecole_id
                WHERE af.enseignant_id = %s AND a.ecole_id = %s
                  AND af.statut = 'active' AND af.date_fin IS NULL
                  AND a.statut = 'en_cours' AND el.statut = 'actif'
                ORDER BY c.nom, el.nom, el.postnom, el.prenom
                LIMIT 300
                """,
                (enseignant["id"], g.current_user["ecole_id"]),
            )
            eleves_classe = cast(list[dict[str, Any]], curseur.fetchall())
            curseur.execute(
                """
                SELECT date_presence, statut, heure_arrivee, heure_depart, justification
                FROM presences_enseignants
                WHERE enseignant_id = %s
                ORDER BY date_presence DESC, id DESC LIMIT 100
                """,
                (enseignant["id"],),
            )
            presences = cast(list[dict[str, Any]], curseur.fetchall())
            curseur.execute(
                """
                SELECT id, mois, annee, total_jours_prevus, total_jours_presents,
                       montant_calcule, montant_valide, statut
                FROM remunerations_enseignants
                WHERE enseignant_id = %s
                ORDER BY annee DESC, mois DESC LIMIT 100
                """,
                (enseignant["id"],),
            )
            remunerations = cast(list[dict[str, Any]], curseur.fetchall())
            curseur.execute(
                """
                SELECT p.numero_recu, p.montant_paye, p.mode_paiement,
                       p.reference_paiement, p.date_paiement, p.statut, r.mois, r.annee
                FROM paiements_enseignants p
                INNER JOIN remunerations_enseignants r ON r.id = p.remuneration_id
                WHERE r.enseignant_id = %s AND p.statut = 'valide'
                ORDER BY p.date_paiement DESC LIMIT 100
                """,
                (enseignant["id"],),
            )
            paiements = cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Chargement de l'espace enseignant impossible.")
        abort(500)
    finally:
        connexion.close()
    return render_template(
        "enseignants/espace.html", enseignant=enseignant, affectations=affectations,
        eleves_classe=eleves_classe, presences=presences,
        remunerations=remunerations, paiements=paiements,
    )


@app.route("/mes-notifications")
def notifications_enseignant():
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT n.id, n.titre, n.message, n.type, n.date_creation,
                   d.lu, d.date_lecture, d.date_envoi
            FROM destinataires_notifications d
            INNER JOIN notifications n ON n.id = d.notification_id
            WHERE d.utilisateur_id = %s AND n.ecole_id = %s
            ORDER BY n.date_creation DESC LIMIT 100
            """,
            (g.current_user["id"], g.current_user["ecole_id"]),
        )
        notifications = cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Chargement des notifications de l'enseignant impossible.")
        notifications = []
    finally:
        connexion.close()
    return render_template("notifications/mes_notifications.html", notifications=notifications)


@app.route("/mes-notifications/<int:notification_id>/lue", methods=["POST"])
def marquer_notification_lue(notification_id):
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor()
        curseur.execute(
            """
            UPDATE destinataires_notifications d
            INNER JOIN notifications n ON n.id = d.notification_id
            SET d.lu = 1, d.date_lecture = NOW()
            WHERE d.notification_id = %s AND d.utilisateur_id = %s AND n.ecole_id = %s
            """,
            (notification_id, g.current_user["id"], g.current_user["ecole_id"]),
        )
        if curseur.rowcount != 1:
            connexion.rollback()
            abort(404)
        connexion.commit()
    except Error:
        connexion.rollback()
        app.logger.exception("Marquage de notification comme lue impossible.")
        abort(500)
    finally:
        connexion.close()
    return redirect(url_for("notifications_enseignant"))


@app.route("/remunerations/<int:remuneration_id>/valider", methods=["POST"])
def valider_remuneration(remuneration_id):
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT r.id, r.statut, r.montant_calcule, r.montant_valide
            FROM remunerations_enseignants r
            INNER JOIN enseignants e ON e.id = r.enseignant_id
            WHERE r.id = %s AND e.ecole_id = %s
            LIMIT 1 FOR UPDATE
            """,
            (remuneration_id, g.current_user["ecole_id"]),
        )
        remuneration = cast(dict[str, Any] | None, curseur.fetchone())
        if not remuneration:
            connexion.rollback()
            abort(404)
        if remuneration["statut"] != "a_valider":
            connexion.rollback()
            flash("Seule une rémunération en attente peut être validée.", "danger")
            return redirect(url_for("page_module", module="remunerations")), 409

        montant_calcule = Decimal(str(remuneration["montant_calcule"] or 0))
        montant_valide = Decimal(str(remuneration["montant_valide"] or 0))
        if montant_calcule <= 0 or montant_valide <= 0 or montant_valide > montant_calcule:
            connexion.rollback()
            flash("Le montant calculé ou validé est incohérent. Aucun paiement n'a été effectué.", "danger")
            return redirect(url_for("page_module", module="remunerations")), 409

        curseur.execute(
            "UPDATE remunerations_enseignants SET statut = 'validee', valide_par = %s, date_validation = NOW() WHERE id = %s",
            (g.current_user["id"], remuneration_id),
        )
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "validation", "remunerations_enseignants", remuneration_id,
             "Rémunération validée par un administrateur; aucun paiement n'a été effectué.", request.remote_addr),
        )
        connexion.commit()
        flash("La rémunération a été validée; elle n'est pas encore payée.", "success")
    except Error:
        connexion.rollback()
        app.logger.exception("Validation de rémunération impossible.")
        flash("La rémunération n'a pas pu être validée.", "danger")
    finally:
        connexion.close()
    return redirect(url_for("page_module", module="remunerations"))


@app.route("/remunerations/<int:remuneration_id>/payer", methods=["POST"])
def payer_remuneration(remuneration_id):
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    mode_paiement = (request.form.get("mode_paiement") or "").strip()
    reference = (request.form.get("reference_paiement") or "").strip() or None
    commentaire = (request.form.get("commentaire") or "").strip() or None
    if mode_paiement not in {"especes", "mobile_money", "banque", "autre"} or len(reference or "") > 100:
        flash("Sélectionnez un mode de paiement valide et une référence de 100 caractères maximum.", "danger")
        return redirect(url_for("page_module", module="remunerations")), 400
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT r.id, r.statut, r.montant_valide, e.ecole_id
            FROM remunerations_enseignants r
            INNER JOIN enseignants e ON e.id = r.enseignant_id
            WHERE r.id = %s AND e.ecole_id = %s
            LIMIT 1 FOR UPDATE
            """,
            (remuneration_id, g.current_user["ecole_id"]),
        )
        remuneration = cast(dict[str, Any] | None, curseur.fetchone())
        if not remuneration:
            connexion.rollback()
            abort(404)
        if remuneration["statut"] != "validee":
            connexion.rollback()
            flash("Seule une rémunération validée par un administrateur peut être payée.", "danger")
            return redirect(url_for("page_module", module="remunerations")), 409
        montant = Decimal(str(remuneration["montant_valide"] or 0)).quantize(Decimal("0.01"))
        if montant <= 0:
            connexion.rollback()
            flash("Le montant validé doit être positif.", "danger")
            return redirect(url_for("page_module", module="remunerations")), 409
        curseur.execute(
            "SELECT id FROM paiements_enseignants WHERE remuneration_id = %s AND statut = 'valide' LIMIT 1 FOR UPDATE",
            (remuneration_id,),
        )
        if curseur.fetchone():
            connexion.rollback()
            flash("Cette rémunération possède déjà un paiement valide.", "danger")
            return redirect(url_for("page_module", module="remunerations")), 409

        numero_recu = f"PAY-ENS-{datetime.now():%Y%m%d}-{secrets.token_hex(4).upper()}"
        curseur.execute(
            """
            INSERT INTO paiements_enseignants
                (remuneration_id, numero_recu, montant_paye, mode_paiement,
                 reference_paiement, commentaire, paye_par, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'valide')
            """,
            (remuneration_id, numero_recu, montant, mode_paiement, reference,
             commentaire, g.current_user["id"]),
        )
        paiement_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "paiement", "paiements_enseignants", paiement_id,
             f"Rémunération payée, reçu {numero_recu}.", request.remote_addr),
        )
        connexion.commit()
        flash(f"Le paiement réel a été enregistré (reçu {numero_recu}).", "success")
    except Error:
        connexion.rollback()
        app.logger.exception("Paiement de rémunération impossible.")
        flash("Le paiement de la rémunération n'a pas été enregistré.", "danger")
    finally:
        connexion.close()
    return redirect(url_for("page_module", module="remunerations"))


@app.route("/eleves/nouveau", methods=["GET", "POST"])
def formulaire_eleve():
    classes, message_classes = charger_classes_inscription(g.current_user["ecole_id"])
    if request.method == "POST":
        nom = (request.form.get("nom") or "").strip()
        sexe = (request.form.get("sexe") or "").strip()
        classe_id = request.form.get("classe_id", type=int)

        if not nom:
            flash("Le nom de l'élève est obligatoire pour enregistrer le dossier.", "danger")
            return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes)

        if sexe not in {"M", "F", "autre"}:
            flash("Sélectionnez une valeur valide pour le sexe de l'élève.", "danger")
            return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes)
        if not classe_id:
            flash("Sélectionnez une classe de l'année scolaire en cours.", "danger")
            return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes)

        connexion = obtenir_connexion()
        if connexion is None:
            flash("La connexion MySQL est indisponible pour enregistrer l'élève.", "danger")
            return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes), 503

        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                """
                SELECT c.id, c.annee_scolaire_id
                FROM classes c
                INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
                WHERE c.id = %s AND c.ecole_id = %s
                  AND c.statut = 'active' AND a.statut = 'en_cours'
                LIMIT 1
                """,
                (classe_id, g.current_user["ecole_id"]),
            )
            classe = cast(dict[str, Any] | None, curseur.fetchone())
            if classe is None:
                connexion.rollback()
                flash("La classe sélectionnée n'est pas disponible pour votre établissement.", "danger")
                return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes), 400

            date_naissance = (request.form.get("date_naissance") or "").strip() or None
            donnees = {
                "ecole_id": g.current_user["ecole_id"],
                "matricule": f"EL-{secrets.token_hex(5).upper()}",
                "nom": nom,
                "postnom": (request.form.get("postnom") or "").strip() or None,
                "prenom": (request.form.get("prenom") or "").strip() or None,
                "sexe": sexe,
                "date_naissance": date_naissance,
                "lieu_naissance": (request.form.get("lieu_naissance") or "").strip() or None,
                "nom_tuteur": (request.form.get("nom_tuteur") or "").strip() or None,
                "telephone_tuteur": (request.form.get("telephone_tuteur") or "").strip() or None,
                "adresse": (request.form.get("adresse") or "").strip() or None,
                "statut": "actif",
            }
            valeurs = tuple(donnees.values())
            placeholders = ", ".join(["%s"] * len(donnees))
            curseur.execute(
                f"INSERT INTO eleves ({', '.join(donnees)}) VALUES ({placeholders})",
                valeurs,
            )
            eleve_id = curseur.lastrowid
            curseur.execute(
                """
                INSERT INTO inscriptions
                    (eleve_id, classe_id, annee_scolaire_id, date_inscription, statut)
                VALUES (%s, %s, %s, CURDATE(), 'inscrit')
                """,
                (eleve_id, classe_id, classe["annee_scolaire_id"]),
            )
            inscription_id = curseur.lastrowid
            curseur.execute(
                """
                INSERT INTO journal_activites
                    (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
                VALUES (%s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s)
                """,
                (
                    g.current_user["id"], "création", "eleves", eleve_id,
                    "Création d'un dossier élève.", request.remote_addr,
                    g.current_user["id"], "inscription", "inscriptions", inscription_id,
                    "Inscription dans la classe sélectionnée.", request.remote_addr,
                ),
            )
            connexion.commit()
        except (Error, ValueError):
            connexion.rollback()
            app.logger.exception("Création et inscription de l'élève impossibles.")
            flash("Le dossier et l'inscription n'ont pas été enregistrés. Vérifiez les données et références.", "danger")
            return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes), 400
        finally:
            connexion.close()
        flash("L'élève a été enregistré et inscrit dans la classe sélectionnée.", "success")
        return redirect(url_for("page_module", module="eleves"))

    return render_template("eleves/formulaire.html", classes=classes, db_message=message_classes)


@app.route("/eleves/<int:eleve_id>")
def detail_eleve(eleve_id):
    connexion = obtenir_connexion()
    if connexion is None:
        return render_template("eleves/detail.html", eleve=None, message="La connexion MySQL est indisponible."), 503

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT e.*, CONCAT_WS(' ', e.nom, e.postnom, e.prenom) AS nom_complet,
                   c.nom AS classe, a.libelle AS annee_scolaire,
                   i.statut AS statut_inscription, i.date_inscription
            FROM eleves e
            LEFT JOIN inscriptions i ON i.id = (
                SELECT i2.id FROM inscriptions i2
                WHERE i2.eleve_id = e.id
                ORDER BY i2.date_creation DESC, i2.id DESC LIMIT 1
            )
            LEFT JOIN classes c ON c.id = i.classe_id
            LEFT JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
            WHERE e.id = %s AND e.ecole_id = %s
            LIMIT 1
            """,
            (eleve_id, g.current_user["ecole_id"]),
        )
        eleve = cast(dict[str, Any] | None, curseur.fetchone())
        historique: list[dict[str, Any]] = []
        if eleve is not None:
            curseur.execute(
                """
                SELECT i.id, i.date_inscription, i.statut, i.montant_inscription,
                       i.observations, c.nom AS classe, c.niveau, a.libelle AS annee_scolaire
                FROM inscriptions i
                INNER JOIN classes c ON c.id = i.classe_id
                INNER JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
                INNER JOIN eleves e ON e.id = i.eleve_id
                WHERE i.eleve_id = %s AND e.ecole_id = %s
                ORDER BY a.date_debut DESC, i.date_creation DESC, i.id DESC
                """,
                (eleve_id, g.current_user["ecole_id"]),
            )
            historique = cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Lecture du dossier élève impossible.")
        return render_template("eleves/detail.html", eleve=None, message="Le dossier élève n'a pas pu être chargé."), 500
    finally:
        connexion.close()

    if eleve is None:
        return render_template("eleves/detail.html", eleve=None, message="Aucun dossier ne correspond à cet élève."), 404

    return render_template("eleves/detail.html", eleve=eleve, historique=historique, message="")


@app.route("/eleves/<int:eleve_id>/modifier", methods=["GET", "POST"])
def modifier_eleve(eleve_id):
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT * FROM eleves WHERE id = %s AND ecole_id = %s LIMIT 1",
            (eleve_id, g.current_user["ecole_id"]),
        )
        eleve = cast(dict[str, Any] | None, curseur.fetchone())
    except Exception:
        app.logger.exception("Lecture du dossier à modifier impossible.")
        abort(500)
    finally:
        connexion.close()
    if not eleve:
        abort(404)
    if request.method == "GET":
        return render_template("eleves/modifier.html", eleve=eleve)

    nom = (request.form.get("nom") or "").strip()
    sexe = (request.form.get("sexe") or "").strip()
    if not nom or sexe not in {"M", "F", "autre"}:
        flash("Le nom et une valeur valide de sexe sont obligatoires.", "danger")
        return render_template("eleves/modifier.html", eleve=eleve), 400
    date_naissance_brute = (request.form.get("date_naissance") or "").strip()
    try:
        date_naissance = date.fromisoformat(date_naissance_brute) if date_naissance_brute else None
    except ValueError:
        flash("La date de naissance n'est pas valide.", "danger")
        return render_template("eleves/modifier.html", eleve=eleve), 400

    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        connexion.start_transaction()
        curseur = connexion.cursor()
        curseur.execute(
            """
            UPDATE eleves SET nom = %s, postnom = %s, prenom = %s, sexe = %s,
                date_naissance = %s, lieu_naissance = %s, nom_tuteur = %s,
                telephone_tuteur = %s, adresse = %s
            WHERE id = %s AND ecole_id = %s
            """,
            (nom, (request.form.get("postnom") or "").strip() or None,
             (request.form.get("prenom") or "").strip() or None, sexe, date_naissance,
             (request.form.get("lieu_naissance") or "").strip() or None,
             (request.form.get("nom_tuteur") or "").strip() or None,
             (request.form.get("telephone_tuteur") or "").strip() or None,
             (request.form.get("adresse") or "").strip() or None,
             eleve_id, g.current_user["ecole_id"]),
        )
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "modification", "eleves", eleve_id,
             "Modification des informations personnelles de l'élève.", request.remote_addr),
        )
        connexion.commit()
        flash("Le dossier élève a été modifié. Son historique d'inscription est conservé.", "success")
        return redirect(url_for("detail_eleve", eleve_id=eleve_id))
    except Error:
        connexion.rollback()
        app.logger.exception("Modification du dossier élève impossible.")
        flash("Le dossier élève n'a pas été modifié.", "danger")
        return render_template("eleves/modifier.html", eleve=eleve), 400
    finally:
        connexion.close()


@app.route("/eleves/<int:eleve_id>/inscrire", methods=["GET", "POST"])
def reinscrire_eleve(eleve_id):
    eleve = None
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, matricule, nom, postnom, prenom FROM eleves WHERE id = %s AND ecole_id = %s AND statut = 'actif' LIMIT 1",
            (eleve_id, g.current_user["ecole_id"]),
        )
        eleve = cast(dict[str, Any] | None, curseur.fetchone())
    except Exception:
        app.logger.exception("Chargement élève avant réinscription impossible.")
        abort(500)
    finally:
        connexion.close()
    if not eleve:
        abort(404)
    classes, message = charger_classes_inscription(g.current_user["ecole_id"])
    contexte = {"eleve": eleve, "classes": classes, "db_message": message}
    if request.method == "GET":
        return render_template("eleves/reinscrire.html", **contexte)

    classe_id = request.form.get("classe_id", type=int)
    observations = (request.form.get("observations") or "").strip() or None
    if not classe_id:
        flash("Sélectionnez une classe de l'année en cours.", "danger")
        return render_template("eleves/reinscrire.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT c.id, c.annee_scolaire_id
            FROM classes c INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
            WHERE c.id = %s AND c.ecole_id = %s AND c.statut = 'active' AND a.statut = 'en_cours'
            LIMIT 1 FOR UPDATE
            """,
            (classe_id, g.current_user["ecole_id"]),
        )
        classe = cast(dict[str, Any] | None, curseur.fetchone())
        if not classe:
            connexion.rollback()
            flash("La classe n'est pas disponible dans votre établissement.", "danger")
            return render_template("eleves/reinscrire.html", **contexte), 400
        curseur.execute(
            """
            SELECT id, classe_id FROM inscriptions
            WHERE eleve_id = %s AND annee_scolaire_id = %s AND statut = 'inscrit'
            LIMIT 1 FOR UPDATE
            """,
            (eleve_id, classe["annee_scolaire_id"]),
        )
        inscription_active = cast(dict[str, Any] | None, curseur.fetchone())
        if inscription_active and inscription_active["classe_id"] == classe_id:
            connexion.rollback()
            flash("L'élève est déjà inscrit dans cette classe pour l'année en cours.", "danger")
            return render_template("eleves/reinscrire.html", **contexte), 409
        if inscription_active:
            curseur.execute(
                "UPDATE inscriptions SET statut = 'transfere', observations = %s WHERE id = %s",
                (observations or "Changement de classe", inscription_active["id"]),
            )
        curseur.execute(
            """
            INSERT INTO inscriptions
                (eleve_id, classe_id, annee_scolaire_id, date_inscription, statut, observations)
            VALUES (%s, %s, %s, CURDATE(), 'inscrit', %s)
            """,
            (eleve_id, classe_id, classe["annee_scolaire_id"], observations),
        )
        nouvelle_inscription_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "inscription", "inscriptions", nouvelle_inscription_id,
             "Inscription ou changement de classe enregistré; les anciennes inscriptions sont conservées.", request.remote_addr),
        )
        connexion.commit()
        flash("L'inscription a été enregistrée; l'historique antérieur est conservé.", "success")
        return redirect(url_for("detail_eleve", eleve_id=eleve_id))
    except Error:
        connexion.rollback()
        app.logger.exception("Réinscription/changement de classe impossible.")
        flash("L'inscription n'a pas été enregistrée.", "danger")
        return render_template("eleves/reinscrire.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/paiements-eleves/nouveau", methods=["GET", "POST"])
def formulaire_paiement_eleve():
    recherche = (request.args.get("q") or request.form.get("recherche") or "").strip()
    inscriptions, frais = charger_references_paiement(g.current_user["ecole_id"], recherche)
    contexte = {"inscriptions": inscriptions, "types_frais": frais, "recherche": recherche}
    if request.method == "GET":
        return render_template("finances/nouveau_paiement_eleve.html", **contexte)

    inscription_id = request.form.get("inscription_id", type=int)
    type_frais_id = request.form.get("type_frais_id", type=int)
    try:
        montant = Decimal((request.form.get("montant_paye") or "").strip().replace(",", "."))
    except InvalidOperation:
        montant = Decimal("0")
    mode_paiement = (request.form.get("mode_paiement") or "").strip()
    reference = (request.form.get("reference_paiement") or "").strip() or None
    commentaire = (request.form.get("commentaire") or "").strip() or None

    if not inscription_id or not type_frais_id or not montant.is_finite() or montant <= 0:
        flash("Sélectionnez l'inscription et le frais, puis saisissez un montant positif valide.", "danger")
        return render_template("finances/nouveau_paiement_eleve.html", **contexte), 400
    if mode_paiement not in {"especes", "mobile_money", "banque", "autre"}:
        flash("Sélectionnez un mode de paiement autorisé.", "danger")
        return render_template("finances/nouveau_paiement_eleve.html", **contexte), 400
    if len(reference or "") > 100:
        flash("La référence du paiement ne peut pas dépasser 100 caractères.", "danger")
        return render_template("finances/nouveau_paiement_eleve.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible. Aucun paiement n'a été enregistré.", "danger")
        return render_template("finances/nouveau_paiement_eleve.html", **contexte), 503

    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT i.id, i.annee_scolaire_id, f.montant, f.id AS frais_id
            FROM inscriptions i
            INNER JOIN eleves e ON e.id = i.eleve_id
            INNER JOIN annees_scolaires a ON a.id = i.annee_scolaire_id
            INNER JOIN types_frais f ON f.id = %s
            WHERE i.id = %s AND e.ecole_id = %s AND i.statut = 'inscrit'
              AND e.statut = 'actif' AND a.statut = 'en_cours'
              AND f.ecole_id = e.ecole_id
              AND f.annee_scolaire_id = i.annee_scolaire_id AND f.statut = 'actif'
            FOR UPDATE
            """,
            (type_frais_id, inscription_id, g.current_user["ecole_id"]),
        )
        inscription = cast(dict[str, Any] | None, curseur.fetchone())
        if inscription is None:
            connexion.rollback()
            flash("L'inscription et le type de frais doivent être actifs et appartenir à la même année et école.", "danger")
            return render_template("finances/nouveau_paiement_eleve.html", **contexte), 400

        curseur.execute(
            """
            SELECT id, pourcentage_hierarchie, pourcentage_prime_enseignants,
                   pourcentage_promoteur, pourcentage_fonctionnement
            FROM regles_financieres
            WHERE ecole_id = %s AND annee_scolaire_id = %s AND actif = 1
              AND date_effet <= CURRENT_DATE()
              AND (date_fin IS NULL OR date_fin >= CURRENT_DATE())
            ORDER BY date_effet DESC, id DESC LIMIT 1 FOR UPDATE
            """,
            (g.current_user["ecole_id"], inscription["annee_scolaire_id"]),
        )
        regle = cast(dict[str, Any] | None, curseur.fetchone())
        if regle is None:
            connexion.rollback()
            flash("Aucune règle financière valide à 100 % n'est configurée pour cette année; contactez l'administrateur.", "danger")
            return render_template("finances/nouveau_paiement_eleve.html", **contexte), 409

        pourcentages = tuple(Decimal(str(regle[nom])) for nom in (
            "pourcentage_hierarchie", "pourcentage_prime_enseignants",
            "pourcentage_promoteur", "pourcentage_fonctionnement",
        ))
        if sum(pourcentages) != Decimal("100.00"):
            connexion.rollback()
            flash("La règle financière active ne totalise pas 100 %. Aucun paiement n'a été enregistré.", "danger")
            return render_template("finances/nouveau_paiement_eleve.html", **contexte), 409

        montant_paye = montant.quantize(Decimal("0.01"))
        montant_du = Decimal(str(inscription["montant"])).quantize(Decimal("0.01"))
        trois_premieres_parts = tuple(
            (montant_paye * pourcentage / Decimal("100")).quantize(Decimal("0.01"))
            for pourcentage in pourcentages[:3]
        )
        derniere_part = montant_paye - sum(trois_premieres_parts)
        montants_repartis = (*trois_premieres_parts, derniere_part)
        numero_recu = f"REC-{datetime.now():%Y%m%d}-{secrets.token_hex(4).upper()}"
        curseur.execute(
            """
            INSERT INTO paiements_eleves
                (inscription_id, type_frais_id, numero_recu, montant_du, montant_paye,
                 mode_paiement, reference_paiement, commentaire, encaisse_par, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'valide')
            """,
            (inscription_id, type_frais_id, numero_recu, montant_du, montant_paye,
             mode_paiement, reference, commentaire, g.current_user["id"]),
        )
        paiement_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO repartitions_paiements
                (paiement_id, regle_financiere_id, montant_reference,
                 pourcentage_hierarchie, montant_hierarchie,
                 pourcentage_prime_enseignants, montant_prime_enseignants,
                 pourcentage_promoteur, montant_promoteur,
                 pourcentage_fonctionnement, montant_fonctionnement)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (paiement_id, regle["id"], montant_paye,
             pourcentages[0], montants_repartis[0], pourcentages[1], montants_repartis[1],
             pourcentages[2], montants_repartis[2], pourcentages[3], montants_repartis[3]),
        )
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "paiement", "paiements_eleves", paiement_id,
             f"Paiement enregistré, reçu {numero_recu}.", request.remote_addr),
        )
        connexion.commit()
        flash("Le paiement a été enregistré et réparti.", "success")
        return redirect(url_for("recu_paiement", numero_recu=numero_recu))
    except Error:
        connexion.rollback()
        app.logger.exception("Enregistrement du paiement élève impossible.")
        flash("Le paiement a échoué. Aucune écriture partielle n'a été conservée.", "danger")
        return render_template("finances/nouveau_paiement_eleve.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/paiements-eleves/recu/<numero_recu>")
def recu_paiement(numero_recu):
    connexion = obtenir_connexion()
    if connexion is None:
        abort(503)
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            """
            SELECT p.*, p.montant_paye AS montant,
                   CONCAT_WS(' ', el.nom, el.postnom, el.prenom) AS eleve,
                   el.matricule, c.nom AS classe, f.nom AS type_frais,
                   CONCAT_WS(' ', u.nom, u.postnom, u.prenom) AS caissier,
                   ec.nom AS ecole, ec.devise
            FROM paiements_eleves p
            INNER JOIN inscriptions i ON i.id = p.inscription_id
            INNER JOIN eleves el ON el.id = i.eleve_id
            INNER JOIN classes c ON c.id = i.classe_id
            INNER JOIN types_frais f ON f.id = p.type_frais_id
            INNER JOIN ecoles ec ON ec.id = el.ecole_id
            LEFT JOIN utilisateurs u ON u.id = p.encaisse_par
            WHERE p.numero_recu = %s AND ec.id = %s AND p.statut = 'valide'
            LIMIT 1
            """,
            (numero_recu, g.current_user["ecole_id"]),
        )
        paiement = cast(dict[str, Any] | None, curseur.fetchone())
    except Exception:
        app.logger.exception("Lecture du reçu impossible.")
        abort(500)
    finally:
        connexion.close()
    if paiement is None:
        abort(404)
    return render_template("finances/recu.html", paiement=paiement, ecole={"nom": paiement["ecole"]})


@app.route("/enseignants/nouveau", methods=["GET", "POST"])
def formulaire_enseignant():
    if request.method == "POST":
        nom = (request.form.get("nom") or "").strip()
        prenom = (request.form.get("prenom") or "").strip()
        telephone = (request.form.get("telephone") or "").strip()

        if not nom or not prenom:
            flash("Le nom et le prénom de l'enseignant sont obligatoires.", "danger")
            return render_template("enseignants/formulaire.html")

        if not telephone:
            flash("Le téléphone est requis pour identifier le dossier enseignant.", "danger")
            return render_template("enseignants/formulaire.html")

        donnees = {
            "nom": nom,
            "postnom": (request.form.get("postnom") or "").strip(),
            "prenom": prenom,
            "telephone": telephone,
            "specialite": (request.form.get("specialite") or "").strip(),
            "date_engagement": (request.form.get("date_engagement") or "").strip(),
        }

        donnees["ecole_id"] = g.current_user["ecole_id"]
        colonnes = set(colonnes_table("enseignants"))
        donnees = {cle: valeur for cle, valeur in donnees.items() if cle in colonnes}
        if "matricule" in colonnes and not donnees.get("matricule"):
            donnees["matricule"] = f"EN-{secrets.token_hex(5).upper()}"
        connexion = obtenir_connexion()
        if connexion is None:
            flash("La connexion MySQL est indisponible pour enregistrer l'enseignant.", "danger")
            return render_template("enseignants/formulaire.html"), 503

        try:
            curseur = connexion.cursor()
            placeholders = ", ".join(["%s"] * len(donnees))
            curseur.execute(
                f"INSERT INTO enseignants ({', '.join(donnees)}) VALUES ({placeholders})",
                tuple(donnees.values()),
            )
            enseignant_id = curseur.lastrowid
            curseur.execute(
                """
                INSERT INTO journal_activites
                    (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (g.current_user["id"], "création", "enseignants", enseignant_id, "Création d'un dossier enseignant.", request.remote_addr),
            )
            connexion.commit()
            flash("Le dossier enseignant a été enregistré.", "success")
            return redirect(url_for("page_module", module="enseignants"))
        except Error:
            connexion.rollback()
            app.logger.exception("Création du dossier enseignant impossible.")
            flash("Le dossier n'a pas pu être enregistré. Vérifiez les données fournies.", "warning")
            return render_template("enseignants/formulaire.html"), 400
        finally:
            connexion.close()

    return render_template("enseignants/formulaire.html")


@app.route("/enseignants/affecter", methods=["GET", "POST"])
def formulaire_affectation_enseignant():
    connexion = obtenir_connexion()
    enseignants = []
    classes = []
    if connexion is not None:
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT id, matricule, CONCAT_WS(' ', nom, postnom, prenom) AS nom_complet FROM enseignants WHERE ecole_id = %s AND statut = 'actif' ORDER BY nom, prenom",
                (g.current_user["ecole_id"],),
            )
            enseignants = cast(list[dict[str, Any]], curseur.fetchall())
            curseur.execute(
                """
                SELECT c.id, c.nom, c.niveau, c.annee_scolaire_id, a.libelle AS annee_scolaire
                FROM classes c INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
                WHERE c.ecole_id = %s AND c.statut = 'active' AND a.statut != 'terminee'
                ORDER BY a.date_debut DESC, c.niveau, c.nom
                """,
                (g.current_user["ecole_id"],),
            )
            classes = cast(list[dict[str, Any]], curseur.fetchall())
        except Exception:
            app.logger.exception("Chargement des options d'affectation impossible.")
        finally:
            connexion.close()
    contexte = {"enseignants": enseignants, "classes": classes}
    if request.method == "GET":
        return render_template("enseignants/affectation.html", **contexte)

    enseignant_id = request.form.get("enseignant_id", type=int)
    classe_id = request.form.get("classe_id", type=int)
    fonction = (request.form.get("fonction") or "Titulaire").strip()
    date_debut_brute = (request.form.get("date_debut") or "").strip()
    try:
        debut = date.fromisoformat(date_debut_brute)
    except ValueError:
        debut = None
    if not enseignant_id or not classe_id or not debut or len(fonction) > 100:
        flash("Sélectionnez un enseignant, une classe et une date de début valides.", "danger")
        return render_template("enseignants/affectation.html", **contexte), 400

    connexion = obtenir_connexion()
    if connexion is None:
        flash("La connexion MySQL est indisponible.", "danger")
        return render_template("enseignants/affectation.html", **contexte), 503
    try:
        connexion.start_transaction()
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id FROM enseignants WHERE id = %s AND ecole_id = %s AND statut = 'actif' LIMIT 1 FOR UPDATE",
            (enseignant_id, g.current_user["ecole_id"]),
        )
        enseignant = curseur.fetchone()
        curseur.execute(
            """
            SELECT c.id, c.annee_scolaire_id FROM classes c
            INNER JOIN annees_scolaires a ON a.id = c.annee_scolaire_id
            WHERE c.id = %s AND c.ecole_id = %s AND c.statut = 'active'
              AND a.statut != 'terminee' LIMIT 1 FOR UPDATE
            """,
            (classe_id, g.current_user["ecole_id"]),
        )
        classe = cast(dict[str, Any] | None, curseur.fetchone())
        if not enseignant or not classe:
            connexion.rollback()
            flash("L'enseignant ou la classe ne correspond pas à cet établissement.", "danger")
            return render_template("enseignants/affectation.html", **contexte), 400

        annee_scolaire_id = int(classe["annee_scolaire_id"])
        curseur.execute(
            """
            SELECT id FROM affectations_enseignants
            WHERE enseignant_id = %s AND annee_scolaire_id = %s
              AND statut = 'active' AND date_fin IS NULL
            LIMIT 1 FOR UPDATE
            """,
            (enseignant_id, annee_scolaire_id),
        )
        if curseur.fetchone():
            connexion.rollback()
            flash("Cet enseignant possède déjà une affectation active pour cette année scolaire.", "danger")
            return render_template("enseignants/affectation.html", **contexte), 409

        curseur.execute(
            """
            INSERT INTO affectations_enseignants
                (enseignant_id, classe_id, annee_scolaire_id, fonction, date_debut, statut)
            VALUES (%s, %s, %s, %s, %s, 'active')
            """,
            (enseignant_id, classe_id, annee_scolaire_id, fonction or "Titulaire", debut),
        )
        affectation_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (g.current_user["id"], "affectation", "affectations_enseignants", affectation_id,
             "Nouvelle affectation d'enseignant enregistrée.", request.remote_addr),
        )
        connexion.commit()
        flash("L'affectation a été enregistrée sans supprimer l'historique.", "success")
        return redirect(url_for("page_module", module="enseignants"))
    except Error:
        connexion.rollback()
        app.logger.exception("Création de l'affectation impossible.")
        flash("L'affectation n'a pas été enregistrée.", "danger")
        return render_template("enseignants/affectation.html", **contexte), 400
    finally:
        connexion.close()


@app.route("/enseignants/<int:enseignant_id>")
def detail_enseignant(enseignant_id):
    connexion = obtenir_connexion()
    if connexion is None:
        return render_template("enseignants/detail.html", enseignant=None, message="La connexion MySQL est indisponible."), 503

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT * FROM enseignants WHERE id = %s AND ecole_id = %s LIMIT 1",
            (enseignant_id, g.current_user["ecole_id"]),
        )
        enseignant = cast(dict[str, Any] | None, curseur.fetchone())
        affectations: list[dict[str, Any]] = []
        if enseignant is not None:
            curseur.execute(
                """
                SELECT af.id, af.fonction, af.date_debut, af.date_fin, af.statut,
                       c.nom AS classe, c.niveau, a.libelle AS annee_scolaire
                FROM affectations_enseignants af
                INNER JOIN classes c ON c.id = af.classe_id
                INNER JOIN annees_scolaires a ON a.id = af.annee_scolaire_id
                WHERE af.enseignant_id = %s AND a.ecole_id = %s
                ORDER BY af.date_debut DESC, af.id DESC
                """,
                (enseignant_id, g.current_user["ecole_id"]),
            )
            affectations = cast(list[dict[str, Any]], curseur.fetchall())
    except Exception:
        app.logger.exception("Lecture du dossier enseignant impossible.")
        return render_template("enseignants/detail.html", enseignant=None, message="Le dossier enseignant n'a pas pu être chargé."), 500
    finally:
        connexion.close()

    if enseignant is None:
        return render_template("enseignants/detail.html", enseignant=None, message="Aucun dossier ne correspond à cet enseignant."), 404

    return render_template("enseignants/detail.html", enseignant=enseignant, affectations=affectations, message="")


@app.route("/utilisateurs/nouveau", methods=["GET", "POST"])
def formulaire_utilisateur():
    enseignants_disponibles = []
    besoin_options_enseignant = request.method == "GET" or request.form.get("role") == "enseignant"
    connexion_options = obtenir_connexion() if besoin_options_enseignant else None
    if connexion_options is not None:
        try:
            curseur_options = connexion_options.cursor(dictionary=True)
            curseur_options.execute(
                """
                SELECT id, matricule, CONCAT_WS(' ', nom, postnom, prenom) AS nom_complet
                FROM enseignants
                WHERE ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NULL
                ORDER BY nom, prenom
                """,
                (g.current_user["ecole_id"],),
            )
            enseignants_disponibles = cast(list[dict[str, Any]], curseur_options.fetchall())
        except Exception:
            app.logger.exception("Chargement des profils enseignants sans compte impossible.")
        finally:
            connexion_options.close()
    contexte = {"enseignants_disponibles": enseignants_disponibles}
    if request.method == "POST":
        nom = (request.form.get("nom") or "").strip()
        postnom = (request.form.get("postnom") or "").strip()
        prenom = (request.form.get("prenom") or "").strip()
        nom_utilisateur = (request.form.get("nom_utilisateur") or "").strip()
        email = (request.form.get("email") or "").strip() or None
        mot_de_passe = request.form.get("mot_de_passe") or ""
        role = (request.form.get("role") or "").strip()
        enseignant_id = request.form.get("enseignant_id", type=int)

        if not nom or not nom_utilisateur or not mot_de_passe or role not in {
            "administrateur", "caissier", "enseignant"
        }:
            flash("Complétez le nom, l'identifiant, le mot de passe et le rôle.", "danger")
            return render_template("utilisateurs/formulaire.html", **contexte)
        if role == "enseignant" and not enseignant_id:
            flash("Sélectionnez le dossier enseignant à relier à ce compte.", "danger")
            return render_template("utilisateurs/formulaire.html", **contexte), 400
        if len(mot_de_passe) < app.config["PASSWORD_MIN_LENGTH"]:
            flash(
                f"Le mot de passe doit contenir au moins {app.config['PASSWORD_MIN_LENGTH']} caractères.",
                "danger",
            )
            return render_template("utilisateurs/formulaire.html", **contexte)

        connexion = obtenir_connexion()
        if connexion is None:
            flash("La connexion MySQL est indisponible pour créer le compte.", "danger")
            return render_template("utilisateurs/formulaire.html", **contexte), 503

        try:
            curseur = connexion.cursor()
            if role == "enseignant":
                curseur.execute(
                    "SELECT id FROM enseignants WHERE id = %s AND ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NULL LIMIT 1 FOR UPDATE",
                    (enseignant_id, g.current_user["ecole_id"]),
                )
                if not curseur.fetchone():
                    connexion.rollback()
                    flash("Le profil enseignant est déjà lié ou n'appartient pas à cet établissement.", "danger")
                    return render_template("utilisateurs/formulaire.html", **contexte), 400
            curseur.execute(
                """
                INSERT INTO utilisateurs
                    (ecole_id, nom, postnom, prenom, nom_utilisateur, email,
                     mot_de_passe, role, statut)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'actif')
                """,
                (
                    g.current_user["ecole_id"], nom, postnom or None, prenom or None,
                    nom_utilisateur, email, generate_password_hash(mot_de_passe), role,
                ),
            )
            utilisateur_id = curseur.lastrowid
            if role == "enseignant":
                curseur.execute(
                    "UPDATE enseignants SET utilisateur_id = %s WHERE id = %s AND ecole_id = %s AND utilisateur_id IS NULL",
                    (utilisateur_id, enseignant_id, g.current_user["ecole_id"]),
                )
                if curseur.rowcount != 1:
                    connexion.rollback()
                    flash("Le profil enseignant n'a pas pu être relié au compte.", "danger")
                    return render_template("utilisateurs/formulaire.html", **contexte), 409
            curseur.execute(
                """
                INSERT INTO journal_activites
                    (utilisateur_id, action, table_concernee, enregistrement_id, description, adresse_ip)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    g.current_user["id"], "création", "utilisateurs", utilisateur_id,
                    f"Création du compte {nom_utilisateur} (rôle {role}).", request.remote_addr,
                ),
            )
            connexion.commit()
            flash("Le compte utilisateur a été créé.", "success")
            return redirect(url_for("page_module", module="utilisateurs"))
        except Error as erreur:
            connexion.rollback()
            app.logger.exception("Création du compte utilisateur impossible.")
            if getattr(erreur, "errno", None) == 1062:
                flash("Ce nom d'utilisateur ou cette adresse e-mail est déjà utilisé.", "danger")
            else:
                flash("Le compte n'a pas pu être créé. Vérifiez les données fournies.", "danger")
            return render_template("utilisateurs/formulaire.html", **contexte), 400
        finally:
            connexion.close()

    return render_template("utilisateurs/formulaire.html", **contexte)


@app.cli.command("bootstrap-admin")
def bootstrap_admin():
    """Crée la première école et le premier administrateur, uniquement si aucun compte n'existe."""
    connexion = obtenir_connexion()
    if connexion is None:
        raise click.ClickException("La connexion MySQL est indisponible.")

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute("SELECT COUNT(*) AS total FROM utilisateurs")
        compte_utilisateurs = cast(dict[str, Any] | None, curseur.fetchone())
        if compte_utilisateurs is None or compte_utilisateurs["total"]:
            raise click.ClickException(
                "Des comptes existent déjà. Utilisez la commande reset-user-password si nécessaire."
            )

        curseur.execute("SELECT id, nom FROM ecoles ORDER BY id")
        ecoles = cast(list[dict[str, Any]], curseur.fetchall())
        if ecoles:
            for ecole in ecoles:
                click.echo(f"{ecole['id']}: {ecole['nom']}")
            ecole_id = click.prompt("ID de l'école pour le compte administrateur", type=int)
            if ecole_id not in {ecole["id"] for ecole in ecoles}:
                raise click.ClickException("L'école sélectionnée n'existe pas.")
        else:
            nom_ecole = click.prompt("Nom de la première école")
            adresse = click.prompt("Adresse (facultatif)", default="", show_default=False) or None
            telephone = click.prompt("Téléphone (facultatif)", default="", show_default=False) or None
            email_ecole = click.prompt("E-mail (facultatif)", default="", show_default=False) or None
            directeur = click.prompt("Directeur ou responsable (facultatif)", default="", show_default=False) or None
            curseur.execute(
                """
                INSERT INTO ecoles (nom, adresse, telephone, email, directeur)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (nom_ecole, adresse, telephone, email_ecole, directeur),
            )
            ecole_id = curseur.lastrowid

        nom = click.prompt("Nom de l'administrateur")
        postnom = click.prompt("Postnom (facultatif)", default="", show_default=False) or None
        prenom = click.prompt("Prénom (facultatif)", default="", show_default=False) or None
        nom_utilisateur = click.prompt("Nom d'utilisateur")
        email = click.prompt("E-mail (facultatif)", default="", show_default=False) or None
        minimum = app.config["PASSWORD_MIN_LENGTH"]
        mot_de_passe = click.prompt(
            f"Mot de passe ({minimum} caractères minimum)",
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(mot_de_passe) < minimum:
            raise click.ClickException(f"Le mot de passe doit contenir au moins {minimum} caractères.")

        curseur.execute(
            """
            INSERT INTO utilisateurs
                (ecole_id, nom, postnom, prenom, nom_utilisateur, email, mot_de_passe, role, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'administrateur', 'actif')
            """,
            (
                ecole_id, nom, postnom, prenom, nom_utilisateur, email,
                generate_password_hash(mot_de_passe),
            ),
        )
        utilisateur_id = curseur.lastrowid
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (utilisateur_id, "création", "utilisateurs", utilisateur_id, "Provisionnement initial de l'administrateur."),
        )
        connexion.commit()
        click.echo("École et compte administrateur créés avec succès.")
    except click.ClickException:
        connexion.rollback()
        raise
    except Error as erreur:
        connexion.rollback()
        app.logger.exception("Provisionnement initial impossible.")
        raise click.ClickException("L'opération a échoué; aucune donnée partielle n'a été conservée.") from erreur
    finally:
        connexion.close()


@app.cli.command("reset-user-password")
@click.argument("nom_utilisateur")
def reset_user_password(nom_utilisateur):
    """Réinitialise le mot de passe d'un compte depuis la console serveur."""
    minimum = app.config["PASSWORD_MIN_LENGTH"]
    mot_de_passe = click.prompt(
        f"Nouveau mot de passe ({minimum} caractères minimum)",
        hide_input=True,
        confirmation_prompt=True,
    )
    if len(mot_de_passe) < minimum:
        raise click.ClickException(f"Le mot de passe doit contenir au moins {minimum} caractères.")

    connexion = obtenir_connexion()
    if connexion is None:
        raise click.ClickException("La connexion MySQL est indisponible.")

    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT id FROM utilisateurs WHERE nom_utilisateur = %s LIMIT 1",
            (nom_utilisateur,),
        )
        utilisateur = cast(dict[str, Any] | None, curseur.fetchone())
        if not utilisateur:
            raise click.ClickException("Aucun compte ne correspond à ce nom d'utilisateur.")
        curseur.execute(
            "UPDATE utilisateurs SET mot_de_passe = %s WHERE id = %s",
            (generate_password_hash(mot_de_passe), utilisateur["id"]),
        )
        curseur.execute(
            """
            INSERT INTO journal_activites
                (utilisateur_id, action, table_concernee, enregistrement_id, description)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (None, "réinitialisation", "utilisateurs", utilisateur["id"], "Réinitialisation du mot de passe depuis la console."),
        )
        connexion.commit()
        click.echo("Mot de passe réinitialisé.")
    except click.ClickException:
        connexion.rollback()
        raise
    except Error as erreur:
        connexion.rollback()
        app.logger.exception("Réinitialisation du mot de passe impossible.")
        raise click.ClickException("La réinitialisation a échoué.") from erreur
    finally:
        connexion.close()


@app.route("/sante")
def sante():
    """Contrôle technique simple, sans exposition d'informations sensibles."""
    if verifier_connexion_base():
        return {"application": "ok", "base_de_donnees": "accessible"}, 200

    return {"application": "ok", "base_de_donnees": "indisponible"}, 503


@app.errorhandler(404)
def page_introuvable(_erreur):
    app.logger.debug("Ressource introuvable : %s", _erreur)
    return render_template("erreurs/404.html"), 404


@app.errorhandler(500)
def erreur_serveur(_erreur):
    app.logger.exception("Erreur interne du serveur : %s", _erreur)
    return render_template("erreurs/500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
