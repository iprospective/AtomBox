/* LES RACCOURCIS CLAVIER (F111, D112).

   Une SEULE table : elle décide ce que fait chaque touche ET ce que dit l'aide. Deux
   listes auraient divergé au premier ajout — et une aide qui ment sur un raccourci est
   pire que pas d'aide.

   Trois règles qui évitent les ennuis :
   — on ne capte RIEN pendant une saisie (champ, zone de texte, liste déroulante) sauf
     Échap : sinon écrire « ce serait » archiverait le message ;
   — on ne capte RIEN avec Ctrl / Cmd / Alt : ces combinaisons appartiennent au
     navigateur, les lui prendre est une faute d'hôte ;
   — un raccourci qui n'a pas d'objet ne fait rien, en silence. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom;
  const App = () => ABX.Controllers.App, Tabs = () => ABX.Controllers.Tabs;
  const List = () => ABX.Controllers.List, Compose = () => ABX.Controllers.Compose;
  const Msg = () => ABX.MessageService;

  /* le message de l'onglet actif — ce sur quoi porte un geste sans souris */
  const courant = () => {
    const ui = ABX.Store.ui, t = ui.tabs.find(x => x.key === ui.tab);
    return t && t.type === "msg" ? ABX.Api.cache.message(t.id) : null;
  };
  const saisie = e => {
    const n = e && e.target, tag = n && n.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (n && n.isContentEditable);
  };
  /* parcourir la liste : le message suivant s'ouvre en onglet PROVISOIRE, comme un clic
     simple — parcourir vingt messages ne laisse pas vingt onglets derrière soi */
  const bouger = pas => {
    const l = List().messages(); if (!l.length) return;
    const m = courant();
    const i = m ? l.findIndex(x => x.id === m.id) : -1;
    const j = i < 0 ? (pas > 0 ? 0 : l.length - 1) : Math.min(l.length - 1, Math.max(0, i + pas));
    Tabs().ouvrir({ type: "msg", id: l[j].id }, true);
    if (App().MOBILE()) App().setVue("detail");
  };
  const sur = geste => () => { const m = courant(); if (m) Msg()[geste](m); };
  const ecrire = (mode) => () => { const m = courant(); if (m || mode === "new") Compose().demarrer(mode, m); };

  const TABLE = [
    { touche: "/",      contexte: "global",  libelle: "chercher",                 fait: () => { const n = D.byId("gsearch"); if (n && n.focus) n.focus(); } },
    { touche: "c",      contexte: "global",  libelle: "nouveau message",          fait: () => Compose().demarrer("new", null) },
    { touche: "?",      contexte: "global",  libelle: "cette aide",               fait: () => Raccourcis.aide() },
    { touche: "Escape", contexte: "global",  libelle: "fermer l'aide ou la recherche", fait: () => Raccourcis.fermer() },
    { touche: "j",      contexte: "liste",   libelle: "message suivant",          fait: () => bouger(+1) },
    { touche: "k",      contexte: "liste",   libelle: "message précédent",        fait: () => bouger(-1) },
    { touche: "e",      contexte: "message", libelle: "marquer traité",           fait: sur("traiter") },
    { touche: "a",      contexte: "message", libelle: "archiver",                 fait: sur("archiver") },
    { touche: "u",      contexte: "message", libelle: "remettre dans la file",    fait: sur("refile") },
    { touche: "#",      contexte: "message", libelle: "mettre à la corbeille",    fait: sur("corbeille") },
    { touche: "r",      contexte: "message", libelle: "répondre",                 fait: ecrire("rep") },
    { touche: "R",      contexte: "message", libelle: "répondre à tous",          fait: ecrire("reptous") },
    { touche: "f",      contexte: "message", libelle: "transférer",               fait: ecrire("tr") },
  ];

  const Raccourcis = {
    TABLE,
    ouverte: false,

    /* rend la touche pressée, ou null si l'événement ne nous appartient pas */
    touche(e) {
      if (!e || e.ctrlKey || e.metaKey || e.altKey) return null;
      if (saisie(e) && e.key !== "Escape") return null;
      return e.key;
    },

    traiter(e) {
      const k = Raccourcis.touche(e); if (k === null) return false;
      const r = TABLE.find(x => x.touche === k);
      if (!r) return false;
      if (e.preventDefault) e.preventDefault();
      r.fait();
      return true;
    },

    aide() { Raccourcis.ouverte = !Raccourcis.ouverte; Raccourcis.peindre(); },
    fermer() {
      if (Raccourcis.ouverte) { Raccourcis.ouverte = false; Raccourcis.peindre(); return; }
      if (App().qOuvert && App().qOuvert()) App().setQ(false);
    },
    peindre() {
      const el = D.byId("raccourcis"); if (!el) return;
      el.innerHTML = Raccourcis.ouverte ? ABX.Views.Raccourcis.render(TABLE) : "";
      el.hidden = !Raccourcis.ouverte;
      const f = D.byId("rac_fermer");
      if (f) f.onclick = () => { Raccourcis.ouverte = false; Raccourcis.peindre(); };
    },

    brancher() { addEventListener("keydown", Raccourcis.traiter); },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Raccourcis = Raccourcis;
})(window.ABX = window.ABX || {});
