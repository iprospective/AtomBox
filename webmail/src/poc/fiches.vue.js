/* LES FICHES DU CDC (RM3627, étude RM3625 § 7) — une fiche par objet, lue dans l'index du CDC atomique.

   La fiche d'une FONCTIONNALITÉ dit le quoi (libellé, état, version, tickets, dépendances), puis
   TOUTE LA CHAÎNE DES DÉCISIONS qui la fondent : chaque décision d'appui, son texte, et ce sur quoi
   elle repose à son tour (ce qu'elle amende, complète, prolonge, précise, réalise, remplace) —
   dépliable niveau par niveau, au clic. Une décision amendée le dit.
   La fiche d'une DÉCISION dit son texte, ce sur quoi elle repose ET ce qui repose sur elle.
   Tout identifiant est un lien vers sa fiche. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt;

  const ASCENDANCE = [["amende", "amende"], ["remplace", "remplace"], ["complete", "complète"],
                      ["prolonge", "prolonge"], ["precise", "précise"], ["realise", "réalise"]];
  const INVERSES = [["amendee_par", "amendée par"], ["remplacee_par", "remplacée par"], ["completee_par", "complétée par"],
                    ["prolongee_par", "prolongée par"], ["precisee_par", "précisée par"], ["realisee_par", "réalisée par"],
                    ["tranchee_par", "tranchée par"], ["fonde", "fonde"], ["necessaire_a", "nécessaire à"],
                    ["conseils", "conseils"], ["traitee_par", "traitée par"]];
  const ETATS = { valide: "✅ validée", propose: "🟡 proposée", invalide: "❌ invalidée", reserve: "⏸ en réserve",
                  attente: "🕐 ouverte", amendee: "✏️ amendée", remplacee: "↪ remplacée", tranchee: "✅ tranchée",
                  traitee: "✅ traitée" };

  const idx = () => ABX.CDC_ATOME || null;
  const liste = v => (v == null ? [] : Array.isArray(v) ? v : [v]);
  const cible = v => (v && typeof v === "object" ? { id: v.id, partie: v.partie } : { id: v, partie: null });

  function objet(id) {
    const I = idx(); if (!I || !id) return null;
    return I.objets[id] || I.objets[(I.alias || {})[id]] || null;
  }

  function lien(id, texte) {
    const o = objet(id);
    if (!o) return F.esc(id);
    return `<a href="#" class="cdc-fiche" data-fiche="${F.esc(o.id)}" title="${F.esc(o.titre || o.libelle || "")}">${F.esc(texte || o.id)}</a>`;
  }

  const etat = o => ETATS[o.etat_calcule] || ETATS[o.etat] || F.esc(o.etat || "");
  const dates = o => [o.cree_le && "créée le " + String(o.cree_le).slice(0, 10), o.modifie_le && "modifiée le " + String(o.modifie_le).slice(0, 10)]
    .filter(Boolean).join(" · ");
  const texte = c => (ABX.Markdown && ABX.Markdown.rendre ? ABX.Markdown.rendre(c || "") : `<pre>${F.esc(c || "")}</pre>`);

  /* une décision et son ascendance : <details>, ouvert au premier niveau, replié ensuite */
  function noeud(id, relation, partie, profondeur, vus) {
    const o = objet(id);
    if (!o) return "";
    const deja = vus.has(o.id);
    vus.add(o.id);
    const tete = `${relation ? `<span class="hint">${F.esc(relation)}${partie ? " " + F.esc(partie) : ""} →</span> ` : ""}
      ${lien(o.id)} <b>${F.esc(o.titre_court || o.titre || "")}</b> <span class="hint">${etat(o)}</span>`;
    if (deja) return `<div class="fiche-noeud">${tete} <span class="hint">(déjà plus haut)</span></div>`;
    const enfants = ASCENDANCE.flatMap(([r, lib]) => liste(o[r]).map(v => { const c = cible(v); return noeud(c.id, lib, c.partie, profondeur + 1, vus); })).join("");
    return `<details class="fiche-noeud"${profondeur === 0 ? " open" : ""}><summary>${tete}</summary>
      <div class="fiche-texte">${texte(o.corps)}</div>${enfants}</details>`;
  }

  function relations(o, champs) {
    return champs.map(([k, lib]) => {
      const v = liste(o[k] || (o.inverses || {})[k]);
      return v.length ? `<div><span class="hint">${F.esc(lib)} :</span> ${v.map(x => lien(cible(x).id) + (cible(x).partie ? " " + F.esc(cible(x).partie) : "")).join(", ")}</div>` : "";
    }).join("");
  }

  function ficheFonctionnalite(o) {
    const inv = o.inverses || {};
    const bloque = liste(o.questions).map(q => objet(cible(q).id)).filter(q => q && !q.etat_calcule && q.etat === "attente");
    const appuis = liste(o.appuis);
    return `<div class="fiche-tete"><span class="fiche-id">${F.esc(o.id)}</span> <b>${F.esc(o.libelle || "")}</b></div>
      <div class="hint">${etat(o)} · ${F.esc(o.version || "sans version")} · ${F.esc(o.domaine || "")}${
        liste(o.tickets).length ? " · tickets " + liste(o.tickets).map(F.esc).join(", ") : ""}${dates(o) ? " · " + dates(o) : ""}</div>
      ${o.note ? `<p>${F.esc(o.note)}</p>` : ""}
      ${relations(o, [["depend_de", "dépend de"]])}${relations({ inverses: inv }, [["necessaire_a", "nécessaire à"]])}
      <h4>Pourquoi : la chaîne des décisions (${appuis.length})</h4>
      ${appuis.length ? appuis.map(v => noeud(cible(v).id, null, null, 0, new Set())).join("") : `<div class="hint">Aucune décision rattachée.</div>`}
      ${bloque.length ? `<h4>Ce qui la bloque</h4>${bloque.map(q => `<div>${lien(q.id)} ${F.esc(q.titre || "")}</div>`).join("")}` : ""}`;
  }

  function ficheDecision(o) {
    const vus = new Set([o.id]);
    const ascend = ASCENDANCE.flatMap(([r, lib]) => liste(o[r]).map(v => noeud(cible(v).id, lib, cible(v).partie, 1, vus))).join("");
    return `<div class="fiche-tete"><span class="fiche-id">${F.esc(o.id)}</span> <b>${F.esc(o.titre || "")}</b></div>
      <div class="hint">${etat(o)}${o.arbitre ? " · arbitrée par " + F.esc(o.arbitre) : ""}${dates(o) ? " · " + dates(o) : ""}${
        liste(o.ex).length ? " · ex " + liste(o.ex).map(F.esc).join(", ") : ""}</div>
      ${relations(o, [["tranche", "tranche"], ["traite", "traite"]])}
      ${relations({ inverses: o.inverses || {} }, INVERSES)}
      <div class="fiche-texte">${texte(o.corps)}</div>
      ${ascend ? `<h4>Ce sur quoi elle repose</h4>${ascend}` : ""}`;
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.Fiche = {
    objet, lien,
    render(id) {
      const o = objet(id);
      if (!o) return `<div class="box fiche"><div class="hint">${F.esc(id)} : aucune fiche.</div></div>`;
      const corps = o.type === "fonctionnalite" ? ficheFonctionnalite(o)
        : o.type === "decision" || o.type === "conseil" ? ficheDecision(o)
        : `<div class="fiche-tete"><span class="fiche-id">${F.esc(o.id)}</span> <b>${F.esc(o.titre || "")}</b></div>
           <div class="hint">${etat(o)}${dates(o) ? " · " + dates(o) : ""}</div>
           ${relations({ inverses: o.inverses || {} }, INVERSES)}<div class="fiche-texte">${texte(o.corps)}</div>`;
      return `<div class="box fiche"><div class="hint"><a href="#" class="cdc-fiche" data-fiche="">‹ fermer la fiche</a></div>${corps}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
