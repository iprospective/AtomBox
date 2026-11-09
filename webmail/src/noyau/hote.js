/* LA PAGE HÔTE du webmail intégré (RM3548, F151) — ce qu'elle sait faire pour nous, et le canal pour le lui demander.

   Intégré dans une application (Dolibarr : la page « Courrier » du module), le webmail est sur SA origine : il ne voit ni
   la session ni le jeton de l'application, et ne doit pas les voir. Un geste qui écrit chez elle — ranger une pièce jointe
   dans les documents d'un objet — se DEMANDE donc à la page hôte, qui le fait avec les droits de son utilisateur.

   Le dialogue (postMessage) :
     webmail → hôte   { type: "atombox:pret" }                       ne porte rien : l'hôte répond à SON origine vérifiée
     hôte → webmail   { type: "atombox:hote", gestes: ["ranger-pj"] } on retient l'origine et les gestes annoncés
     webmail → hôte   { type: "atombox:ranger-pj", rid, msg, pj, axe, val }   à cette origine-là seulement
     hôte → webmail   { type: "atombox:ranger-pj:resultat", rid, ok, nom, erreur, objet }

   N'est écouté que le cadre parent ; une fois l'origine de l'hôte connue, une autre origine est ignorée. Le webmail
   n'accepte d'être affiché que par une application déclarée (frame-ancestors, D108) : le parent est elle. */
(function (ABX) {
  "use strict";
  const H = { origine: null, gestes: [], attente: {}, n: 0, DELAI: 30000 };
  /** le cadre parent (la page hôte), ou null hors cadre — remplaçable : le harnais de test y branche un faux parent */
  H.cadre = () => (typeof window !== "undefined" && window.parent && window.parent !== window) ? window.parent : null;
  const parent = () => H.cadre();

  /** l'hôte a-t-il annoncé ce geste ? */
  H.peut = g => !!H.origine && H.gestes.includes(g);

  /** pur : traite un message reçu ; rend vrai s'il a été pris en compte */
  H.recevoir = e => {
    const d = (e && e.data) || {};
    if (!e || e.source !== parent()) return false;
    if (d.type === "atombox:hote" && Array.isArray(d.gestes)) {
      if (H.origine && H.origine !== e.origin) return false;        // l'hôte ne change pas d'origine en cours de route
      const neuf = !H.origine;
      H.origine = e.origin; H.gestes = d.gestes.map(String);
      if (neuf && ABX.Bus) ABX.Bus.emit("corpus:changed", { hote: H.gestes });   // les gestes offerts apparaissent
      return true;
    }
    if (d.type === "atombox:ranger-pj:resultat" && e.origin === H.origine) {
      const fin = H.attente[d.rid]; if (!fin) return false;
      delete H.attente[d.rid]; fin(d); return true;
    }
    return false;
  };

  /** à l'amorçage, en mode intégré seulement : on écoute, puis on se dit prêt */
  H.demarrer = () => {
    const p = parent();
    if (!p || !(ABX.Session && ABX.Session.integre())) return false;
    window.addEventListener("message", H.recevoir);
    p.postMessage({ type: "atombox:pret" }, "*");
    return true;
  };

  /** demande à l'hôte de ranger une pièce jointe dans les documents de l'objet d'un tag ; rend une promesse du résultat */
  H.ranger = ({ msg, pj, axe, val }) => new Promise(fin => {
    const p = parent();
    if (!p || !H.peut("ranger-pj")) return fin({ ok: false, erreur: "l'application hôte ne propose pas ce geste" });
    const rid = "r" + (++H.n);
    H.attente[rid] = fin;
    p.postMessage({ type: "atombox:ranger-pj", rid, msg: String(msg), pj: String(pj), axe: String(axe), val: String(val) }, H.origine);
    setTimeout(() => { if (H.attente[rid]) { delete H.attente[rid]; fin({ ok: false, erreur: "pas de réponse de l'application" }); } }, H.DELAI);
  });

  ABX.Hote = H;
})(window.ABX = window.ABX || {});
