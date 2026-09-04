/* AMORÇAGE — le seul fichier qui a le droit de tout connaître.

   Ordre : charger le delta, engendrer le corpus, rejouer le delta dessus,
   compter, peindre. Le corpus n'est jamais lu depuis le stockage : il est
   reconstruit. C'est la démonstration que l'état d'un webmail tient dans le
   rattachement, pas dans le message (D036). */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, C = ABX.Corpus, App = ABX.Controllers.App;

  /* ---- réactions du bus ---------------------------------------------------
     Les services ne peignent rien ; ils émettent, et la conséquence est ici. */
  ABX.Bus.on("corpus:changed",   () => App.peindre("all"));
  ABX.Bus.on("querylog:changed", () => App.peindre("q"));

  /* ---- en-tête ------------------------------------------------------------ */
  D.byId("btheme").onclick = () => {
    const r = document.documentElement;
    const cur = r.getAttribute("data-theme")
      || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
    r.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
  };
  D.byId("bq").onclick   = () => App.setQ(!App.qOuvert());
  D.byId("bnew").onclick = () => ABX.Controllers.Compose.demarrer("new", null);
  D.byId("badmin").onclick = () => ABX.Controllers.Admin.ouvrir(St.ui.adminVolet);
  D.byId("bpj").onclick = () => ABX.Controllers.Admin.ouvrirPJ();
  document.querySelectorAll(".pocnav [data-page]").forEach(b =>
    b.onclick = () => ABX.Controllers.Pages.ouvrir(b.dataset.page));
  /* La V0 (D140) : un interrupteur. Tout ce qui demande une base rend vide, rien
     n'est réécrit — on repeint, c'est tout. */
  const bv0 = D.byId("pocv0");
  if (bv0) {
    const etat = () => bv0.classList.toggle("on", ABX.V0());
    etat();
    bv0.onclick = () => { St.ui.jalon = ABX.V0() ? null : 0; St.save(); etat(); App.peindre(); };
  }
  D.byId("breset").onclick = () => {
    if (!confirm("Oublier l'état local (lectures, archivages, corbeille, brouillons, onglets) "
               + "et repartir des fixtures ?")) return;
    St.oublier(); location.reload();
  };
  D.byId("bnav").onclick = () => App.MOBILE() ? App.setVue("nav")
    : (D.byId("main").classList.contains("navopen") ? App.fermerNav() : App.ouvrirNav());
  D.byId("scrim").onclick = () => { App.fermerNav(); App.setQ(false); };

  D.byId("gsearch").oninput = e => {
    if (e.target.value.length !== 3) return;
    ABX.log("Recherche globale plein texte",
`SELECT m.comm_id, ts_rank(m.corps_tsv, plainto_tsquery('french', :q)) AS rang
  FROM rattachement r JOIN comm m USING (comm_id)
 WHERE r.compte_id = :moi                      -- la portée d'abord (D036)
   AND m.corps_tsv @@ plainto_tsquery('french', :q)
   AND r.sorti_le > now() - interval '2 years'  -- fenêtre par défaut : sans elle, pas d'élagage
 ORDER BY rang DESC LIMIT 50;`,
      "GIN sur corps_tsv, chaud sur la zone active seulement (D034) — archives sur disque lent");
  };

  addEventListener("keydown", e => { if (e.key === "Escape" && App.qOuvert()) App.setQ(false); });
  addEventListener("resize", () => { if (!App.TABLET()) App.fermerNav();
    if (!App.MOBILE()) D.byId("main").dataset.vue = "liste"; });
  try { if (localStorage.getItem("abx.q") === "0") App.setQ(false); } catch (e) {}

  /* ---- amorçage ----------------------------------------------------------- */
  const repris = St.charge();
  if (St.perime) ABX.log("Stockage d'une version antérieure oublié",
`-- le delta local (rattachements, brouillons, réglages) était d'un schéma antérieur :
-- il n'est pas migré, il est jeté. Le corpus est reconstruit ; rien du produit n'est perdu.`,
    "un état de simulation ne se migre pas ; un état de produit vivrait côté serveur");
  ABX.Providers.charge(St.ui.providers);
  /* MODE POC (D141) : le corpus engendré existe, on l'amorce. En mode produit
     ces trois lignes n'ont pas d'objet — Corpus n'est pas chargé — et l'API
     réelle répond aux mêmes appels. */
  const gen = C ? (C.engendre(), C.applique(), C.recompte(), C) && { n: C.tous.length, ms: 0 } : { n: 0, ms: 0 };
  /* le journal des requêtes OBSERVE la couche d'accès ; il n'est appelé à la main nulle part */
  if (ABX.QueryLog && ABX.Api.on) ABX.Api.on(a => { if (a.ms > 0) ABX.QueryLog.mesure && ABX.QueryLog.mesure(a); });

  /* Les onglets sont restaurés TELS QUELS (D141) : au démarrage le cache de la
     couche d'accès est vide — un onglet de message ira chercher son message
     quand il se peindra, et dira « n'existe plus » si la réponse est 404. C'est
     le comportement du produit ; l'ancien filtre lisait le corpus engendré. */
  St.ui.tabs = St.ui.tabs || [];
  if (!St.ui.tabs.some(t => t.key === St.ui.tab))
    St.ui.tab = St.ui.tabs.length ? St.ui.tabs[0].key : null;
  if (!repris) St.ui.ouverts.fournisseur = true;

  /* les référentiels arrivent par promesse (D141) ; on peint quand on les a.
     En POC c'est immédiat ; en prod c'est le premier aller-retour du produit. */
  /* référentiels PUIS compteurs PUIS peinture : l'arborescence a besoin des deux
     avant de s'afficher — sinon elle montre « 0 / 0 » partout (D141) */
  ABX.pret = ABX.Ref.charger().then(() => ABX.Api.compteurs()).then(() => App.peindre("all")).then(() => true)
    /* l'API peut être indisponible (réseau, serveur arrêté) : l'interface TIENT —
       arborescence vide, liste qui le dit — et ne lève rien. C'est du produit
       (D141), et c'est ce que le harnais vérifie en mode produit sans réseau. */
    .catch(e => { App.peindre("nav"); App.peindre("tabs");
      D.paint("list", `<div class="empty">Service indisponible.<br><small>${
        String(e && e.message || e).replace(/</g, "&lt;")}</small></div>`);
      return false; });

  ABX.log("Amorçage — " + gen.n + " messages engendrés en " + gen.ms + " ms",
`-- rien à charger : le corpus est reconstruit, seul le rattachement était stocké.
-- Côté serveur c'est l'inverse : le message est le fait durable, et c'est le
-- rattachement qui bouge — mais le partage des rôles est le même.`,
    "le POC ne persiste que " + Object.keys(St.ratt).length + " ligne(s) de rattachement + " +
    St.crees.length + " message(s) écrit(s), soit " + St.tailleKo() + " ko");
  ABX.Controllers.Nav.logCompteurs();
  ABX.Controllers.Tabs.logRestauration(St.ui.tabs.filter(t => t.type === "msg").length);
})(window.ABX = window.ABX || {});
