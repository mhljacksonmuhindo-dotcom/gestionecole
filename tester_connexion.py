
from database import obtenir_connexion

connexion = obtenir_connexion()

if connexion and connexion.is_connected():
    print("Connexion à MySQL réussie !")
    print("Base de données : gestion_ecole_primaire")
    connexion.close()
else:
    print("Échec de connexion. Vérifie que MySQL est démarré dans XAMPP.")
