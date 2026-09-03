/* LE CORPUS — engendré, jamais stocké.

   Tout est produit au démarrage dans un ordre fixe : c'est ce qui le rend
   identique d'une session à l'autre, et donc persistable par simple delta
   (voir core/store.js). Les compteurs de l'arborescence ne sont pas des
   fixtures : ils se CALCULENT en une passe, jamais une requête par dossier (D78). */
(function (ABX) {
  "use strict";
  const P = ABX.PRNG, Fx = ABX.Fixtures, At = ABX.Attachments, St = ABX.Store;

  const dossiers = {};   // folderId -> [messages]
  const parId    = {};   // comm_id -> message
  let   tous     = [];
  let   compte   = {};   // folderId -> { t, u }

  function fabriqueMessages(fid, label, n, opt) {
    const out = [], o = opt || {};
    const axe = fid.split(":")[0];
    /* D133 — être abonné à une newsletter est un fait qui porte sur le
       CORRESPONDANT, pas sur le message : on ne reçoit pas une lettre d'OVH une
       fois, on la reçoit tous les mois. Le tirage se fait donc une fois par
       dossier, hors flux (P.with), et non message par message — sinon on
       obtiendrait deux cents listes d'un seul message, ce qu'aucune boîte réelle
       ne montre. Fournisseurs et partenaires seulement : un client n'envoie pas
       de newsletter. */
    const emetteurListe = (axe === "fournisseur" || axe === "partenaire") &&
                          P.with("nl/" + fid, () => P.next()) < .10;
    for (let i = 0; i < n; i++) {
      const qui = fid.startsWith("collaborateur") ? label : Fx.pers();
      const dom = ABX.Fmt.slug(label).slice(0, 14) + ".fr";
      const adr = ABX.Fmt.slug(qui).replace(/-/g, ".") + "@" + dom;
      const boite = P.pick(Fx.MOI.boites).adresse;
      /* Un dossier virtuel porte TOUTE la correspondance d'un tiers, pas seulement
         ce qu'on en a reçu : sans les envois, un dossier client raconte la moitié
         de l'histoire, et le fil de discussion est amputé. */
      const tirage = P.next(), luTirage = P.next() < .3;
      /* On répond à un client, à un fournisseur, à un ticket — jamais à une
         alerte de supervision ni à un réseau social. Un axe « sans retour » ne
         porte donc que du courrier entrant. */
      const sansRetour = axe === "notification" || axe === "social";
      const sortant = !!o.sortant || (Fx.estAxe(axe) && !sansRetour && tirage < .25);
      const m = {
        id: fid + "/m" + i, fid,
        sens: sortant ? "out" : "in",
        from: sortant ? Fx.MOI.nom : qui,
        mail: sortant ? boite : adr,
        to:   sortant ? [adr]  : [boite],
        boite,                                    // la boîte qui a reçu ou émis — Q26
        subject: sujet(axe, label),
        body: P.pick(Fx.CORPS),
        date: Date.now() - P.int(0, 300) * 864e5 - P.int(0, 86399) * 1000,
        lu: sortant ? true : !luTirage,
        thread: P.int(1, 4), tags: [],
        statut: "nouveau",
        sorti: null, motif: null, dossier: null, ref: null, compo: null,
      };
      /* Un corpus où tout serait « nouveau » ne montrerait pas la file de travail. */
      if (!sortant && P.next() < .28) m.statut = P.pick(["a_faire","a_faire","en_cours","attente"]);
      m.snippet = m.body.split("\n")[2] || "…";
      /* D126 — un correspondant est « connu » quand il est enregistré : ceux qui
         portent un axe métier le sont, une notification ou un réseau social non.
         D128 (B1) — on fabrique quelques usurpations : le NOM d'un correspondant
         connu, posé sur une adresse qui n'est pas la sienne. C'est le meilleur
         signal du catalogue, et le seul qui se voie à l'écran.
         Tirage hors flux principal (P.with) pour ne pas décaler le corpus. */
      m.connu = !sortant && Fx.estAxe(axe);
      /* 1 % : FRÉQUENCE DE DÉMONSTRATION, volontairement gonflée. Dans un corpus
         réel, une usurpation par nom est rare — quelques-unes par an et par boîte.
         Ce taux est choisi pour qu'on en croise sans chercher, pas mesuré. */
      if (m.connu && P.with("spoof/" + m.id, () => P.next()) < .01) {
        m.spoof = true;
        m.connu = false;
        m.mail = ABX.Fmt.slug(qui).replace(/-/g, ".") + "@" +
                 P.with("spoofdom/" + m.id, () => P.pick(Fx.DOMAINES_LIBRES));
      }
      /* D130 — la NATURE du message. Une PME reçoit plus de machines que de
         personnes ; les ranger toutes pareil, c'est noyer les trois qui comptent.
         La ligne de partage n'est pas humain/machine, c'est « quelqu'un attend-il
         quelque chose de moi ? » — d'où quatre valeurs, pas un booléen.
         Tirage hors flux (P.with) : la nature s'ajoute sans décaler le corpus. */
      m.nature = "humain";
      if (!sortant && !m.spoof) {
        const t = P.with("nature/" + m.id, () => P.next());
        if      (axe === "notification")     m.nature = "notification";
        /* Une liste de discussion est une diffusion par nature : le forum entre
           dans la branche Abonnements sans qu'on ait rien à déclarer (D133). */
        else if (axe === "social" || axe === "forum") m.nature = "liste";
        /* 5 % / 45 % : CALAGE DE DÉMONSTRATION. Une vraie PME reçoit bien plus de
           courrier de machines que ça — souvent la moitié. Les taux sont baissés
           pour que la maquette montre le mécanisme sans noyer le reste ; il ne
           faut pas les lire comme une mesure. Un émetteur de newsletter envoie
           aussi des factures : d'où les 45 %, et non 100 %. */
        else if (Fx.estAxe(axe) && t < .05)  m.nature = "notification";
        else if (emetteurListe && t < .45)   m.nature = "liste";
      }
      if (m.nature !== "humain") {
        /* Une boîte fonctionnelle n'est pas une personne : elle ne peut pas être
           un correspondant du carnet — le modèle le disait déjà de no-reply@. */
        const d = m.mail.split("@")[1];
        m.connu  = false;
        m.from   = m.nature === "liste" ? label : label + " — notifications";
        m.mail   = (m.nature === "liste" ? "news@" : "noreply@") + d;
        if (m.nature === "liste") {
          /* Le List-Id est l'identifiant de la liste, pas de l'émetteur : c'est
             lui qui regroupe (D130) et lui que vise le désabonnement (D132). */
          m.listId    = "<newsletter." + d + ">";
          m.listeLbl  = label;
          m.listeId   = "abonnement:" + ABX.Fmt.slug(label);
        }
        /* Le point de D130 : une diffusion n'entre pas dans la file des non
           traités — une notification, si. Une facture est une machine qui
           attend un paiement ; un booléen « automatique » les confondait. */
        if (m.nature === "liste") m.statut = "nouveau";
      }
      /* D131 — trois niveaux. « avertir » se DÉDUIT de la nature ; « non » ne se
         déduit de rien : il s'APPREND d'un retour de non-remise (D119). C'est la
         seule preuve qu'une adresse ne lit pas ses réponses — le mot « noreply »
         n'en est pas une, il existe des noreply@ relevés par un humain. */
      m.repond = m.nature === "humain" ? "oui" : "avertir";
      if (m.nature !== "humain" &&
          P.with("dsn/" + m.id, () => P.next()) < .3) {
        m.repond = "non";
        m.dsn = { jours: P.with("dsnj/" + m.id, () => P.int(12, 240)),
                  code: "550 5.1.1 mailbox unavailable" };
      }
      /* Ne jamais refuser sans dire à qui écrire : le carnet connaît souvent
         quelqu'un du même domaine (D131). Montré, jamais présélectionné. */
      if (m.repond !== "oui" && Fx.estAxe(axe) &&
          axe !== "notification" && axe !== "social")
        m.alt = { nom: label, mail: "contact@" + m.mail.split("@")[1] };
      /* D136/D137 — la FIABILITÉ de l'expéditeur, à deux niveaux. Elle n'est pas
         un booléen « connu » de plus : elle combine ce que le domaine permet
         d'affirmer et ce qu'un humain a validé chez nous. Signée : au-dessus de
         zéro un correspondant établi, en dessous un émetteur douteux. */
      if (!sortant) {
        const t2 = P.with("fiab/" + m.id, () => P.next());
        /* L'alignement ne suit PAS le fait d'être connu : un correspondant établi
           peut écrire depuis un serveur mal configuré, une liste qui casse la
           signature, une redirection. C'est même le cas le plus instructif —
           celui où afficher « fiable » serait une faute (D137). */
        m.dom = { aligne: t2 < .82 };              // DMARC aligné sur CE message
        m.valide = m.connu && t2 < .35;            // validé par un humain de chez nous
        m.fiab = m.spoof ? -2
               : !m.dom.aligne ? 0
               : m.valide ? 2
               : m.connu ? 1 : 0;
      }
      At.attacher(m);
      /* La SOURCE du tag est l'application qui l'a poussé (D19/D20) : Dolibarr
         tient les tiers, Redmine tient les tickets. Deux axes, deux ACL, et
         c'est ce qui rend Q34 concrète — retirer à la main un tag posé par un
         connecteur n'a pas le même sens selon qui l'a posé. */
      if (Fx.estAxe(axe))
        m.tags.push({ axe, val: label,
                      src: (Fx.AXES.find(a => a.id === axe) || {}).app || "dolibarr-mmi" });
      if (P.next() < .25) m.tags.push({ axe:"projet", val:"RM" + P.int(2800, 2900), src:"redmine-ipro" });
      if (P.next() < .18) m.tags.push({ axe:"type", val:P.pick(["facture","devis","contrat"]), src:"filtre" });
      out.push(m);
    }
    return out.sort((a, b) => b.date - a.date);
  }

  /* Un ticket de développement ne parle pas de bons de livraison : le sujet suit
     l'axe, sinon l'arborescence engendrée n'a plus l'air d'être la même donnée
     que les messages qu'elle range. */
  function sujet(axe, label) {
    if (axe === "developpement") {
      const num = (label.match(/RM(\d+)/) || [0, "2881"])[1];
      const titre = label.split(" · ")[1] || "le ticket";
      return P.pick(Fx.SUJETS_RM).replace("{t}", titre).replace("{n}", num);
    }
    const propre = Fx.SUJETS_AXE[axe];
    if (propre)
      return P.pick(propre).replace("{n}", "" + P.int(1000, 9999)).replace("{v}", label);
    return (P.next() < .3 ? "Re: " : "") +
           P.pick(Fx.SUJETS).replace("{n}", "" + P.int(1000, 9999));
  }

  /* D133 — l'arborescence des abonnements n'est pas saisie, elle est DÉDUITE du
     corpus : un dossier par liste rencontrée. C'est D77 pris au mot, et le seul
     axe du POC dont les dossiers ne viennent ni d'une saisie ni d'un connecteur.
     Le message n'est pas déplacé : il reste chez son correspondant et apparaît
     ici en plus — deux vues, un seul message. */
  function deriveAbonnements() {
    const par = {};
    for (const m of tous) {
      if (m.nature !== "liste" || !m.listeId) continue;
      const v = par[m.listeId] = par[m.listeId] ||
        { id: m.listeId, label: m.listeLbl, axe: "abonnement", last: 0, listId: m.listId };
      if (m.date > v.last) v.last = m.date;
    }
    Fx.valeurs.abonnement = Object.values(par).sort((x, y) => y.last - x.last);
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
      deriveAbonnements();
      return { n: tous.length, ms: Date.now() - t0 };
    },

    /* Rejoue le delta persisté par-dessus le corpus fraîchement engendré. */
    applique() {
      St.crees.forEach(m => { parId[m.id] = m;
        (dossiers[m.fid] = dossiers[m.fid] || []).unshift(m); });
      Object.entries(St.ratt).forEach(([id, r]) => { const m = parId[id]; if (m) Object.assign(m, r); });
      tous = Object.values(parId).filter(m => !m.suppr);
      deriveAbonnements();
    },

    ajoute(m) { parId[m.id] = m; tous.push(m);
                (dossiers[m.fid] = dossiers[m.fid] || []).unshift(m); },

    retire(m) { tous = tous.filter(x => x !== m); },

    /* UNE passe sur le corpus pour les ~300 branches de l'arborescence (D78). */
    recompte() {
      compte = {};
      const bump = (k, m) => { const c = compte[k] = compte[k] || { t:0, u:0, f:0 };
        c.t++; if (!m.lu) c.u++;
        if (m.statut === "a_faire" || m.statut === "en_cours") c.f++; };
      for (const m of tous) {
        if (m.dossier === "trash") { bump("trash", m); continue; }
        if (m.motif) { bump(m.motif === "archive" ? "archives" : "traites", m); continue; }
        const k = m.dossier || m.fid;
        bump(k, m);
        const ax = k.split(":")[0];
        if (Fx.estAxe(ax)) bump("axe:" + ax, m);
        /* Le même message compte DEUX fois : dans l'axe de son correspondant et
           dans son abonnement. Ce n'est pas un doublon, c'est le multi-classement
           (D17/D77) — et c'est la raison pour laquelle les compteurs se calculent
           en une passe plutôt qu'en une requête par branche (D78). */
        if (m.nature === "liste" && m.listeId) {
          bump(m.listeId, m); bump("axe:abonnement", m);
        }
      }
      return compte;
    },

    cnt: k => compte[k] || { t:0, u:0, f:0 },

    /* La file de travail, tous dossiers confondus : « ce qu'il me reste à faire ». */
    aFaire: () => tous.filter(m => !m.motif && m.dossier !== "trash" &&
      (m.statut === "a_faire" || m.statut === "en_cours" || m.statut === "attente")),

    /* Le contenu d'un dossier, avant filtre de liste. */
    vue(folder) {
      if (VUES[folder.id]) return tous.filter(VUES[folder.id]);
      const hors = m => m.dossier !== "trash";
      if (folder.kind === "abo")
        return tous.filter(m => hors(m) && m.listeId === folder.id);
      if (folder.kind === "axe" && folder.axe === "abonnement")
        return tous.filter(m => hors(m) && m.nature === "liste");
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

    /* Filtre + tri de la liste. Le SENS est un second axe, indépendant du premier :
       on veut « non lus ET reçus », pas l'un ou l'autre. */
    filtrer(folder, filtre, tri, sens, statut) {
      let a = Corpus.vue(folder);
      if (sens === "in" || sens === "out") a = a.filter(m => (m.sens || "in") === sens);
      if (statut && statut !== "tous") a = a.filter(m => (m.statut || "nouveau") === statut);
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
