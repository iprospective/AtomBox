"""LA SYNCHRONISATION DES ÉTATS AVEC IMAP (F113 — D140b, D043).

En V0, **IMAP reste la vérité** : ce qu'un utilisateur fait dans Thunderbird ou Roundcube doit se
voir dans AtomBox, et réciproquement. Deux sens, deux mécanismes :

- **montante** (AtomBox → IMAP) : un geste dans le webmail écrit le rattachement, émet un
  événement `rattachement.change`, et le processus des tâches pose le STORE ou le MOVE. Hors
  processus, au moins une fois, avec tentatives — parce qu'un serveur IMAP injoignable ne doit
  pas faire échouer un clic (D161) ;
- **descendante** (IMAP → AtomBox) : à chaque relève, le démon lit les FLAGS des messages qu'il
  connaît et met à jour `lu_le` et `drapeau`.

La BOUCLE est le piège de tout miroir : appliquer un changement venu d'IMAP ne doit pas le
renvoyer à IMAP. Un jeton de contexte (`descendante()`) le dit à l'émetteur, qui se tait.
"""
from .sync import descendante, en_descendante, etat_imap, appliquer_descendante, drapeaux_voulus
