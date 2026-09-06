"""LES CONTRÔLEURS (D158) — une classe par ressource, une action par route de routes.yml."""
from .session import SessionControleur
from .etat import EtatControleur

CONTROLEURS = [SessionControleur, EtatControleur]
