/* ADMINISTRATION — quatre volets, un onglet.
   Ce qu'un exploitant doit pouvoir régler sans ouvrir psql : les domaines et
   boîtes, les applications connectées et leurs jetons, les axes de tags, et le
   choix des fournisseurs de la suite. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, Fx = ABX.Fixtures, P = ABX.Providers;

  const VOLETS = [["boites","Domaines & boîtes"], ["apps","Applications & jetons"],
                  ["axes","Axes & tags"], ["suite","Suite collaborative"],
                  ["canaux","Canaux"]];
  const jalon = v => v && v > 1 ? `<span class="jalon v${v}">V${v}</span>` : "";

  function boites() {
    return `<div class="box"><h4>Domaines</h4>
      <table class="erpl"><tr><th>Domaine</th><th>Rôle</th><th>Boîtes</th><th>Alias</th>
        <th>Ingestion</th></tr>
      ${Fx.DOMAINES.map(d => `<tr><td><b>${F.esc(d.nom)}</b></td>
        <td><span class="st ${d.role === "pilote" ? "ok" : "wait"}">${d.role}</span></td>
        <td class="num">${d.boites}</td><td class="num">${d.alias}</td>
        <td>${F.esc(d.ingestion)}</td></tr>`).join("")}</table>
      <div class="hint">Les alias ne sont pas des redirections : chaque alias est une
        <b>boîte propre</b> (D039), sinon deux destinataires distincts se retrouvent dans le
        même fil et personne ne sait à qui le message était adressé.</div></div>

    <div class="box"><h4>Boîtes</h4>
      <table class="erpl"><tr><th>Adresse</th><th>Type</th><th>Accès</th><th>Messages</th><th></th></tr>
      ${Fx.BOITES.map(b => `<tr><td><b>${F.esc(b.adresse)}</b></td>
        <td>${b.type === "alias" ? `alias → ${F.esc(b.cible)}` : F.esc(b.type)}</td>
        <td class="num">${b.acces != null ? b.acces + " compte(s)" : "—"}</td>
        <td class="num">${b.msg != null ? b.msg.toLocaleString("fr-FR") : "—"}</td>
        <td class="num"><button class="hbtn ic" data-adm="boite:${F.esc(b.adresse)}">⋯</button></td>
        </tr>`).join("")}</table>
      <div class="cbar"><button class="hbtn prim" data-adm="boite:new">+ Créer une boîte</button>
        <button class="hbtn" data-adm="alias:new">+ Créer un alias</button></div>
      <div class="hint">Une boîte <b>commune</b> est un vrai destinataire, pas un partage :
        c'est ce qui permet de répondre depuis elle et de garder le fil entier pour toute
        l'équipe (Q026).</div></div>`;
  }

  function apps() {
    return `<div class="box"><h4>Applications connectées</h4>
      <table class="erpl"><tr><th>Application</th><th>Axes</th><th>Droits</th><th>Portée</th>
        <th>Jeton</th><th>Vue</th><th></th></tr>
      ${Fx.APPLICATIONS.map(a => `<tr>
        <td><b>${F.esc(a.label)}</b><br><span class="hash">${F.esc(a.code)}</span></td>
        <td>${a.axes.map(x => `<span class="tag ax">${F.esc(x)}</span>`).join(" ")}</td>
        <td>${F.esc(a.droits)}</td><td>${F.esc(a.portee)}</td>
        <td><span class="hash">${F.esc(a.jeton)}</span></td>
        <td>${F.esc(a.vu)}</td>
        <td class="num"><button class="hbtn ic dgr" data-adm="tok:${F.esc(a.code)}"
          title="Révoquer et régénérer">⟳</button></td></tr>`).join("")}</table>
      <div class="cbar"><button class="hbtn prim" data-adm="app:new">+ Connecter une application</button></div>
      <div class="hint">Le jeton est <b>opaque</b> et porte sa propre portée (D063/D037) : ce
        n'est pas un compte utilisateur déguisé. Révoquer coupe l'accès sans toucher aux tags
        déjà posés — ils appartiennent à l'application, pas au jeton.</div></div>

    <div class="box"><h4>Ce qu'une application peut faire</h4>
      <div class="hint">Trois droits par <b>axe</b>, pas par message (D018) : lire, écrire,
        administrer. « Retranche, jamais n'élargit » — une application ne voit jamais plus que
        le compte au nom duquel elle appelle, et l'unicité <code>(axe, application, valeur)</code>
        garantit que quatre Dolibarr font quatre jeux de tags sans s'écraser (D020).</div></div>`;
  }

  function axes() {
    return `<div class="box"><h4>Axes de tags</h4>
      <table class="erpl"><tr><th>Axe</th><th>Valeurs</th><th>Posé par</th><th>ACL</th><th></th></tr>
      ${Fx.AXES.map(a => `<tr><td>${a.icon} <b>${F.esc(a.label)}</b>
          <br><span class="hash">${F.esc(a.id)}</span></td>
        <td class="num">${Fx.valeurs[a.id].length}</td>
        <td>${a.id === "notification" || a.id === "social"
              ? `<span class="tag">filtre AtomBox</span>`
              : `<span class="tag">dolibarr-mmi</span>`}</td>
        <td><span class="st ok">lire</span> <span class="st wait">écrire</span></td>
        <td class="num"><button class="hbtn ic" data-adm="axe:${F.esc(a.id)}">⋯</button></td>
        </tr>`).join("")}
      <tr><td>🏷 <b>Libres</b><br><span class="hash">projet, type</span></td>
        <td class="num">—</td><td><span class="tag">utilisateur</span></td>
        <td><span class="st ok">lire</span> <span class="st ok">écrire</span></td><td></td></tr>
      </table>
      <div class="cbar"><button class="hbtn prim" data-adm="axe:new">+ Créer un axe</button></div>
      <div class="hint"><b>Q005 n'est pas tranchée</b> : qui crée un axe, qui le nomme. Le
        mécanisme est là (droit « administrer »), la politique non — et c'est elle qui décide si
        l'interopérabilité tient ou si chaque application invente son vocabulaire.</div></div>`;
  }

  function suite() {
    return `<div class="box"><h4>Fournisseurs de la suite</h4>
      <div class="hint">AtomBox se propose comme une <b>suite collaborative centrée sur la
        messagerie</b> : contacts, tâches, cloud et CRM naissent d'un email. Chaque capacité
        est un <b>contrat</b> — mais les composants <b>internes sont une cible de V3</b>. En
        V1 et V2, AtomBox est une messagerie qui <b>se branche</b> : par connecteur, ou
        absente. Ce que le contrat garantit, c'est que la V3 ne demandera aucune réécriture
        d'interface.</div>
      ${Object.entries(P.CAPACITES).map(([cap, c]) => {
        const a = P.actif(cap);
        return `<div class="capa">
          <div class="capt">${c.ic} <b>${F.esc(c.label)}</b>
            <span class="hash">${c.contrat.join("  ·  ")}</span></div>
          <div class="chips">${Object.entries(c.fournisseurs).map(([id, f]) =>
            `<span class="chip${id === a.id ? " on" : ""}${f.v > 1 ? " futur" : ""}"
              data-cap="${cap}" data-f="${id}"
              >${f.ic} ${F.esc(f.label)} ${jalon(f.v)}</span>`).join("")}</div>
          <div class="hint">${F.esc(a.note)}</div>
        </div>`; }).join("")}
      </div>`;
  }

  /* Les canaux ne sont pas des capacités : c'est de l'ingestion, donc le cœur du
     moteur. Ce volet ne sert qu'à une chose — rappeler ce qu'il ne faut PAS
     s'interdire dès la V1, parce que ces trois précautions sont gratuites
     maintenant et coûteuses plus tard. */
  function canaux() {
    return `<div class="box"><h4>Canaux d'entrée</h4>
      <table class="erpl"><tr><th>Canal</th><th>Jalon</th><th>État</th></tr>
      ${P.CANAUX.map(c => `<tr><td>${c.ic} <b>${F.esc(c.label)}</b></td>
        <td>${jalon(c.v) || `<span class="st ok">V1</span>`}</td>
        <td>${F.esc(c.etat)}</td></tr>`).join("")}</table>
      <div class="hint">La V4 ouvre AtomBox aux canaux non-mail. Ce n'est pas une capacité
        enfichable : un canal ENTRE dans le moteur, il ne se branche pas à côté.</div></div>

    <div class="box"><h4>Ce qu'il ne faut pas s'interdire, dès la V1</h4>
      <div class="hint">Trois précautions gratuites aujourd'hui, très coûteuses en V4 —
        même raisonnement que D062 pour le multi-organisation : on ne construit pas la suite,
        on ne se ferme pas la porte.</div>
      <table class="erpl">
        <tr><th>Précaution</th><th>Sans elle, en V4</th></tr>
        <tr><td><b>L'identifiant d'un correspondant a un TYPE</b><br>
          <span class="hash">correspondant_identifiant (type, valeur)</span> plutôt qu'une
          colonne <code>adresse</code></td>
          <td>un numéro de téléphone ne peut pas rejoindre l'identité qui porte déjà l'email
          — et c'est justement l'intérêt de D035</td></tr>
        <tr><td><b>Le message porte son CANAL</b><br>
          <span class="hash">message.canal = 'email'</span> dès la première ligne</td>
          <td>toutes les vues et tous les index supposent l'email, et il faut réécrire les
          requêtes une par une</td></tr>
        <tr><td><b>Ce qui est PROPRE À L'EMAIL est isolé</b><br>
          <span class="hash">message_email</span> : headers, DKIM/SPF, MIME, uid IMAP</td>
          <td>un SMS se retrouve avec douze colonnes nulles, et <code>message</code> devient
          une table à trous que plus personne n'ose modifier</td></tr>
      </table>
      <div class="hint">La troisième est la seule qui demande un arbitrage : elle coûte une
        jointure sur le chemin le plus chaud du produit. <b>Q038</b>.</div></div>`;
  }

  const RENDU = { boites, apps, axes, suite, canaux };

  ABX.Views = ABX.Views || {};
  ABX.Views.Admin = {
    VOLETS,
    render(volet) {
      const v = RENDU[volet] ? volet : "boites";
      return `<div class="backbar"><button data-vue="liste">‹ Retour</button></div>
        <div class="dhead"><div class="dsubj">Administration</div>
          <div class="dmeta">rôles d'administration par utilisateur (D072) — ce POC affiche
            tout, un exploitant réel ne verra que ses volets</div>
          <div class="chips" style="margin-top:9px">${VOLETS.map(([k, l]) =>
            `<span class="chip${k === v ? " on" : ""}" data-vol="${k}">${l}</span>`).join("")}</div>
        </div>
        <div class="admin">${RENDU[v]()}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
