/* LE DIRECT (RM3632, D169, D170) — le webmail reste connecté, et le serveur lui dit ce qui change.

   Une connexion SSE persistante sur `/api/v1/evenements`. Elle passe par `fetch` et non par
   `EventSource` : la session est un JETON porté par l'en-tête (D063), et EventSource ne sait pas
   envoyer d'en-tête — il faudrait le mettre dans l'URL, donc dans tous les journaux.

   L'événement INVALIDE (D169) : il dit « ce message, ce dossier a changé » ; on relit par les routes
   habituelles. Les événements d'une même seconde sont regroupés : une relève de vingt messages
   repeint une fois, pas vingt.

   La connexion se RÉTABLIT seule (3 s, puis jusqu'à 30 s), avec le dernier événement vu
   (`Last-Event-ID`) : rien de perdu pendant une coupure. Sans flux lisible (un navigateur trop
   ancien, le harnais), le direct s'abstient — l'écran marche comme avant, au rechargement. */
(function (ABX) {
  "use strict";

  const BASE = (ABX.config && ABX.config.api) || "/api/v1";

  /* « id / event / data » : une trame SSE ; renvoie [trames complètes, reste non terminé] */
  function decouper(tampon) {
    const blocs = tampon.split(/\r?\n\r?\n/), reste = blocs.pop(), trames = [];
    for (const b of blocs) {
      const t = { id: null, event: "message", data: "" };
      for (const l of b.split(/\r?\n/)) {
        if (!l || l.startsWith(":")) continue;                  // commentaire : « connecte », « ping »
        const i = l.indexOf(":"), k = i < 0 ? l : l.slice(0, i), v = i < 0 ? "" : l.slice(i + 1).replace(/^ /, "");
        if (k === "id") t.id = v; else if (k === "event") t.event = v; else if (k === "data") t.data += (t.data ? "\n" : "") + v;
      }
      if (t.id || t.data) trames.push(t);
    }
    return [trames, reste];
  }

  const Direct = {
    etat: "ferme", curseur: null, attenteInitiale: 3000, attente: 3000, _lot: [], _minuterie: null, _ctl: null, _fetch: null,

    possible() {
      return typeof fetch === "function" && typeof TextDecoder !== "undefined"
        && !!(ABX.Session && ABX.Session.jeton && ABX.Session.jeton()) && !(ABX.Session.simulee && ABX.Session.simulee());
    },

    /* `f` : le fetch à employer (le harnais en prête un qui rend un flux) ; gardé pour les reconnexions */
    demarrer(f) {
      if (f) Direct._fetch = f;
      if (!Direct.possible() || Direct.etat === "ouvert" || Direct.etat === "ouverture") return null;
      Direct.etat = "ouverture";
      const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
      Direct._ctl = ctl;
      const h = { "Authorization": "Bearer " + ABX.Session.jeton(), "Accept": "text/event-stream" };
      if (Direct.curseur) h["Last-Event-ID"] = Direct.curseur;
      return (Direct._fetch || fetch)(BASE + "/evenements", { headers: h, signal: ctl && ctl.signal, cache: "no-store" })
        .then(r => {
          if (!r.ok || !r.body || !r.body.getReader) { Direct.etat = r.status === 401 ? "refuse" : "indisponible"; return null; }
          Direct.etat = "ouvert"; Direct.attente = Direct.attenteInitiale; Direct.signaler();
          const lecteur = r.body.getReader(), dec = Direct.decodeur();
          let tampon = "";
          const lire = () => lecteur.read().then(({ done, value }) => {
            if (done) return;
            tampon += dec.decode(value, { stream: true });
            const [trames, reste] = decouper(tampon); tampon = reste;
            trames.forEach(Direct.trame);
            return lire();
          });
          return lire();
        })
        .catch(() => null)
        .then(() => {
          if (Direct.etat === "ferme" || Direct.etat === "refuse" || Direct.etat === "indisponible") { Direct.signaler(); return; }
          Direct.etat = "coupe"; Direct.signaler();
          // se rétablir, sans marteler — sauf si on l'a fermé entre-temps
          setTimeout(() => { if (Direct.etat === "coupe") Direct.demarrer(); }, Direct.attente);
          Direct.attente = Math.min(Direct.attente * 2, 30000);
        });
    },

    /* isolé : le harnais n'a pas de TextDecoder, le test lui prête celui de Node */
    decodeur() { return new TextDecoder(); },

    arreter() { Direct.etat = "ferme"; if (Direct._ctl) Direct._ctl.abort(); Direct.signaler(); },

    trame(t) {
      if (t.id) Direct.curseur = t.id;
      let data = {};
      try { data = t.data ? JSON.parse(t.data) : {}; } catch (e) {}
      Direct.recevoir(t.event, data);
    },

    /* un événement ; ceux d'une même fenêtre de 300 ms repeignent ensemble */
    recevoir(type, data) {
      Direct._lot.push({ type, data: data || {} });
      if (Direct._minuterie) return;
      Direct._minuterie = setTimeout(() => { Direct._minuterie = null; Direct.appliquer(); }, 300);
    },

    /* ce qui a changé → ce qu'on relit. Rend la promesse de la mise à jour (le harnais l'attend). */
    appliquer() {
      const lot = Direct._lot.splice(0);
      if (!lot.length) return Promise.resolve(false);
      const types = new Set(lot.map(e => e.type));
      // un message qu'on a ouvert et qui a changé : son détail est relu (tags, état, dossier)
      lot.forEach(e => { const m = e.data.comm_id && ABX.Api.cache.message(e.data.comm_id); if (m) delete m._complet; });
      const referentiel = types.has("dossier.change") || types.has("message.ingere") || types.has("tags.change");
      return Promise.resolve(referentiel ? ABX.Ref.charger() : null)
        .then(() => ABX.Api.compteurs())
        .catch(() => null)
        .then(() => { ABX.Bus.emit("corpus:changed", { direct: lot }); return true; });
    },

    /* l'état se lit sur la page : <html data-direct="ouvert|coupe|…"> — un indicateur discret */
    signaler() {
      try { document.documentElement.setAttribute("data-direct", Direct.etat); } catch (e) {}
    },

    decouper,
  };

  ABX.Direct = Direct;
})(window.ABX = window.ABX || {});
