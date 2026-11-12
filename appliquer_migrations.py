

from typing import cast

from database import obtenir_connexion


def appliquer_migrations():
    connexion = obtenir_connexion()
    if connexion is None:
        print("Impossible de se connecter à MySQL. Vérifiez que MySQL est démarré dans XAMPP.")
        return False

    curseur = connexion.cursor()

    modifications = [
       
        (
            "inscriptions",
            "decision_fin_annee",
            "ALTER TABLE `inscriptions` ADD COLUMN `decision_fin_annee` ENUM('admis', 'redouble', 'a_traiter') DEFAULT NULL AFTER `statut`",
        ),
        (
            "inscriptions",
            "date_decision",
            "ALTER TABLE `inscriptions` ADD COLUMN `date_decision` DATE DEFAULT NULL AFTER `decision_fin_annee`",
        ),
        (
            "inscriptions",
            "decision_par",
            "ALTER TABLE `inscriptions` ADD COLUMN `decision_par` INT(11) DEFAULT NULL AFTER `date_decision`",
        ),
        (
            "inscriptions",
            "motif_retrait",
            "ALTER TABLE `inscriptions` ADD COLUMN `motif_retrait` TEXT DEFAULT NULL AFTER `observations`",
        ),
        (
            "inscriptions",
            "date_retrait",
            "ALTER TABLE `inscriptions` ADD COLUMN `date_retrait` DATE DEFAULT NULL AFTER `motif_retrait`",
        ),
        # Table paiements_eleves
        (
            "paiements_eleves",
            "motif_annulation",
            "ALTER TABLE `paiements_eleves` ADD COLUMN `motif_annulation` TEXT DEFAULT NULL AFTER `statut`",
        ),
        (
            "paiements_eleves",
            "annule_par",
            "ALTER TABLE `paiements_eleves` ADD COLUMN `annule_par` INT(11) DEFAULT NULL AFTER `motif_annulation`",
        ),
        (
            "paiements_eleves",
            "date_annulation",
            "ALTER TABLE `paiements_eleves` ADD COLUMN `date_annulation` DATETIME DEFAULT NULL AFTER `annule_par`",
        ),
        # Table utilisateurs
        (
            "utilisateurs",
            "doit_changer_mdp",
            "ALTER TABLE `utilisateurs` ADD COLUMN `doit_changer_mdp` TINYINT(1) DEFAULT 0 AFTER `derniere_connexion`",
        ),
    ]

    for table, colonne, sql_alter in modifications:
        curseur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (table, colonne),
        )
        resultat_colonne = cast(tuple[int, ...] | None, curseur.fetchone())
        existe = bool(resultat_colonne and resultat_colonne[0] > 0)
        if not existe:
            try:
                curseur.execute(sql_alter)
                print(f"Colonnne {colonne} ajoutée à {table}.")
            except Exception as e:
                print(f"Erreur lors de l'ajout de {colonne} à {table}: {e}")
        else:
            print(f"La colonne {colonne} existe déjà sur {table}.")

    curseur.execute(
        """
        SELECT COUNT(*) AS nombre FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'classes'
          AND INDEX_NAME = 'annee_niveau_division'
        """
    )
    resultat_index = cast(tuple[int, ...] | None, curseur.fetchone())
    if resultat_index and resultat_index[0] == 0:
        try:
            curseur.execute(
                "ALTER TABLE `classes` ADD UNIQUE KEY `annee_niveau_division` (`annee_scolaire_id`, `niveau`, `nom`)"
            )
            print("Index unique année + niveau + division ajouté à classes.")
        except Exception as e:
            print(f"Erreur lors de l'ajout de l'index des divisions: {e}")

    curseur.execute(
        """
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'classes'
          AND INDEX_NAME = 'annee_niveau_division'
        """
    )
    resultat_index = cast(tuple[int, ...] | None, curseur.fetchone())
    nouvel_index_present = bool(resultat_index and resultat_index[0] > 0)

    curseur.execute(
        """
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'classes'
          AND INDEX_NAME = 'annee_scolaire_id' AND NON_UNIQUE = 0
        """
    )
    resultat_ancien_index = cast(tuple[int, ...] | None, curseur.fetchone())
    if nouvel_index_present and resultat_ancien_index and resultat_ancien_index[0] > 0:
        try:
            curseur.execute("ALTER TABLE `classes` DROP INDEX `annee_scolaire_id`")
            print("Ancienne unicité année + nom supprimée de classes.")
        except Exception as e:
            print(f"Erreur lors de la suppression de l'ancienne unicité: {e}")

    fk_modifications = [
        (
            "inscriptions",
            "fk_inscriptions_decision_par",
            "ALTER TABLE `inscriptions` ADD CONSTRAINT `fk_inscriptions_decision_par` FOREIGN KEY (`decision_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL",
        ),
        (
            "paiements_eleves",
            "fk_paiements_annule_par",
            "ALTER TABLE `paiements_eleves` ADD CONSTRAINT `fk_paiements_annule_par` FOREIGN KEY (`annule_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL",
        ),
    ]

    for table, nom_fk, sql_fk in fk_modifications:
        curseur.execute(
            """
            SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
            """,
            (table, nom_fk),
        )
        resultat_contrainte = cast(tuple[int, ...] | None, curseur.fetchone())
        existe = bool(resultat_contrainte and resultat_contrainte[0] > 0)
        if not existe:
            try:
                curseur.execute(sql_fk)
                print(f"Contrainte {nom_fk} ajoutée à {table}.")
            except Exception as e:
                print(f"Erreur lors de l'ajout de {nom_fk}: {e}")
        else:
            print(f"La contrainte {nom_fk} existe déjà.")

    connexion.commit()
    connexion.close()
    print("Vérification des migrations terminée.")
    return True


if __name__ == "__main__":
    appliquer_migrations()
