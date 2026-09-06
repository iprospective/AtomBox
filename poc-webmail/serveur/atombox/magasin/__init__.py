"""Le magasin d'octets : une interface (Magasin), une implémentation fichiers (ab/cd/<id>, D145).
Une implémentation objet (S3-compatible) garde la même clé — c'est ce que D161 réserve aux
grosses infrastructures : le chemin est l'identifiant, le support est un réglage."""
from .magasin import Magasin, empreinte
