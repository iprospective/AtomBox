"""Le harnais teste le code du répertoire d'OÙ ON LE LANCE. Rien d'autre.

Le venv est installé en `pip install -e` : son chemin pointe le worktree où l'installation a été
faite. Un autre worktree qui emprunte ce venv — c'est le cas de toute branche de ticket — importe
alors le code du PREMIER, et son harnais devient un théâtre : il passe au vert sur du code qu'on
n'a pas écrit. Constaté sur RM3165 : deux routes neuves, une table de contrôle qui les annonçait,
et un 405 à l'appel, parce que pytest exécutait le serveur d'à côté.

On met donc la racine du worktree EN TÊTE de sys.path, avant tout ce que le venv déclare.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) in sys.path:
    sys.path.remove(str(RACINE))
sys.path.insert(0, str(RACINE))
