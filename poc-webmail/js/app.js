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
  ABX.Providers.charge(St.ui.providers);
  const gen = C.engendre();
  C.applique();
  C.recompte();

  /* Un onglet dont le message a disparu (corbeille vidée) ne se restaure pas. */
  const AUTONOMES = { compo:1, admin:1, pj:1, page:1 };
  St.ui.tabs = (St.ui.tabs || []).filter(t => AUTONOMES[t.type] || C.par(t.id));
  if (!St.ui.tabs.some(t => t.key === St.ui.tab))
    St.ui.tab = St.ui.tabs.length ? St.ui.tabs[0].key : null;
  if (!repris) St.ui.ouverts.fournisseur = true;

  App.peindre("all");

  ABX.log("Amorçage — " + gen.n + " messages engendrés en " + gen.ms + " ms",
`-- rien à charger : le corpus est reconstruit, seul le rattachement était stocké.
-- Côté serveur c'est l'inverse : le message est le fait durable, et c'est le
-- rattachement qui bouge — mais le partage des rôles est le même.`,
    "le POC ne persiste que " + Object.keys(St.ratt).length + " ligne(s) de rattachement + " +
    St.crees.length + " message(s) écrit(s), soit " + St.tailleKo() + " ko");
  ABX.Controllers.Nav.logCompteurs();
  ABX.Controllers.Tabs.logRestauration(St.ui.tabs.filter(t => t.type === "msg").length);
})(window.ABX = window.ABX || {});
