
import os

import mysql.connector
from mysql.connector import Error


def obtenir_connexion():
    if os.environ.get("APP_ENV", "development").lower() == "production":
        variables_requises = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
        manquantes = [nom for nom in variables_requises if not os.environ.get(nom)]
        if manquantes:
            raise RuntimeError(
                "Configuration MySQL de production incomplète: " + ", ".join(manquantes)
            )

    try:
        connexion = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "gestion_ecole_primaire"),
        )
        return connexion

    except Error as erreur:
        print(f"Connexion MySQL impossible ({erreur.__class__.__name__}).")
        return None
