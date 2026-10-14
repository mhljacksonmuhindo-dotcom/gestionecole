from decimal import Decimal
from unittest.mock import Mock

from app import app, check_password_hash, generate_password_hash


def test_dashboard_aggregate_payments_by_month(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.executed = None

        def execute(self, query, params=None):
            self.executed = (query, params)

        def fetchall(self):
            return [
                {"mois_num": 1, "nom": "Jan", "montant": Decimal("1500")},
                {"mois_num": 2, "nom": "Fév", "montant": Decimal("3000")},
            ]

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr("app.obtenir_connexion", lambda: FakeConnection())

    from app import charger_encaissements_mensuels

    resultat = charger_encaissements_mensuels(1, 7)

    assert resultat == [
        {"nom": "Jan", "montant": 1500.0, "pourcentage": 50.0},
        {"nom": "Fév", "montant": 3000.0, "pourcentage": 100.0},
    ]


def ouvrir_session_admin(client, monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        lambda utilisateur_id: {
            "id": utilisateur_id,
            "ecole_id": 1,
            "nom": "Admin",
            "prenom": "Test",
            "role": "administrateur",
            "statut": "actif",
        },
    )
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["_csrf_token"] = "test-csrf-token"


def test_dashboard_requires_login():
    with app.test_client() as client:
        response = client.get("/dashboard")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/connexion")


def test_login_page_is_available():
    with app.test_client() as client:
        response = client.get("/connexion")
    assert response.status_code == 200
    assert 'name="_csrf_token"' in response.get_data(as_text=True)


def test_login_requires_values():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_csrf_token"] = "test-csrf-token"
        response = client.post(
            "/connexion",
            data={
                "_csrf_token": "test-csrf-token",
                "identifiant": "",
                "mot_de_passe": "",
            },
        )
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Veuillez remplir" in html


def test_login_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setattr("app.trouver_utilisateur", Mock(return_value=None))

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_csrf_token"] = "test-csrf-token"
        response = client.post(
            "/connexion",
            data={
                "_csrf_token": "test-csrf-token",
                "identifiant": "inconnu",
                "mot_de_passe": "mot-de-passe-invalide",
            },
        )

    assert response.status_code == 200
    assert "Identifiant ou mot de passe incorrect" in response.get_data(as_text=True)


def test_login_accepts_valid_hash_and_establishes_session(monkeypatch):
    monkeypatch.setattr(
        "app.trouver_utilisateur",
        Mock(
            return_value={
                "id": 7,
                "mot_de_passe": generate_password_hash("un-secret-long-et-valide"),
                "statut": "actif",
            }
        ),
    )
    monkeypatch.setattr("app.enregistrer_derniere_connexion", Mock(return_value=True))

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_csrf_token"] = "test-csrf-token"
        response = client.post(
            "/connexion",
            data={
                "_csrf_token": "test-csrf-token",
                "identifiant": "admin",
                "mot_de_passe": "un-secret-long-et-valide",
            },
        )
        assert response.status_code == 302
        with client.session_transaction() as session:
            assert session["user_id"] == 7
            assert session.get("_csrf_token")


def test_post_without_csrf_token_is_rejected():
    with app.test_client() as client:
        response = client.post("/connexion", data={"identifiant": "", "mot_de_passe": ""})
    assert response.status_code == 400


def test_eleve_form_validates_submit(monkeypatch):
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/eleves/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "",
                "sexe": "",
            },
        )
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Le nom" in html


def test_journal_displays_activity_fields(monkeypatch):
    monkeypatch.setattr(
        "app.charger_module",
        Mock(return_value=([{"utilisateur": "Admin", "action": "Création"}], "")),
    )

    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.get("/module/journal")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Journal d'activités" in html
    assert "Admin" in html
    assert "Création" in html


def test_account_form_requires_admin(monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 5, "ecole_id": 1, "role": "caissier", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 5
        response = client.get("/utilisateurs/nouveau")
    assert response.status_code == 403


def test_account_creation_stores_hash_and_journal_atomically(monkeypatch):
    statements = []

    class FakeCursor:
        lastrowid = 42

        def execute(self, query, parameters=None):
            statements.append((query, parameters))

    class FakeConnection:
        committed = False
        closed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("Un rollback inattendu a été effectué")

        def close(self):
            self.closed = True

    fake_connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", lambda: fake_connection)

    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/utilisateurs/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Test",
                "nom_utilisateur": "test-caisse",
                "mot_de_passe": "mhlcode",
                "role": "caissier",
            },
        )

    assert response.status_code == 302
    assert fake_connection.committed
    assert fake_connection.closed
    assert len(statements) == 2
    account_parameters = statements[0][1]
    password_hash = account_parameters[6]
    assert password_hash != "mhlcode"
    assert check_password_hash(password_hash, "mhlcode")
    assert "journal_activites" in statements[1][0]


def test_teacher_account_requires_linked_profile(monkeypatch):
    class FakeCursor:
        def execute(self, query, parameters=None):
            pass

        def fetchall(self):
            return []

    class FakeConnection:
        closed = False

        def cursor(self, **kwargs):
            return FakeCursor()

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/utilisateurs/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Enseignant",
                "nom_utilisateur": "professeur",
                "mot_de_passe": "mhlcode",
                "role": "enseignant",
            },
        )
    assert response.status_code == 400
    assert connection.closed


def test_teacher_account_links_user_to_teacher_profile(monkeypatch):
    statements = []

    class FakeCursor:
        lastrowid = 21
        rowcount = 1

        def execute(self, query, parameters=None):
            statements.append((query, parameters))
            if "SELECT id FROM enseignants WHERE id = %s AND ecole_id = %s AND statut = 'actif' AND utilisateur_id IS NULL" in query:
                self.result = {"id": 15}
                return
            if "INSERT INTO utilisateurs" in query:
                self.result = None
                return
            if "UPDATE enseignants SET utilisateur_id" in query:
                self.result = None
                return

        def fetchone(self):
            return {"id": 15}

    class FakeConnection:
        committed = False
        closed = False

        def cursor(self, **kwargs):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("Rollback inattendu pendant la création du compte enseignant")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))

    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/utilisateurs/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Professeur",
                "nom_utilisateur": "prof1",
                "mot_de_passe": "mhlcode",
                "role": "enseignant",
                "enseignant_id": "15",
            },
        )

    assert response.status_code == 302
    assert connection.committed and connection.closed
    assert any("UPDATE enseignants SET utilisateur_id = %s" in query for query, _ in statements)
    assert any(
        parameters and parameters[0] == 21 and parameters[1] == 15 and parameters[2] == 1
        for _, parameters in statements
        if isinstance(parameters, tuple)
    )


def test_password_below_development_minimum_is_rejected(monkeypatch):
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/utilisateurs/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Test",
                "nom_utilisateur": "trop-court",
                "mot_de_passe": "court",
                "role": "caissier",
            },
        )
    assert response.status_code == 200
    assert "au moins 7 caractères" in response.get_data(as_text=True)


def test_school_year_form_rejects_invalid_date_order(monkeypatch):
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/annees-scolaires/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "libelle": "2026-2027",
                "date_debut": "2027-09-01",
                "date_fin": "2027-06-30",
                "statut": "en_preparation",
            },
        )
    assert response.status_code == 400
    assert "date de fin" in response.get_data(as_text=True)


def test_class_form_rejects_unknown_level(monkeypatch):
    monkeypatch.setattr("app.charger_annees_ecole", Mock(return_value=[]))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/classes/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Classe témoin",
                "niveau": "niveau-invalide",
                "annee_scolaire_id": "1",
                "capacite": "40",
            },
        )
    assert response.status_code == 400
    assert "niveau valides" in response.get_data(as_text=True)


def test_cashier_can_open_payment_form_but_not_admin_pages(monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 8, "ecole_id": 1, "role": "caissier", "statut": "actif"}),
    )
    monkeypatch.setattr("app.charger_references_paiement", Mock(return_value=([], [])))

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 8
            session["_csrf_token"] = "cashier-token"
        payment_page = client.get("/paiements-eleves/nouveau")
        admin_page = client.get("/module/utilisateurs")

    assert payment_page.status_code == 200
    assert admin_page.status_code == 403


def test_student_payment_commits_receipt_split_and_journal(monkeypatch):
    statements = []

    class FakeCursor:
        def __init__(self):
            self.results = [
                {"id": 2, "annee_scolaire_id": 3, "montant": Decimal("100.00")},
                {
                    "id": 4,
                    "pourcentage_hierarchie": Decimal("20.00"),
                    "pourcentage_prime_enseignants": Decimal("48.00"),
                    "pourcentage_promoteur": Decimal("24.00"),
                    "pourcentage_fonctionnement": Decimal("8.00"),
                },
            ]
            self.lastrowid = 20

        def execute(self, query, parameters=None):
            statements.append((query, parameters))

        def fetchone(self):
            return self.results.pop(0)

    class FakeConnection:
        committed = False
        rolled_back = False
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return self.fake_cursor

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    monkeypatch.setattr("app.charger_references_paiement", Mock(return_value=([], [])))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 8, "ecole_id": 1, "role": "caissier", "statut": "actif"}),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 8
            session["_csrf_token"] = "cashier-token"
        response = client.post(
            "/paiements-eleves/nouveau",
            data={
                "_csrf_token": "cashier-token",
                "inscription_id": "2",
                "type_frais_id": "5",
                "montant_paye": "10.01",
                "mode_paiement": "especes",
            },
        )

    assert response.status_code == 302
    assert "/paiements-eleves/recu/REC-" in response.headers["Location"]
    assert connection.committed and connection.closed and not connection.rolled_back
    inserts = [(query, params) for query, params in statements if query.lstrip().startswith("INSERT")]
    assert len(inserts) == 3
    split_parameters = inserts[1][1]
    split_amounts = (split_parameters[4], split_parameters[6], split_parameters[8], split_parameters[10])
    assert sum(split_amounts) == Decimal("10.01")
    assert "journal_activites" in inserts[2][0]


def test_student_payment_requires_a_valid_financial_rule(monkeypatch):
    statements = []

    class FakeCursor:
        def __init__(self):
            self.results = [{"id": 2, "annee_scolaire_id": 3, "montant": Decimal("100.00")}, None]

        def execute(self, query, parameters=None):
            statements.append(query)

        def fetchone(self):
            return self.results.pop(0)

    class FakeConnection:
        rolled_back = False
        closed = False

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("Un paiement sans règle ne doit pas être validé")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    monkeypatch.setattr("app.charger_references_paiement", Mock(return_value=([], [])))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 8, "ecole_id": 1, "role": "caissier", "statut": "actif"}),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 8
            session["_csrf_token"] = "cashier-token"
        response = client.post(
            "/paiements-eleves/nouveau",
            data={
                "_csrf_token": "cashier-token",
                "inscription_id": "2",
                "type_frais_id": "5",
                "montant_paye": "10.00",
                "mode_paiement": "especes",
            },
        )

    assert response.status_code == 409
    assert connection.rolled_back and connection.closed
    assert not any(query.lstrip().startswith("INSERT") for query in statements)


def test_financial_rule_requires_exactly_one_hundred_percent(monkeypatch):
    monkeypatch.setattr("app.charger_annees_ecole", Mock(return_value=[]))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/regles-financieres/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Règle invalide",
                "annee_scolaire_id": "1",
                "pourcentage_hierarchie": "20",
                "pourcentage_prime_enseignants": "48",
                "pourcentage_promoteur": "24",
                "pourcentage_fonctionnement": "7",
                "date_effet": "2026-01-01",
            },
        )
    assert response.status_code == 400
    assert "exactement égale à 100 %" in response.get_data(as_text=True)


def test_fee_form_rejects_negative_amount(monkeypatch):
    monkeypatch.setattr("app.charger_annees_ecole", Mock(return_value=[]))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/frais/nouveau",
            data={
                "_csrf_token": "test-csrf-token",
                "nom": "Frais invalide",
                "annee_scolaire_id": "1",
                "montant": "-1",
            },
        )
    assert response.status_code == 400
    assert "montant valide" in response.get_data(as_text=True)


def test_duplicate_teacher_presence_is_rejected_without_insert(monkeypatch):
    statements = []

    class FakeCursor:
        def __init__(self):
            self.results = [{"id": 3}, {"id": 4}, {"id": 99}]

        def execute(self, query, parameters=None):
            statements.append(query)

        def fetchone(self):
            return self.results.pop(0)

    class FakeConnection:
        rolled_back = False
        closed = False

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("Une présence en doublon ne doit pas être validée")

        def close(self):
            self.closed = True

    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=FakeConnection()))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 8, "ecole_id": 1, "role": "administrateur", "statut": "actif"}),
    )
    monkeypatch.setattr("app.charger_annees_ecole", Mock(return_value=[{"id": 4, "statut": "en_cours"}]))

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 8
            session["_csrf_token"] = "presence-token"
        response = client.post(
            "/presences/nouvelle",
            data={
                "_csrf_token": "presence-token",
                "enseignant_id": "3",
                "annee_scolaire_id": "4",
                "date_presence": "2026-10-14",
                "statut": "present",
            },
        )

    assert response.status_code == 409
    assert not any(query.lstrip().startswith("INSERT") for query in statements)


def test_teacher_can_open_private_notifications_but_not_student_lists(monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 22, "ecole_id": 1, "role": "enseignant", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 22
            session["_csrf_token"] = "teacher-token"
        private_page = client.get("/mes-notifications")
        admin_data = client.get("/module/eleves")
    assert private_page.status_code == 200
    assert admin_data.status_code == 403


def test_teacher_cannot_mark_another_users_notification_read(monkeypatch):
    statements = []

    class FakeCursor:
        rowcount = 0

        def execute(self, query, parameters=None):
            statements.append((query, parameters))

    class FakeConnection:
        rolled_back = False
        closed = False

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("Le destinataire n'a pas été vérifié")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 22, "ecole_id": 1, "role": "enseignant", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 22
            session["_csrf_token"] = "teacher-token"
        response = client.post(
            "/mes-notifications/99/lue",
            data={"_csrf_token": "teacher-token"},
        )
    assert response.status_code == 404
    assert connection.rolled_back and connection.closed
    assert "d.utilisateur_id = %s" in statements[0][0]
    assert statements[0][1] == (99, 22, 1)


def test_cashier_dashboard_redirects_to_student_payments(monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 8, "ecole_id": 1, "role": "caissier", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 8
        response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/module/paiements_eleves")


def test_teacher_dashboard_redirects_to_own_workspace(monkeypatch):
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 22, "ecole_id": 1, "role": "enseignant", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 22
        response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/espace-enseignant")


def test_admin_validates_remuneration_without_creating_payment(monkeypatch):
    statements = []

    class FakeCursor:
        def __init__(self):
            self.results = [{
                "id": 10,
                "statut": "a_valider",
                "montant_calcule": Decimal("80.00"),
                "montant_valide": Decimal("75.00"),
            }]
            self.lastrowid = 1

        def execute(self, query, parameters=None):
            statements.append((query, parameters))

        def fetchone(self):
            return self.results.pop(0)

    class FakeConnection:
        committed = False
        closed = False

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("Une rémunération valide doit être commitée")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 1, "ecole_id": 2, "role": "administrateur", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["_csrf_token"] = "admin-token"
        response = client.post(
            "/remunerations/10/valider",
            data={"_csrf_token": "admin-token"},
        )
    assert response.status_code == 302
    assert connection.committed and connection.closed
    assert any("UPDATE remunerations_enseignants SET statut = 'validee'" in query for query, _ in statements)
    assert any("journal_activites" in query for query, _ in statements)
    assert not any("INSERT INTO paiements_enseignants" in query for query, _ in statements)


def test_unvalidated_remuneration_cannot_be_paid(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.results = [{"id": 10, "statut": "a_valider", "montant_valide": Decimal("75.00")}]

        def execute(self, query, parameters=None):
            pass

        def fetchone(self):
            return self.results.pop(0)

    class FakeConnection:
        rolled_back = False
        closed = False

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("Une rémunération en attente ne doit pas être payée")

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=connection))
    monkeypatch.setattr(
        "app.charger_utilisateur_connecte",
        Mock(return_value={"id": 1, "ecole_id": 2, "role": "administrateur", "statut": "actif"}),
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["_csrf_token"] = "admin-token"
        response = client.post(
            "/remunerations/10/payer",
            data={"_csrf_token": "admin-token", "mode_paiement": "especes"},
        )
    assert response.status_code == 409
    assert connection.rolled_back and connection.closed


def test_school_form_rejects_missing_name_without_database_write(monkeypatch):
    monkeypatch.setattr("app.obtenir_connexion", Mock(side_effect=AssertionError("No DB write expected")))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.post(
            "/ecoles/nouvelle",
            data={"_csrf_token": "test-csrf-token", "nom": "", "devise": "USD"},
        )
    assert response.status_code == 400


def test_student_edit_form_loads_for_school_record(monkeypatch):
    class FakeCursor:
        def execute(self, query, parameters=None):
            pass

        def fetchone(self):
            return {
                "id": 7, "nom": "Nsimba", "postnom": "", "prenom": "Amina",
                "sexe": "F", "date_naissance": None, "lieu_naissance": None,
                "nom_tuteur": None, "telephone_tuteur": None, "adresse": None,
            }

    class FakeConnection:
        def cursor(self, **kwargs):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr("app.obtenir_connexion", Mock(return_value=FakeConnection()))
    with app.test_client() as client:
        ouvrir_session_admin(client, monkeypatch)
        response = client.get("/eleves/7/modifier")
    assert response.status_code == 200
    assert "Enregistrer les changements" in response.get_data(as_text=True)
