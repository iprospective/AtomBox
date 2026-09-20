/* L'APPLICATION ANDROID (RM3252, F144, D172) — une Trusted Web Activity ouvre le site en plein
   écran À CONDITION que trois choses se correspondent exactement : le manifeste web (ce que le
   site déclare être), le manifeste de l'application (ce qu'elle va ouvrir), et assetlinks.json
   (la preuve que ce site et cette application vont ensemble).

   Si l'une diverge, rien ne casse bruyamment : l'application s'ouvre avec une BARRE D'ADRESSE,
   comme un simple navigateur. C'est le genre de défaut qu'on ne voit pas depuis un poste de
   développement — d'où ce harnais. */
"use strict";
const fs = require("fs"), path = require("path");
const { eq, vrai, bilan, RACINE } = require("./run");

const lire = f => JSON.parse(fs.readFileSync(path.join(RACINE, f), "utf8"));
const twa = lire("android/twa-manifest.json");
const web = lire("manifest.webmanifest");
const liens = lire(".well-known/assetlinks.json");

console.log("— l'application ouvre CE site ——————————————————————————————");
const hote = new URL(twa.webManifestUrl).host;
eq(twa.host, hote, "le domaine de l'application est celui de son manifeste web");
eq(new URL(twa.fullScopeUrl).host, hote, "et la portée aussi — sinon l'application sort d'elle-même au premier lien");
vrai(twa.webManifestUrl.startsWith("https://"), "en HTTPS : une TWA ne se vérifie pas autrement");

console.log("— elle dit la même chose que le site ————————————————————————");
eq(twa.name, web.name, "le nom");
eq(twa.themeColor.toLowerCase(), web.theme_color.toLowerCase(), "la couleur de thème");
eq(twa.backgroundColor.toLowerCase(), web.background_color.toLowerCase(), "la couleur de fond");
eq(twa.display, web.display, "le mode d'affichage");
const url = f => new URL(f, twa.webManifestUrl).pathname.replace(/^\//, "");
vrai(web.icons.some(i => url(twa.iconUrl) === i.src), "son icône est une icône du manifeste web : " + url(twa.iconUrl));
vrai(web.icons.some(i => url(twa.maskableIconUrl) === i.src && i.purpose === "maskable"),
     "et son icône « maskable » en est bien une");
vrai(fs.existsSync(path.join(RACINE, url(twa.iconUrl))), "l'icône existe dans le dépôt");

console.log("— la preuve de domaine ————————————————————————————————————");
eq(liens.length, 1, "une seule déclaration");
const cible = liens[0].target;
eq(cible.namespace, "android_app", "elle vise bien une application Android");
eq(cible.package_name, twa.packageId, "le paquet déclaré par le site est celui de l'application");
vrai(liens[0].relation.includes("delegate_permission/common.handle_all_urls"),
     "elle délègue l'ouverture des liens — c'est ce qui retire la barre d'adresse");
eq(cible.sha256_cert_fingerprints.length, 1, "une empreinte de clé");
const emp = cible.sha256_cert_fingerprints[0];
vrai(/^([0-9A-F]{2}:){31}[0-9A-F]{2}$/.test(emp),
     "l'empreinte est 32 octets en hexadécimal majuscule séparés par « : » — le format exact qu'Android attend");

console.log("— ce qui ne doit JAMAIS entrer dans le dépôt ————————————————");
const chemin = twa.signingKey.path;
vrai(!chemin.startsWith(RACINE) && !chemin.includes("/webmail/"),
     "la clé de signature vit HORS du dépôt (" + chemin + ") : la publier, c'est laisser signer à sa place");
vrai(!JSON.stringify(twa).match(/password|motdepasse|mot_de_passe/i), "et aucun mot de passe n'est écrit ici");
const ignore = fs.readFileSync(path.join(RACINE, "android/.gitignore"), "utf8");
for (const f of ["app/", "*.apk", "*.keystore"])
  vrai(ignore.includes(f), "android/.gitignore écarte " + f + " — le projet Android est engendré, pas versionné");
bilan();
