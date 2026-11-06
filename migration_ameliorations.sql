

USE `gestion_ecole_primaire`;

-- 1. Table inscriptions 
ALTER TABLE `inscriptions`
  ADD COLUMN `decision_fin_annee` ENUM('admis', 'redouble', 'a_traiter') DEFAULT NULL AFTER `statut`,
  ADD COLUMN `date_decision` DATE DEFAULT NULL AFTER `decision_fin_annee`,
  ADD COLUMN `decision_par` INT(11) DEFAULT NULL AFTER `date_decision`,
  ADD COLUMN `motif_retrait` TEXT DEFAULT NULL AFTER `observations`,
  ADD COLUMN `date_retrait` DATE DEFAULT NULL AFTER `motif_retrait`;


ALTER TABLE `inscriptions`
  ADD CONSTRAINT `fk_inscriptions_decision_par`
  FOREIGN KEY (`decision_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

-- 2. Table paiements_eleves 
ALTER TABLE `paiements_eleves`
  ADD COLUMN `motif_annulation` TEXT DEFAULT NULL AFTER `statut`,
  ADD COLUMN `annule_par` INT(11) DEFAULT NULL AFTER `motif_annulation`,
  ADD COLUMN `date_annulation` DATETIME DEFAULT NULL AFTER `annule_par`;


ALTER TABLE `paiements_eleves`
  ADD CONSTRAINT `fk_paiements_annule_par`
  FOREIGN KEY (`annule_par`) REFERENCES `utilisateurs` (`id`) ON DELETE SET NULL;

-- 3. Table utilisateurs 
ALTER TABLE `utilisateurs`
  ADD COLUMN `doit_changer_mdp` TINYINT(1) DEFAULT 0 AFTER `derniere_connexion`;
