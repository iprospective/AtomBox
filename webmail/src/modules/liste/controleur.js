/* CONTRÔLEUR LISTE — ouverture de dossier, filtres, tris, actions de survol. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, C = ABX.Corpus, M = ABX.MessageService;
  const App = () => ABX.Controllers.App;

  const IDX_TRI = {
    date_desc: ["index (tag_id, sorti_le DESC, comm_id) — tri porté par l'index (D016)", false],
    date_asc:  ["même index parcouru à l'envers", false],
    from_nom:      ["tri NON indexé — tenable seulement parce que la fenêtre est paginée", true],
    subj:      ["tri NON indexé — idem", true],
    taille:      ["tri NON indexé sur taille_octets — idem", true],
  };
  const SQL_TRI = { date_desc:"m.date_reception DESC", date_asc:"m.date_reception ASC",
                    from_nom:"m.from_nom", subj:"m.sujet_normalise", taille:"m.taille_octets DESC" };

  const List = {
    ouvrir(folder) {
      /* Le filtre par défaut dépend de la NATURE du dossier (D166) : une file de travail
         s'ouvre sur « en file », un classement sur « tout ». Sinon un projet dont tout est
         traité s'affiche vide — et c'est justement celui qu'on vient consulter. */
      const classement = ["perso", "virtuel", "abo", "axe"].includes(folder.kind);
      if (classement && (St.ui.filtre === "file" || !St.ui.filtre)) St.ui.filtre = "tous";
      if (!classement && St.ui.filtre === "tous") St.ui.filtre = "file";
      const ui = St.ui;
      ui.folder = folder;
      St.save();
      ABX.Controllers.Nav.peindre();
      /* la liste arrive par promesse ; la trace est journalisée avec ce qui a été servi */
      List.charger().then(() => ABX.Traces.ouvrirDossier(folder, List._cache.length));
      if (App().MOBILE()) App().setVue("liste"); else App().fermerNav();
    },

    logOuverture(folder) {
      const vue = C.VUES[folder.id];
      const where = folder.kind === "special"
          ? (vue ? `r.exit_reason = '${
                     { archives:"archived", traites:"processed", junk:"junk", trash:"deleted" }[folder.id]}'`
                 : `r.boite_id = :boite AND <vue ${folder.id}>`)
        : folder.kind === "user" ? `r.dossier_id = :dossier`
        : folder.kind === "axe"  ? `t.axe_id = :axe            -- récursif : l'axe sans la valeur`
        : folder.kind === "perso" ? `EXISTS (…) AND EXISTS (…)  -- un EXISTS par critère du filtre (D143), conjonction`
        : `t.axe_id = :axe AND t.valeur = :valeur`;
      const jointure = (folder.kind === "virtuel" || folder.kind === "axe")
        ? "\n  JOIN comm_tag mt USING (comm_id) JOIN tag t USING (tag_id)" : "";
      ABX.log("Ouvrir « " + folder.label + " »",
`-- la liste ne touche QUE le tronc : aucune jointure vers comm_email (D138)
-- l'état de LECTURE est personnel (D175) : une jointure externe, creuse par nature
SELECT m.comm_id, m.from_nom, m.sujet, m.snippet, m.nb_pieces_jointes, s.opened_at, s.flagged
  FROM rattachement r JOIN comm m USING (comm_id)${jointure}
  LEFT JOIN read_state s ON s.comm_id = r.comm_id AND s.boite_id = r.boite_id AND s.compte_id = :moi
 WHERE r.boite_id = ANY (:mes_boites) AND ${where}
 ORDER BY m.date_reception DESC
 LIMIT 50;`,
        folder.kind === "axe" || folder.kind === "virtuel" || folder.kind === "perso"
          ? "index (tag_id, sorti_le DESC, comm_id) — D016, date dénormalisée dans la liaison"
          : "index (boite_id, exit_reason, date_reception DESC) — D036 : la portée EST le chemin d'accès" +
            " · partition (type='email', période) : ni le chat ni les canaux à venir ne sont balayés (D138/D013)");
    },

    /* La liste se CHARGE par promesse (D141 : asynchrone, même quand la réponse est
       immédiate) puis se PEINT depuis ce qui a été chargé. Une clé de requête évite
       de peindre une réponse périmée quand l'utilisateur a déjà changé de dossier. */
    _cache: [], _cle: null,
    /* ce que la liste affiche — les raccourcis (F111) parcourent CETTE liste, jamais le DOM */
    messages() { return List._cache; },
    charger() {
      const ui = St.ui, cle = [ui.folder.id, ui.filtre, ui.tri, ui.sens, ui.statut].join("|");
      List._cle = cle;
      return ABX.Api.liste(ui.folder, ui.filtre, ui.tri, ui.sens, ui.statut).then(l => {
        if (List._cle !== cle) return;            // réponse périmée : on ne peint pas
        List._cache = l; List.peindre();
      });
    },
    peindre() {
      const ui = St.ui;
      const messages = List._cache;
      const actif = ui.tabs.find(t => t.key === ui.tab);
      const selection = actif && actif.type === "msg" ? actif.id : null;
      const el = D.paint("list", ABX.Views.List.render(ui, messages, selection));
      App().bindRetour(el);
      el.querySelector("#tri").value = ui.tri;

      const vider = el.querySelector("#vider");
      if (vider) vider.onclick = () => ABX.Api.contenu(ui.folder).then(M.viderCorbeille);

      /* CHARGER, pas peindre : filtre, sens et tri sont des paramètres de la REQUÊTE — c'est le
         serveur qui les applique (D078 : on ne rapatrie pas tout pour trier ici). Repeindre
         depuis le cache changeait la puce active et laissait la liste identique : les boutons
         avaient l'air cassés, et ils l'étaient. */
      D.on(el, ".chip[data-f]", "onclick", c => { ui.filtre = c.dataset.f; St.save();
        List.charger(); List.logFiltre(ui.filtre); });

      D.on(el, ".chip[data-s]", "onclick", c => { ui.sens = c.dataset.s; St.save();
        List.charger(); List.logSens(ui.sens); });

      D.byId("tri").onchange = e => {
        ui.tri = e.target.value; St.save(); List.charger();
        const idx = IDX_TRI[ui.tri];
        ABX.log("Tri : " + e.target.selectedOptions[0].text,
          `SELECT … ORDER BY ${SQL_TRI[ui.tri]} LIMIT 50;`, idx[0], idx[1]);
      };

      D.on(el, ".msg", "onclick", (d, e) => {
        const m = ABX.Api.cache.message(d.dataset.id);
        const b = D.closest(e, "data-act");
        if (b) { e.stopPropagation(); return M[b.dataset.act](m); }
        /* Un brouillon ne s'ouvre pas en lecture : il se rouvre en composition. La LISTE ne
           porte ni corps ni composition (une seule passe, D078) : on va chercher le détail
           avant de rouvrir — sinon le brouillon s'ouvrait en lecture seule, et on ne pouvait
           plus le reprendre. */
        if ((m.dossier || m.dossier_origine) === "drafts") {
          if (m.composition) return ABX.Controllers.Compose.rouvrir(m);
          return ABX.Api.message(m.id).then(x => {
            if (x && x.composition) return ABX.Controllers.Compose.rouvrir(x);
            ABX.Controllers.Tabs.ouvrir({ type:"msg", id:m.id }, true);
          });
        }
        ABX.Controllers.Tabs.ouvrir({ type:"msg", id:m.id }, true);
        if (App().MOBILE()) App().setVue("detail");
      });

      D.on(el, ".msg", "ondblclick", d => {
        const t = ui.tabs.find(x => x.key === "m:" + d.dataset.id);
        if (t) { t.prov = false; St.save(); ABX.Controllers.Tabs.peindre(); }
      });
    },

    /* Le sens ne se DÉDUIT pas de l'expéditeur : une boîte commune reçoit ses
       propres envois, et un IN sur les N adresses du compte ne s'indexe pas. */
    logSens(s) {
      if (s === "tous") return ABX.log("Sens : tous",
        `SELECT … -- aucune clause de sens`, "l'index de liste suffit, rien de plus à payer");
      ABX.log("Filtre « " + (s === "in" ? "reçus" : "envoyés") + " »",
`SELECT m.comm_id, m.sujet, m.from_nom, m.date_reception
  FROM rattachement r JOIN comm m USING (comm_id)
 WHERE r.compte_id = :moi AND <portée du dossier>
   AND r.sens = '${s === "in" ? "recu" : "envoye"}'
 ORDER BY m.date_reception DESC LIMIT 50;

-- l'alternative, à ne PAS retenir :
--   AND m.from_adresse IN (SELECT adresse FROM boite WHERE compte_id = :moi)`,
        "⚠ le sens doit être une COLONNE du rattachement, posée à l'ingestion et à " +
        "l'émission. Le déduire de from_adresse est faux (une boîte commune reçoit ses " +
        "propres envois) et ne s'indexe pas (IN sur N adresses). Sinon, index partiel " +
        "(compte_id, date_reception DESC) WHERE sens = 'envoye'", true);
    },

    logFiltre(f) {
      if (f === "non_lus") ABX.log("Filtre « à voir »",
`SELECT … FROM rattachement r
 WHERE <portée du dossier>
   AND (NOT EXISTS (SELECT 1 FROM read_state s
                     WHERE s.comm_id = r.comm_id AND s.boite_id = r.boite_id
                       AND s.compte_id = :moi AND s.opened_at IS NOT NULL)
        OR EXISTS (SELECT 1 FROM marker_personal p JOIN marker k USING (marker_id)
                    WHERE p.comm_id = r.comm_id AND p.boite_id = r.boite_id
                      AND p.compte_id = :moi AND k.code = 'to_review'))
 ORDER BY m.date_reception DESC LIMIT 50;`,
        "DEUX termes, et c'est D175 § 2 : jamais ouvert PAR MOI, ou remis de côté. Les deux tables " +
        "sont creuses, donc leur taille est celle du non-lu, pas celle du corpus. Et le compteur " +
        "évalue la MÊME expression que la liste — D166 interdit qu'ils disent deux choses");
      else if (f === "pj") ABX.log("Filtre « avec pièce jointe »",
        `SELECT … WHERE m.nb_pieces_jointes > 0 …;`,
        "nb_pieces_jointes dénormalisé (D029) — sinon un COUNT par ligne de liste");
      else if (f === "lourds") ABX.log("Filtre « lourds » — la file de recompression (D070)",
`SELECT m.comm_id, m.sujet, m.taille_octets, m.nb_pieces_jointes
  FROM rattachement r JOIN comm m USING (comm_id)
 WHERE r.compte_id = :moi AND <portée du dossier>
   AND m.taille_octets > 2 * 1024 * 1024
 ORDER BY m.taille_octets DESC LIMIT 50;`,
        "⚠ aucun index sur taille_octets : acceptable au clic, PAS pour balayer le corpus. " +
        "L'écran de recompression devra partir de piece_jointe (octets DESC), pas de message", true);
      else if (f === "sortis") ABX.log("Filtre « sortis de la file »",
`SELECT … FROM rattachement r
 WHERE r.exit_reason IS NOT NULL AND <portée du dossier>
 ORDER BY coalesce(r.processed_at, r.archived_at, r.deleted_at, r.junk_at) DESC LIMIT 50;`,
        "⚠ ces lignes sont dans une AUTRE partition que la file (D014/D030) : deux plans, deux " +
        "index. C'est voulu — mais un écran qui mélange les deux paie les deux. Le `coalesce` dit " +
        "quelque chose de plus : il n'y a plus UNE date de sortie, mais une par transition — un " +
        "message est généralement traité puis archivé des années après (D175 § 4 bis)", true);
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.List = List;
})(window.ABX = window.ABX || {});
