/* LE CORPUS — engendré, jamais stocké.

   Tout est produit au démarrage dans un ordre fixe : c'est ce qui le rend
   identique d'une session à l'autre, et donc persistable par simple delta
   (voir core/store.js). Les compteurs de l'arborescence ne sont pas des
   fixtures : ils se CALCULENT en une passe, jamais une requête par dossier (D78). */
(function (ABX) {
  "use strict";
  const P = ABX.PRNG, Fx = ABX.Fixtures, At = ABX.Attachments, St = ABX.Store;

  const dossiers = {};   // folderId -> [messages]
  const parId    = {};   // message_id -> message
  let   tous     = [];
  let   compte   = {};   // folderId -> { t, u }

  function fabriqueMessages(fid, label, n, opt) {
    const out = [], o = opt || {};
    for (let i = 0; i < n; i++) {
      const qui = fid.startsWith("collaborateur") ? label : Fx.pers();
      const dom = ABX.Fmt.slug(label).slice(0, 14) + ".fr";
      const adr = ABX.Fmt.slug(qui).replace(/-/g, ".") + "@" + dom;
      const boite = P.pick(Fx.MOI.boites).adresse;
      const m = {
        id: fid + "/m" + i, fid,
        from: o.sortant ? Fx.MOI.nom : qui,
        mail: o.sortant ? boite : adr,
        to:   o.sortant ? [adr]  : [boite],
        boite,                                    // la boîte qui a REÇU — Q26
        subject: (P.next() < .3 ? "Re: " : "") + P.pick(Fx.SUJETS).replace("{n}", "" + P.int(1000, 9999)),
        body: P.pick(Fx.CORPS),
        date: Date.now() - P.int(0, 300) * 864e5 - P.int(0, 86399) * 1000,
        lu: o.sortant ? true : !(P.next() < .3),
        thread: P.int(1, 4), tags: [],
        sorti: null, motif: null, dossier: null, ref: null, compo: null,
      };
      m.snippet = m.body.split("\n")[2] || "…";
      At.attacher(m);
      const ax = fid.split(":")[0];
      if (Fx.estAxe(ax)) m.tags.push({ axe: ax, val: label, src: "dolibarr-mmi" });
      if (P.next() < .25) m.tags.push({ axe:"projet", val:"RM" + P.int(2800, 2900), src:"redmine-ipro" });
      if (P.next() < .18) m.tags.push({ axe:"type", val:P.pick(["facture","devis","contrat"]), src:"filtre" });
      out.push(m);
    }
    return out.sort((a, b) => b.date - a.date);
  }

  /* Les vues qui ne sont pas des dossiers : elles lisent motif_sortie (D30/D51). */
  const VUES = {
    trash:    m => m.dossier === "trash",
    archives: m => m.motif === "archive" && m.dossier !== "trash",
    traites:  m => m.motif === "traite"  && m.dossier !== "trash",
  };

  const Corpus = {
    dossiers, parId, VUES,
    get tous() { return tous; },
    get compteurs() { return compte; },
    par: id => parId[id],

    engendre() {
      const t0 = Date.now();
      const gen = (fid, label, n, opt) => {
        dossiers[fid] = fabriqueMessages(fid, label, n, opt);
        dossiers[fid].forEach(m => parId[m.id] = m);
      };
      Fx.SPECIAUX.forEach(o => gen(o.id, o.label, o.poids, { sortant: o.sortant }));
      Fx.UTIL.forEach(o => gen(o.id, o.label, o.poids));
      Fx.AXES.forEach(a => Fx.valeurs[a.id].forEach(v => {
        gen(v.id, v.label, v.poids);
        v.last = dossiers[v.id].length ? dossiers[v.id][0].date : 0;
      }));
      Fx.AXES.forEach(a => Fx.valeurs[a.id].sort((x, y) => y.last - x.last));
      tous = Object.values(parId);
      return { n: tous.length, ms: Date.now() - t0 };
    },

    /* Rejoue le delta persisté par-dessus le corpus fraîchement engendré. */
    applique() {
      St.crees.forEach(m => { parId[m.id] = m;
        (dossiers[m.fid] = dossiers[m.fid] || []).unshift(m); });
      Object.entries(St.ratt).forEach(([id, r]) => { const m = parId[id]; if (m) Object.assign(m, r); });
      tous = Object.values(parId).filter(m => !m.suppr);
    },

    ajoute(m) { parId[m.id] = m; tous.push(m);
                (dossiers[m.fid] = dossiers[m.fid] || []).unshift(m); },

    retire(m) { tous = tous.filter(x => x !== m); },

    /* UNE passe sur le corpus pour les ~300 branches de l'arborescence (D78). */
    recompte() {
      compte = {};
      const bump = (k, m) => { (compte[k] = compte[k] || { t:0, u:0 }).t++; if (!m.lu) compte[k].u++; };
      for (const m of tous) {
        if (m.dossier === "trash") { bump("trash", m); continue; }
        if (m.motif) { bump(m.motif === "archive" ? "archives" : "traites", m); continue; }
        const k = m.dossier || m.fid;
        bump(k, m);
        const ax = k.split(":")[0];
        if (Fx.estAxe(ax)) bump("axe:" + ax, m);
      }
      return compte;
    },

    cnt: k => compte[k] || { t:0, u:0 },

    /* Le contenu d'un dossier, avant filtre de liste. */
    vue(folder) {
      if (VUES[folder.id]) return tous.filter(VUES[folder.id]);
      const hors = m => m.dossier !== "trash";
      if (folder.kind === "axe")
        return tous.filter(m => hors(m) && (m.dossier || m.fid).startsWith(folder.axe + ":"));
      return tous.filter(m => hors(m) && (m.dossier || m.fid) === folder.id);
    },

    TRIS: {
      date_desc: (x, y) => y.date - x.date,
      date_asc:  (x, y) => x.date - y.date,
      from:      (x, y) => x.from.localeCompare(y.from),
      subj:      (x, y) => x.subject.localeCompare(y.subject),
      size:      (x, y) => y.size - x.size,
    },

    /* Filtre + tri de la liste. Dans une vue de sortie, « en file » n'a pas de sens. */
    filtrer(folder, filtre, tri) {
      let a = Corpus.vue(folder);
      if (!VUES[folder.id]) a = filtre === "sortis" ? a.filter(m => m.motif) : a.filter(m => !m.motif);
      if (filtre === "non_lus") a = a.filter(m => !m.lu);
      if (filtre === "recents") a = a.filter(m => Date.now() - m.date < 30 * 864e5);
      if (filtre === "pj")      a = a.filter(m => m.pj);
      if (filtre === "lourds")  a = a.filter(m => m.size > 2048);
      return a.slice().sort(Corpus.TRIS[tri] || Corpus.TRIS.date_desc);
    },
  };

  ABX.Corpus = Corpus;
})(window.ABX = window.ABX || {});
