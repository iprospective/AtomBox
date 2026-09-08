/* LE SERVEUR SIMULÉ — la seule chose qu'on jette (D141).

   Il reçoit ce que req() lui passe — méthode, chemin, corps — et répond
   comme le vrai serveur répondra : les MÊMES formes JSON, les mêmes codes.
   Derrière, il lit le corpus engendré et écrit le delta local ; mais
   l'interface ne le sait pas, et ne doit jamais le savoir.

   Chaque route est écrite ici EXPLICITEMENT (méthode + motif de chemin).
   Écrire le serveur réel, ce sera réécrire ce fichier dans son langage,
   route par route — c'est la spécification exécutable de l'API. */
(function (ABX) {
  "use strict";
  const C = ABX.Corpus, St = ABX.Store, T = ABX.Traces;

  /* ---- représentations : ce que le serveur SERT --------------------------
     L'objet du corpus porte EXACTEMENT les clés du contrat — celles du
     dictionnaire (sujet, from_nom, from_adresse, date_recue, nb_pieces_jointes,
     sorti_le, motif_sortie…). Le serveur le sert tel quel ; les clés « _ »
     (état de session) ne font pas partie du contrat et ne sortent jamais du
     vrai serveur. En POC on rend l'objet lui-même : le cache et le corpus ne
     font qu'un, ce qui est le comportement d'avant — sans plus aucun _m. */
  const rep = m => m;
  const ok = (extra) => Object.assign({ ok: true }, extra || {});

  const dossierDe = p => ({ id: p.dossier, kind: p.kind || (p.dossier && p.dossier.includes(":") ? "virtuel" : "special"), axe: p.axe });

  /* ---- les routes ----------------------------------------------------------- */
  const ROUTES = [
    ["GET", /^\/referentiels$/, () => { const Fx = ABX.Fixtures; return {
      moi: Fx.MOI, speciaux: Fx.SPECIAUX, util: Fx.UTIL, axes: Fx.AXES, valeurs: Fx.valeurs,
      statuts: Fx.STATUTS, vues: Object.keys(C.VUES) }; }],

    /* l'arborescence de l'utilisateur : les compteurs (D078), ses dossiers virtuels
       personnels (D143) et ses épingles (D144) — une seule réponse */
    /* la session (D157) : le serveur simulé ne connaît que poc/poc — ce que le vrai
       serveur fera avec un mot de passe ou un SSO (D063, D150) */
    ["POST", /^\/session$/, (_, __, c) => { c = c || {};
      if (c.utilisateur !== "poc" || c.mot_de_passe !== "poc") throw new Error("POST /session → 401 : identifiants refusés");
      return { jeton: "poc", compte: ABX.Fixtures.MOI }; }],
    ["DELETE", /^\/session$/, () => ok({ fermee: true })],

    ["GET", /^\/arborescence$/, () => ({ compteurs: C.recompte(),
      /* des COPIES : le vrai serveur sérialise, le cache du client ne doit pas partager
         le tableau du store — sinon un push s'y verrait deux fois */
      virtuels: St.virtuels.map(v => ({ ...v })), epingles: (St.ui.epingles || []).slice() })],

    ["GET", /^\/messages$/, (_, p) => {
      const f = dossierDe(p);
      const l = p.tout ? C.vue(f) : C.filtrer(f, p.filtre, p.tri, p.sens, p.statut);
      return { messages: l.map(m => rep(m, false)), total: l.length }; }],

    ["GET", /^\/messages\/([^/]+)\/fil$/, (m) => { const x = C.par(dec(m[1])); if (!x) return null;
      return { messages: C.tous.filter(y => y.thread_id === x.thread_id && y.dossier_origine === x.dossier_origine)
        .sort((a, b) => a.date_recue - b.date_recue).map(y => rep(y, false)) }; }],

    ["GET", /^\/messages\/([^/]+)$/, (m) => { const x = C.par(dec(m[1])); return x ? rep(x, true) : null; }],

    /* le suivi d'envoi (D099) : le POC le simule sur les messages sortants — deux états qui
       se succèdent, pour qu'on voie les deux à l'écran sans serveur */
    ["GET", /^\/envois\/([^/]+)$/, (m) => { const x = C.par(dec(m[1])); if (!x || x.sens !== "out") return null;
      const st = St.envois && St.envois[x.id] || (x._envoiEtat || "remis");
      const dest = (x.destinataires || []).map(a => ({ adresse: a, etat: st === "remis" ? "remis" : "prepare", code: null, mis_a_jour_le: new Date().toISOString() }));
      const DETAIL = { remis: "remis au relais", en_echec: "échec (1 tentative), nouvelle tentative à 12:05 : relais injoignable", en_attente: "en attente de remise au relais" };
      return { comm_id: x.id, sujet: x.sujet, date: new Date(x.date_recue).toISOString(), envoi_id: "e-" + x.id,
               remis_le: st === "remis" ? new Date(x.date_recue).toISOString() : null, etat: st, detail: DETAIL[st] || st,
               tentatives: st === "en_echec" ? 1 : 0, erreur: st === "en_echec" ? "relais injoignable" : null,
               relancable: st !== "remis", destinataires: dest }; }],

    ["POST", /^\/envois\/([^/]+)\/relancer$/, (m) => { const x = C.par(dec(m[1])); if (!x || x.sens !== "out") return null;
      St.envois = St.envois || {}; St.envois[x.id] = "remis"; St.save();
      return ok({ relance: 1, comm_id: x.id, destinataires: x.destinataires || [] }); }],

    /* L'ÉTAT et les RÈGLES : le POC les simule pour que les deux écrans vivent sans serveur.
       Les mêmes formes que le vrai serveur — c'est le contrat qui compte, pas la source. */
    ["GET", /^\/etat$/, () => {
      const dossiers = ABX.Ref.speciaux.filter(x => !x.vue).map((x, i) => ({
        boite: ABX.Ref.moi.boites[0].adresse, dossier: x.label, uid_validity: 1788742784,
        uid_suivant: 100 + i * 37, messages: ABX.Api.cache.compteur(x.id).t, jamais_releve: false }));
      const muettes = (St.filtres || []).filter(f => !f.nb_declenchements).map(f => ({ nom: f.nom }));
      return { quand: new Date().toISOString(), ingestion: dossiers,
        files: { en_attente: 0, en_echec: 1, abandonnes: 0, traites: 128, retard_secondes: 42,
                 prochaine_tentative: new Date(Date.now() + 6e4).toISOString(),
                 plus_vieux_en_attente: new Date(Date.now() - 42e3).toISOString() },
        en_echec: [{ type: "message.a_envoyer", tentatives: 1, erreur: "relais injoignable", cree_le: new Date(Date.now() - 42e3).toISOString() }],
        magasin: { chemin: "/var/lib/atombox/magasin", blobs: C.tous.length + 40,
                   octets_stockes: 41 * 1024 * 1024, octets_bruts: 68 * 1024 * 1024, orphelins: 2, gain: 0.397 },
        contenu: { messages: C.tous.length, pieces_jointes: 312, rattachements: C.tous.length, boites: ABX.Ref.moi.boites.length },
        regles_muettes: muettes, journaux: "/var/log/atombox" }; }],

    ["GET", /^\/etat\/journal$/, (_, p) => {
      const N = ["DEBUG", "INFO", "WARNING", "ERROR"], seuil = N.indexOf((p.niveau || "INFO").toUpperCase());
      const brut = [
        ["INFO", "ingestion", "nouveau 01a07b28 : Devis 4521, de jean@tessier-industries.example, 8 pièce(s)"],
        ["DEBUG", "imap", "FETCH uid 42 : 8214 octets, \\Seen"],
        ["INFO", "auth", "session ouverte pour mathieu (Firefox)"],
        ["WARNING", "imap", "IDLE refusé : reconnexion dans 60 s"],
        ["ERROR", "apps", "événement message.a_envoyer : tentative 1 en échec — relais injoignable"],
        ["INFO", "api", "GET /api/v1/messages → 200 en 12 ms"],
      ];
      const q = (p.filtre || "").toLowerCase();
      const lignes = brut
        .filter(([n, d]) => N.indexOf(n) >= seuil && (!p.domaine || p.domaine === "atombox" || p.domaine === "erreurs" || d === p.domaine))
        .filter(([n, d, m]) => !q || (d + m).toLowerCase().includes(q))
        .filter(([n]) => p.domaine !== "erreurs" || N.indexOf(n) >= 2)
        .map(([niveau, domaine, message], i) => ({ quand: new Date(Date.now() - i * 6e4).toISOString().slice(0, 19).replace("T", " "),
                                                   niveau, domaine, message }));
      return { domaine: p.domaine || "atombox", niveau: p.niveau || "INFO", lignes, fichier: "/var/log/atombox/atombox.log" }; }],

    ["GET", /^\/filtres$/, () => ({ filtres: (St.filtres || []).slice(), total: (St.filtres || []).length,
      champs: ["corps", "destinataire", "dossier", "from", "from_nom", "liste", "nature", "pieces", "sujet", "taille"],
      operateurs: ["commence_par", "contient", "correspond_a", "est", "existe", "finit_par", "inferieur_a", "ne_contient_pas", "superieur_a"],
      actions: ["classer", "marquer_lu", "drapeau", "statut", "corbeille", "indesirable", "arreter", "ignorer"] })],

    ["POST", /^\/filtres$/, (_, __, corps) => { const c = corps || {};
      if (!(c.nom || "").trim()) throw new Error("POST /filtres → 400 : un nom");
      if (!((c.predicat || {}).criteres || []).length) throw new Error("POST /filtres → 400 : au moins un critère");
      St.filtres = St.filtres || [];
      const f = { id: "f" + (++St.seq), nom: c.nom.trim(), ordre: St.filtres.length + 1, actif: c.actif !== false,
                  predicat: c.predicat, action: c.action, portee: c.portee || "compte",
                  nb_declenchements: 0, dernier_declenchement: null, muette: true };
      St.filtres.push(f); St.save();
      return ok({ crees: 1, filtre: f }); }],

    ["PATCH", /^\/filtres\/([^/]+)$/, (m, _, corps) => { const f = (St.filtres || []).find(x => x.id === dec(m[1]));
      if (!f) return null;
      Object.assign(f, corps || {}); St.save();
      return ok({ modifies: 1, filtre: f }); }],

    ["DELETE", /^\/filtres\/([^/]+)$/, (m) => { const i = (St.filtres || []).findIndex(x => x.id === dec(m[1]));
      if (i < 0) return null;
      St.filtres.splice(i, 1); St.save();
      return ok({ supprimes: 1 }); }],

    ["GET", /^\/recherche$/, (_, p) => { const q = (p.q || "").toLowerCase().trim();
      const l = q.length < 2 ? [] : C.tous.filter(m => !m.motif_sortie && m.dossier !== "trash" &&
        ((m.sujet || "").toLowerCase().includes(q) || (m.corps || "").toLowerCase().includes(q) || (m.from_adresse || "").toLowerCase().includes(q) || (m.from_nom || "").toLowerCase().includes(q)));
      return { messages: l.map(m => rep(m, false)), total: l.length, q }; }],

    ["GET", /^\/pieces-jointes$/, () => { const out = [];
      C.tous.forEach(m => (m.pieces_jointes || []).forEach((p, i) => out.push({ m, p, i })));
      return { pieces_jointes: out }; }],

    ["PATCH", /^\/messages\/([^/]+)\/rattachement$/, (m, _, corps) => {
      const x = C.par(dec(m[1])); if (!x) return null;
      St.patch(x, corps || {}); St.save();
      return ok({ modifies: 1, message: rep(x, false) }); }],

    /* réenregistrer un brouillon : le POC garde l'objet et le met à jour, comme le serveur (D089) */
    ["PUT", /^\/messages\/([^/]+)$/, (m, _, corps) => { const x = C.par(dec(m[1])); if (!x) return null;
      Object.assign(x, corps || {}); St.save();
      return ok({ modifies: 1, message: rep(x, true) }); }],

    ["GET", /^\/carnet$/, (_, p) => { const q = (p.q || "").toLowerCase();
      const compte = {};
      C.tous.filter(x => x.sens === "out").forEach(x => (x.destinataires || []).forEach(a => {
        if (q && !a.toLowerCase().includes(q)) return;
        compte[a] = compte[a] || { adresse: a, nom: null, echanges: 0, dernier: null };
        compte[a].echanges++; compte[a].dernier = new Date(x.date_recue).toISOString(); }));
      const l = Object.values(compte).sort((a, b) => b.echanges - a.echanges).slice(0, 50);
      return { carnet: l, total: l.length }; }],

    ["POST", /^\/messages$/, (_, __, corps) => {
      C.ajoute(corps); St.crees.push(corps); St.save();
      return ok({ crees: 1, message: rep(corps, false) }); }],

    ["DELETE", /^\/messages\/([^/]+)\/rattachement$/, (m) => {
      const x = C.par(dec(m[1])); if (!x) return null;
      St.patch(x, { suppr: true }); C.retire(x); St.save();
      return ok({ modifies: 1, detache: true }); }],

    /* un dossier virtuel personnel = un filtre sans action (D075, D143) : une
       conjonction de critères {axe, val?} ; le vrai serveur écrira une ligne de `filtre` */
    ["POST", /^\/dossiers-virtuels$/, (_, __, corps) => {
      const d = { id: "perso:" + (++St.seq), label: ((corps || {}).label || "").trim(),
                  criteres: ((corps || {}).criteres || []).filter(c => c && c.axe)
                    .map(c => ({ axe: c.axe, val: (c.val || "").trim() || undefined })) };
      if (!d.label || !d.criteres.length) throw new Error("POST /dossiers-virtuels → 400 : libellé et au moins un critère");
      St.virtuels.push(d); St.save();
      return ok({ crees: 1, dossier: { ...d } }); }],

    ["DELETE", /^\/dossiers-virtuels\/([^/]+)$/, (m) => {
      const id = dec(m[1]), i = St.virtuels.findIndex(v => v.id === id); if (i < 0) return null;
      St.virtuels.splice(i, 1);
      St.ui.epingles = (St.ui.epingles || []).filter(e => e !== id);   // l'épingle part avec lui (D144)
      St.save();
      return ok({ supprimes: 1 }); }],

    /* un réglage personnel (D106) — la même route que tout paramètre ; le POC ne
       connaît que les épingles (D144) */
    ["PUT", /^\/parametres$/, (_, __, corps) => {
      const c = corps || {};
      if (c.cle !== "epingles") throw new Error("PUT /parametres → 400 : réglage inconnu " + c.cle);
      St.ui.epingles = (c.valeur || []).slice(); St.save();
      return ok({ modifies: 1, parametre: { cle: c.cle, valeur: St.ui.epingles.slice(), portee: "compte" } }); }],
  ];
  const dec = s => decodeURIComponent(s);

  function params(chemin) {
    const i = chemin.indexOf("?"); if (i < 0) return [chemin, {}];
    const p = {}; chemin.slice(i + 1).split("&").forEach(kv => { const [k, v] = kv.split("="); p[dec(k)] = dec(v || ""); });
    return [chemin.slice(0, i), p];
  }

  const ServeurSimule = {
    ROUTES,
    /* même contrat que fetch(...).then(r => r.json()) : un JSON, ou null pour 404 */
    traiter(methode, cheminBrut, corps) {
      const [chemin, p] = params(cheminBrut);
      for (const [meth, motif, fn] of ROUTES) {
        if (meth !== methode) continue;
        const m = chemin.match(motif); if (!m) continue;
        return fn(m, p, corps);
      }
      throw new Error("serveur simulé : route inconnue " + methode + " " + chemin);
    },
    routes: () => ROUTES.map(([m, r]) => m + " " + r.source.replace(/\\\//g, "/").replace(/\^|\$/g, "")),
  };
  ABX.ServeurSimule = ServeurSimule;
})(window.ABX = window.ABX || {});
