
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";




CREATE TABLE `affectations_enseignants` (
  `id` int(11) NOT NULL,
  `enseignant_id` int(11) NOT NULL,
  `classe_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `fonction` varchar(100) DEFAULT 'Titulaire',
  `date_debut` date NOT NULL,
  `date_fin` date DEFAULT NULL,
  `statut` enum('active','terminee') DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `annees_scolaires` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `libelle` varchar(20) NOT NULL,
  `date_debut` date NOT NULL,
  `date_fin` date NOT NULL,
  `statut` enum('en_preparation','en_cours','terminee') DEFAULT 'en_preparation',
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `annees_scolaires`
(`id`, `ecole_id`, `libelle`, `date_debut`, `date_fin`, `statut`, `date_creation`)
VALUES
(1, 1, '2026-2027', '2026-09-02', '2027-07-02', 'en_cours', '2026-10-14 18:07:33');


CREATE TABLE `classes` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `niveau` enum('1ere_primaire','2eme_primaire','3eme_primaire','4eme_primaire','5eme_primaire','6eme_primaire','autre') NOT NULL,
  `capacite` int(11) DEFAULT 50,
  `frais_inscription` decimal(12,2) DEFAULT 0.00,
  `statut` enum('active','inactive') DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `classes`
(`id`, `ecole_id`, `annee_scolaire_id`, `nom`, `niveau`, `capacite`, `frais_inscription`, `statut`)
VALUES
(1, 1, 1, 'A', '1ere_primaire', 50, 0.00, 'active'),
(2, 1, 1, '1B', '1ere_primaire', 50, 0.00, 'active');


CREATE TABLE `destinataires_notifications` (
  `id` int(11) NOT NULL,
  `notification_id` int(11) NOT NULL,
  `utilisateur_id` int(11) NOT NULL,
  `lu` tinyint(1) DEFAULT 0,
  `date_lecture` datetime DEFAULT NULL,
  `date_envoi` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `ecoles` (
  `id` int(11) NOT NULL,
  `nom` varchar(150) NOT NULL,
  `adresse` varchar(255) DEFAULT NULL,
  `telephone` varchar(30) DEFAULT NULL,
  `email` varchar(150) DEFAULT NULL,
  `directeur` varchar(150) DEFAULT NULL,
  `devise` varchar(100) DEFAULT 'USD',
  `logo` varchar(255) DEFAULT NULL,
  `statut` enum('active','inactive') DEFAULT 'active',
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `ecoles`
(`id`, `nom`, `adresse`, `telephone`, `email`, `directeur`, `devise`, `logo`, `statut`, `date_creation`)
VALUES
(1, 'ECOLE PRIMAIRE LA REFERENCE', 'BP 180BUTEMBO', NULL, NULL, 'MHL', 'USD', NULL, 'active', '2026-10-14 12:25:59');


CREATE TABLE `eleves` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `matricule` varchar(50) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `postnom` varchar(100) DEFAULT NULL,
  `prenom` varchar(100) DEFAULT NULL,
  `sexe` enum('M','F','autre') NOT NULL,
  `date_naissance` date DEFAULT NULL,
  `lieu_naissance` varchar(150) DEFAULT NULL,
  `nom_tuteur` varchar(150) DEFAULT NULL,
  `telephone_tuteur` varchar(30) DEFAULT NULL,
  `adresse` varchar(255) DEFAULT NULL,
  `photo` varchar(255) DEFAULT NULL,
  `statut` enum('actif','inactif') DEFAULT 'actif',
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `eleves`
(`id`, `ecole_id`, `matricule`, `nom`, `postnom`, `prenom`, `sexe`, `date_naissance`, `lieu_naissance`, `nom_tuteur`, `telephone_tuteur`, `adresse`, `photo`, `statut`, `date_creation`)
VALUES
(1, 1, 'EL-710A0920DF', 'MUHINDO', 'MBAS', 'jackson', 'M', '2028-01-01', 'BK', 'MHL', '239', '1', NULL, 'actif', '2026-10-14 18:12:01');


CREATE TABLE `enseignants` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `utilisateur_id` int(11) DEFAULT NULL,
  `matricule` varchar(50) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `postnom` varchar(100) DEFAULT NULL,
  `prenom` varchar(100) DEFAULT NULL,
  `sexe` enum('M','F','autre') DEFAULT NULL,
  `telephone` varchar(30) DEFAULT NULL,
  `email` varchar(150) DEFAULT NULL,
  `adresse` varchar(255) DEFAULT NULL,
  `specialite` varchar(150) DEFAULT NULL,
  `date_engagement` date DEFAULT NULL,
  `salaire_base` decimal(12,2) DEFAULT 0.00,
  `statut` enum('actif','inactif','suspendu') DEFAULT 'actif',
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `inscriptions` (
  `id` int(11) NOT NULL,
  `eleve_id` int(11) NOT NULL,
  `classe_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `date_inscription` date NOT NULL,
  `montant_inscription` decimal(12,2) DEFAULT 0.00,
  `statut` enum('inscrit','transfere','abandonne','termine') DEFAULT 'inscrit',
  `decision_fin_annee` enum('admis','redouble','a_traiter') DEFAULT NULL,
  `date_decision` date DEFAULT NULL,
  `decision_par` int(11) DEFAULT NULL,
  `observations` text DEFAULT NULL,
  `motif_retrait` text DEFAULT NULL,
  `date_retrait` date DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `inscriptions`
(`id`, `eleve_id`, `classe_id`, `annee_scolaire_id`, `date_inscription`, `montant_inscription`, `statut`, `observations`, `date_creation`)
VALUES
(1, 1, 2, 1, '2026-10-14', 0.00, 'inscrit', NULL, '2026-10-14 18:12:01');


CREATE TABLE `journal_activites` (
  `id` bigint(20) NOT NULL,
  `utilisateur_id` int(11) DEFAULT NULL,
  `action` varchar(100) NOT NULL,
  `table_concernee` varchar(100) DEFAULT NULL,
  `enregistrement_id` int(11) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `adresse_ip` varchar(45) DEFAULT NULL,
  `date_action` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


INSERT INTO `journal_activites`
(`id`, `utilisateur_id`, `action`, `table_concernee`, `enregistrement_id`, `description`, `adresse_ip`, `date_action`)
VALUES
(1, 1, 'création', 'utilisateurs', 1, 'Provisionnement initial de l''administrateur.', NULL, '2026-10-14 12:30:25'),
(2, 1, 'création', 'annees_scolaires', 1, 'Création de l''année scolaire 2026-2027.', '127.0.0.1', '2026-10-14 18:07:33'),
(3, 1, 'création', 'classes', 1, 'Création de la classe A.', '127.0.0.1', '2026-10-14 18:08:12'),
(4, 1, 'création', 'classes', 2, 'Création de la classe 1B.', '127.0.0.1', '2026-10-14 18:08:36'),
(5, 1, 'création', 'eleves', 1, 'Création d''un dossier élève.', '127.0.0.1', '2026-10-14 18:12:01'),
(6, 1, 'inscription', 'inscriptions', 1, 'Inscription dans la classe sélectionnée.', '127.0.0.1', '2026-10-14 18:12:01');


CREATE TABLE `notifications` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `titre` varchar(180) NOT NULL,
  `message` text NOT NULL,
  `type` enum('information','alerte','paiement','rappel') DEFAULT 'information',
  `cree_par` int(11) DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `paiements_eleves` (
  `id` int(11) NOT NULL,
  `inscription_id` int(11) NOT NULL,
  `type_frais_id` int(11) NOT NULL,
  `numero_recu` varchar(50) NOT NULL,
  `montant_du` decimal(12,2) NOT NULL DEFAULT 0.00,
  `montant_paye` decimal(12,2) NOT NULL,
  `mode_paiement` enum('especes','mobile_money','banque','autre') DEFAULT 'especes',
  `reference_paiement` varchar(100) DEFAULT NULL,
  `date_paiement` datetime NOT NULL DEFAULT current_timestamp(),
  `commentaire` text DEFAULT NULL,
  `encaisse_par` int(11) DEFAULT NULL,
  `statut` enum('valide','annule') DEFAULT 'valide',
  `motif_annulation` text DEFAULT NULL,
  `annule_par` int(11) DEFAULT NULL,
  `date_annulation` datetime DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `paiements_enseignants` (
  `id` int(11) NOT NULL,
  `remuneration_id` int(11) NOT NULL,
  `numero_recu` varchar(50) NOT NULL,
  `montant_paye` decimal(12,2) NOT NULL,
  `mode_paiement` enum('especes','mobile_money','banque','autre') DEFAULT 'especes',
  `reference_paiement` varchar(100) DEFAULT NULL,
  `date_paiement` datetime NOT NULL DEFAULT current_timestamp(),
  `commentaire` text DEFAULT NULL,
  `paye_par` int(11) DEFAULT NULL,
  `statut` enum('valide','annule') DEFAULT 'valide',
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `presences_enseignants` (
  `id` int(11) NOT NULL,
  `enseignant_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `date_presence` date NOT NULL,
  `statut` enum('present','absent','retard','permission','maladie') NOT NULL,
  `heure_arrivee` time DEFAULT NULL,
  `heure_depart` time DEFAULT NULL,
  `justification` text DEFAULT NULL,
  `enregistre_par` int(11) DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `regles_financieres` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `pourcentage_hierarchie` decimal(5,2) NOT NULL DEFAULT 20.00,
  `pourcentage_prime_enseignants` decimal(5,2) NOT NULL DEFAULT 48.00,
  `pourcentage_promoteur` decimal(5,2) NOT NULL DEFAULT 24.00,
  `pourcentage_fonctionnement` decimal(5,2) NOT NULL DEFAULT 8.00,
  `date_effet` date NOT NULL,
  `date_fin` date DEFAULT NULL,
  `actif` tinyint(1) DEFAULT 1,
  `cree_par` int(11) DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `remunerations_enseignants` (
  `id` int(11) NOT NULL,
  `enseignant_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `mois` tinyint(4) NOT NULL,
  `annee` smallint(6) NOT NULL,
  `total_jours_prevus` int(11) DEFAULT 0,
  `total_jours_presents` int(11) DEFAULT 0,
  `total_absences` int(11) DEFAULT 0,
  `montant_pool_disponible` decimal(12,2) DEFAULT 0.00,
  `montant_calcule` decimal(12,2) DEFAULT 0.00,
  `montant_valide` decimal(12,2) DEFAULT 0.00,
  `regle_calcul` text DEFAULT NULL,
  `statut` enum('brouillon','a_valider','validee','refusee') DEFAULT 'brouillon',
  `valide_par` int(11) DEFAULT NULL,
  `date_validation` datetime DEFAULT NULL,
  `commentaire` text DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `repartitions_paiements` (
  `id` int(11) NOT NULL,
  `paiement_id` int(11) NOT NULL,
  `regle_financiere_id` int(11) DEFAULT NULL,
  `montant_reference` decimal(12,2) NOT NULL,
  `pourcentage_hierarchie` decimal(5,2) NOT NULL,
  `montant_hierarchie` decimal(12,2) NOT NULL,
  `pourcentage_prime_enseignants` decimal(5,2) NOT NULL,
  `montant_prime_enseignants` decimal(12,2) NOT NULL,
  `pourcentage_promoteur` decimal(5,2) NOT NULL,
  `montant_promoteur` decimal(12,2) NOT NULL,
  `pourcentage_fonctionnement` decimal(5,2) NOT NULL,
  `montant_fonctionnement` decimal(12,2) NOT NULL,
  `date_repartition` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


CREATE TABLE `types_frais` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `annee_scolaire_id` int(11) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `montant` decimal(12,2) NOT NULL DEFAULT 0.00,
  `obligatoire` tinyint(1) DEFAULT 1,
  `date_limite` date DEFAULT NULL,
  `statut` enum('actif','inactif') DEFAULT 'actif'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `utilisateurs` (
  `id` int(11) NOT NULL,
  `ecole_id` int(11) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `postnom` varchar(100) DEFAULT NULL,
  `prenom` varchar(100) DEFAULT NULL,
  `nom_utilisateur` varchar(100) NOT NULL,
  `email` varchar(150) DEFAULT NULL,
  `telephone` varchar(30) DEFAULT NULL,
  `mot_de_passe` varchar(255) NOT NULL,
  `role` enum('administrateur','caissier','enseignant') NOT NULL,
  `statut` enum('actif','inactif','bloque') DEFAULT 'actif',
  `derniere_connexion` datetime DEFAULT NULL,
  `doit_changer_mdp` tinyint(1) DEFAULT 0,
  `date_creation` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `utilisateurs`
(`id`, `ecole_id`, `nom`, `postnom`, `prenom`, `nom_utilisateur`, `email`, `telephone`, `mot_de_passe`, `role`, `statut`, `derniere_connexion`, `date_creation`)
VALUES
(1, 1, 'MHL', 'JACKSON', NULL, 'MHL', NULL, NULL, 'scrypt:32768:8:1$zUnThlUtRjGBuad0$bcec851769599c109dde956abdbf3bbc8b08d32eafa2d1f08d301ee416479997624a73b33f2307e8f1f77f4f40984c2d1a0a83d1ea881e94022c6d1312d0e696', 'administrateur', 'actif', '2026-10-14 20:05:46', '2026-10-14 12:30:25');


ALTER TABLE `affectations_enseignants`
  ADD PRIMARY KEY (`id`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`),
  ADD KEY `enseignant_id` (`enseignant_id`,`annee_scolaire_id`),
  ADD KEY `classe_id` (`classe_id`,`annee_scolaire_id`);

ALTER TABLE `annees_scolaires`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `ecole_id` (`ecole_id`,`libelle`);

ALTER TABLE `classes`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `annee_niveau_division` (`annee_scolaire_id`,`niveau`,`nom`),
  ADD KEY `ecole_id` (`ecole_id`);

ALTER TABLE `destinataires_notifications`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `notification_id` (`notification_id`,`utilisateur_id`),
  ADD KEY `utilisateur_id` (`utilisateur_id`,`lu`);

ALTER TABLE `ecoles`
  ADD PRIMARY KEY (`id`);

ALTER TABLE `eleves`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `ecole_id` (`ecole_id`,`matricule`);

ALTER TABLE `enseignants`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `ecole_id` (`ecole_id`,`matricule`),
  ADD UNIQUE KEY `utilisateur_id` (`utilisateur_id`);

ALTER TABLE `inscriptions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `eleve_id` (`eleve_id`,`annee_scolaire_id`),
  ADD KEY `classe_id` (`classe_id`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`);

ALTER TABLE `journal_activites`
  ADD PRIMARY KEY (`id`),
  ADD KEY `date_action` (`date_action`),
  ADD KEY `utilisateur_id` (`utilisateur_id`,`date_action`);

ALTER TABLE `notifications`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ecole_id` (`ecole_id`),
  ADD KEY `cree_par` (`cree_par`);

ALTER TABLE `paiements_eleves`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `numero_recu` (`numero_recu`),
  ADD KEY `type_frais_id` (`type_frais_id`),
  ADD KEY `encaisse_par` (`encaisse_par`),
  ADD KEY `date_paiement` (`date_paiement`),
  ADD KEY `inscription_id` (`inscription_id`,`statut`);

ALTER TABLE `paiements_enseignants`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `numero_recu` (`numero_recu`),
  ADD KEY `remuneration_id` (`remuneration_id`),
  ADD KEY `paye_par` (`paye_par`),
  ADD KEY `date_paiement` (`date_paiement`,`statut`);

ALTER TABLE `presences_enseignants`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `enseignant_id` (`enseignant_id`,`date_presence`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`),
  ADD KEY `enregistre_par` (`enregistre_par`),
  ADD KEY `date_presence` (`date_presence`,`statut`);

ALTER TABLE `regles_financieres`
  ADD PRIMARY KEY (`id`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`),
  ADD KEY `cree_par` (`cree_par`),
  ADD KEY `ecole_id` (`ecole_id`,`annee_scolaire_id`,`actif`);

ALTER TABLE `remunerations_enseignants`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `enseignant_id` (`enseignant_id`,`annee_scolaire_id`,`mois`,`annee`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`),
  ADD KEY `valide_par` (`valide_par`),
  ADD KEY `annee` (`annee`,`mois`,`statut`);

ALTER TABLE `repartitions_paiements`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `paiement_id` (`paiement_id`),
  ADD KEY `regle_financiere_id` (`regle_financiere_id`);

ALTER TABLE `types_frais`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ecole_id` (`ecole_id`),
  ADD KEY `annee_scolaire_id` (`annee_scolaire_id`,`statut`);

ALTER TABLE `utilisateurs`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nom_utilisateur` (`nom_utilisateur`),
  ADD UNIQUE KEY `email` (`email`),
  ADD KEY `ecole_id` (`ecole_id`);



ALTER TABLE `affectations_enseignants`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `annees_scolaires`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

ALTER TABLE `classes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

ALTER TABLE `destinataires_notifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `ecoles`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

ALTER TABLE `eleves`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

ALTER TABLE `enseignants`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `inscriptions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

ALTER TABLE `journal_activites`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

ALTER TABLE `notifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `paiements_eleves`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `paiements_enseignants`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `presences_enseignants`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `regles_financieres`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `remunerations_enseignants`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `repartitions_paiements`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `types_frais`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `utilisateurs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;





ALTER TABLE `affectations_enseignants`
  ADD CONSTRAINT `affectations_enseignants_ibfk_1`
    FOREIGN KEY (`enseignant_id`) REFERENCES `enseignants` (`id`),
  ADD CONSTRAINT `affectations_enseignants_ibfk_2`
    FOREIGN KEY (`classe_id`) REFERENCES `classes` (`id`),
  ADD CONSTRAINT `affectations_enseignants_ibfk_3`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`);

ALTER TABLE `annees_scolaires`
  ADD CONSTRAINT `annees_scolaires_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`) ON DELETE CASCADE;

ALTER TABLE `classes`
  ADD CONSTRAINT `classes_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`),
  ADD CONSTRAINT `classes_ibfk_2`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`);

ALTER TABLE `destinataires_notifications`
  ADD CONSTRAINT `destinataires_notifications_ibfk_1`
    FOREIGN KEY (`notification_id`) REFERENCES `notifications` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `destinataires_notifications_ibfk_2`
    FOREIGN KEY (`utilisateur_id`) REFERENCES `utilisateurs` (`id`) ON DELETE CASCADE;

ALTER TABLE `eleves`
  ADD CONSTRAINT `eleves_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`);

ALTER TABLE `enseignants`
  ADD CONSTRAINT `enseignants_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`),
  ADD CONSTRAINT `enseignants_ibfk_2`
    FOREIGN KEY (`utilisateur_id`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `inscriptions`
  ADD CONSTRAINT `inscriptions_ibfk_1`
    FOREIGN KEY (`eleve_id`) REFERENCES `eleves` (`id`),
  ADD CONSTRAINT `inscriptions_ibfk_2`
    FOREIGN KEY (`classe_id`) REFERENCES `classes` (`id`),
  ADD CONSTRAINT `inscriptions_ibfk_3`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`),
  ADD CONSTRAINT `inscriptions_ibfk_4`
    FOREIGN KEY (`decision_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `journal_activites`
  ADD CONSTRAINT `journal_activites_ibfk_1`
    FOREIGN KEY (`utilisateur_id`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `notifications`
  ADD CONSTRAINT `notifications_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `notifications_ibfk_2`
    FOREIGN KEY (`cree_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `paiements_eleves`
  ADD CONSTRAINT `paiements_eleves_ibfk_1`
    FOREIGN KEY (`inscription_id`) REFERENCES `inscriptions` (`id`),
  ADD CONSTRAINT `paiements_eleves_ibfk_2`
    FOREIGN KEY (`type_frais_id`) REFERENCES `types_frais` (`id`),
  ADD CONSTRAINT `paiements_eleves_ibfk_3`
    FOREIGN KEY (`encaisse_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `paiements_eleves_ibfk_4`
    FOREIGN KEY (`annule_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `paiements_enseignants`
  ADD CONSTRAINT `paiements_enseignants_ibfk_1`
    FOREIGN KEY (`remuneration_id`) REFERENCES `remunerations_enseignants` (`id`),
  ADD CONSTRAINT `paiements_enseignants_ibfk_2`
    FOREIGN KEY (`paye_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `presences_enseignants`
  ADD CONSTRAINT `presences_enseignants_ibfk_1`
    FOREIGN KEY (`enseignant_id`) REFERENCES `enseignants` (`id`),
  ADD CONSTRAINT `presences_enseignants_ibfk_2`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`),
  ADD CONSTRAINT `presences_enseignants_ibfk_3`
    FOREIGN KEY (`enregistre_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `regles_financieres`
  ADD CONSTRAINT `regles_financieres_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`),
  ADD CONSTRAINT `regles_financieres_ibfk_2`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`),
  ADD CONSTRAINT `regles_financieres_ibfk_3`
    FOREIGN KEY (`cree_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `remunerations_enseignants`
  ADD CONSTRAINT `remunerations_enseignants_ibfk_1`
    FOREIGN KEY (`enseignant_id`) REFERENCES `enseignants` (`id`),
  ADD CONSTRAINT `remunerations_enseignants_ibfk_2`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`),
  ADD CONSTRAINT `remunerations_enseignants_ibfk_3`
    FOREIGN KEY (`valide_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

ALTER TABLE `repartitions_paiements`
  ADD CONSTRAINT `repartitions_paiements_ibfk_1`
    FOREIGN KEY (`paiement_id`) REFERENCES `paiements_eleves` (`id`),
  ADD CONSTRAINT `repartitions_paiements_ibfk_2`
    FOREIGN KEY (`regle_financiere_id`) REFERENCES `regles_financieres` (`id`) ON DELETE SET NULL;

ALTER TABLE `types_frais`
  ADD CONSTRAINT `types_frais_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`),
  ADD CONSTRAINT `types_frais_ibfk_2`
    FOREIGN KEY (`annee_scolaire_id`) REFERENCES `annees_scolaires` (`id`);

ALTER TABLE `utilisateurs`
  ADD CONSTRAINT `utilisateurs_ibfk_1`
    FOREIGN KEY (`ecole_id`) REFERENCES `ecoles` (`id`);
