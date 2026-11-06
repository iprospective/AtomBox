#!/usr/bin/env node
/* LES FIXTURES DOLIBARR DE LA DÉMO, tirées du POC d'AtomBox (RM3520 — devcamp Dolibarr, 27-29/11).

   Mathieu, 05/11 : « go faire des fixtures pour le poc dolibarr, en lien avec les fixtures atombox ».
   Le POC du webmail engendre, d'une graine fixe, ses correspondants : 200 fournisseurs, 52 clients, des
   prospects, des partenaires, et les personnes qui leur écrivent. Le Dolibarr de démo doit raconter LA MÊME
   histoire : les mêmes sociétés, les mêmes contacts, les mêmes adresses. On ne recopie donc rien à la main :
   on charge le POC tel quel (mêmes fichiers, même graine) et on en extrait le jeu.

   Ce qui sort (JSON, sur la sortie standard ou --out) :
     tiers     : nom, axe (client / fournisseur / prospect / partenaire), domaine, contacts (nom, adresse)
     documents : pour un client, des propositions et des factures — montants et états tirés de la même graine
                 (P.with : ajoutés sans décaler le corpus du POC)

   Aucune donnée réelle : tout vient du générateur du POC. ⚠ Les domaines en .fr sont fabriqués à partir des
   noms (« acme-distribu.fr ») et PEUVENT exister : le Dolibarr de démo ne doit pas leur écrire
   (MAIN_MAIL_FORCE_SENDTO sur l'instance, voir le chargeur demo-fixtures.php du module).

     node tools/export-fixtures-dolibarr.js --out fixtures-dolibarr.json */
"use strict";
const path = require("path");
const fs = require("fs");

global.window = global; global.ABX = {};
const _ls = {}; global.localStorage = { getItem: k => _ls[k] ?? null, setItem: (k, v) => { _ls[k] = String(v); }, removeItem: k => { delete _ls[k]; } };
const SRC = path.join(__dirname, "..", "webmail", "src");
// l'ordre du POC (index.html) pour ce dont le corpus dépend : format, store, pièces jointes, puis le générateur
for (const f of ["noyau/format.js", "noyau/store.js", "modules/pieces-jointes/service.js", "poc/prng.js", "poc/fixtures.js", "poc/corpus.js"])
  require(path.join(SRC, f));
const P = ABX.PRNG, Fx = ABX.Fixtures, C = ABX.Corpus;
C.engendre();

const AXES = { client: "client", fournisseur: "fournisseur", prospect: "prospect", partenaire: "partenaire" };
const domaine = label => ABX.Fmt.slug(label).slice(0, 14) + ".fr";          // la règle de corpus.js
const EUR = n => Math.round(n * 100) / 100;
const PRESTATIONS = ["Audit et cadrage", "Développement spécifique", "Maintenance annuelle", "Formation des équipes",
                     "Hébergement et supervision", "Paramétrage et reprise de données", "Accompagnement au déploiement"];

const tiers = [];
for (const [axe, role] of Object.entries(AXES)) {
  for (const v of Fx.valeurs[axe] || []) {
    const vus = new Map();
    for (const m of C.dossiers[v.id] || []) {
      // les personnes qui ÉCRIVENT pour ce tiers : ni nos envois, ni les machines, ni les usurpations (D128)
      if (m.sens === "out" || m.usurpation || (m.nature && m.nature !== "humain")) continue;
      if (!m.from_adresse || !m.from_adresse.endsWith("@" + domaine(v.label))) continue;
      if (!vus.has(m.from_adresse)) vus.set(m.from_adresse, { nom: m.from_nom, adresse: m.from_adresse });
    }
    const t = { cle: v.id, nom: v.label, axe: role, domaine: domaine(v.label),
                contacts: [...vus.values()], messages: (C.dossiers[v.id] || []).length };
    if (role === "client" || role === "prospect") {
      t.documents = P.with("docs/" + v.id, () => {
        const out = [], n = role === "client" ? P.int(1, 3) : P.int(0, 1);
        for (let i = 0; i < n; i++) {
          const ht = EUR(P.int(4, 120) * 50 + P.int(0, 99) / 100 * 50);
          out.push({ type: "propal", ht, tva: 20, libelle: P.pick(PRESTATIONS),
                     etat: role === "prospect" ? "ouverte" : P.pick(["signee", "signee", "ouverte", "refusee"]) });
        }
        if (role === "client") {
          const nf = P.int(0, 2);
          for (let i = 0; i < nf; i++) {
            out.push({ type: "facture", ht: EUR(P.int(4, 80) * 50), tva: 20, libelle: P.pick(PRESTATIONS),
                       etat: P.pick(["payee", "payee", "impayee", "echue"]) });
          }
        }
        return out;
      });
    }
    tiers.push(t);
  }
}

const res = {
  source: "POC AtomBox — webmail/src/poc (fixtures.js, corpus.js), graine fixe", genere_par: "tools/export-fixtures-dolibarr.js",
  marque: "abxpoc",
  boites: Fx.MOI.boites.map(b => b.adresse),
  comptes: { tiers: tiers.length, contacts: tiers.reduce((n, t) => n + t.contacts.length, 0),
             propositions: tiers.reduce((n, t) => n + (t.documents || []).filter(d => d.type === "propal").length, 0),
             factures: tiers.reduce((n, t) => n + (t.documents || []).filter(d => d.type === "facture").length, 0) },
  tiers,
};
const i = process.argv.indexOf("--out");
const json = JSON.stringify(res, null, 1);
if (i > 0) { fs.writeFileSync(process.argv[i + 1], json + "\n"); console.error(`✓ ${process.argv[i + 1]} : ` + JSON.stringify(res.comptes)); }
else process.stdout.write(json + "\n");
