/* Interface de test du modèle IDS : construction du formulaire et appels API. */

const formulaire = document.getElementById("formulaire");
const champs = document.getElementById("champs");
const resultat = document.getElementById("resultat");
const meta = document.getElementById("meta");
const version = document.getElementById("version");

let donnees = null;

async function chargerFeatures() {
  const reponse = await fetch("api/features");
  donnees = await reponse.json();

  meta.textContent = `${donnees.nb_variables} variables · ${donnees.classes.length} familles`;
  version.textContent = donnees.modele;

  const parGroupe = new Map(donnees.groupes.map((groupe) => [groupe, []]));
  donnees.features.forEach((feature) => {
    parGroupe.get(feature.groupe).push(feature);
  });

  champs.innerHTML = "";
  donnees.groupes.forEach((groupe) => {
    const bloc = document.createElement("fieldset");
    bloc.className = "groupe";

    const titre = document.createElement("legend");
    titre.className = "groupe__titre";
    titre.textContent = groupe;
    bloc.appendChild(titre);

    const grille = document.createElement("div");
    grille.className = "groupe__grille";

    parGroupe.get(groupe).forEach((feature) => {
      const label = document.createElement("label");
      label.className = "champ";
      label.innerHTML =
        `<span>${feature.nom}<small>${feature.signification}</small></span>`;

      const input = document.createElement("input");
      input.type = "number";
      input.step = "any";
      input.name = feature.nom;
      input.value = feature.defaut;
      input.required = true;
      label.appendChild(input);
      grille.appendChild(label);
    });

    bloc.appendChild(grille);
    champs.appendChild(bloc);
  });
}

function valuesDuFormulaire() {
  const values = {};
  donnees.features.forEach((feature) => {
    values[feature.nom] = parseFloat(formulaire.elements.namedItem(feature.nom).value);
  });
  return values;
}

function afficherResultat(data) {
  const lignes = Object.entries(data.probabilites)
    .sort((a, b) => b[1] - a[1])
    .map(([nom, valeur]) => `
      <li class="probabilites__ligne">
        <span class="probabilites__nom">${nom}</span>
        <div class="probabilites__barre"><span style="width:${valeur * 100}%"></span></div>
        <span class="probabilites__valeur">${(valeur * 100).toFixed(1)}%</span>
      </li>`)
    .join("");

  const classe = data.est_attaque ? "badge--attack" : "badge--safe";
  const titre = data.est_attaque ? "Attaque détectée" : "Trafic normal";

  resultat.innerHTML = `
    <div class="badge ${classe}">
      <span class="badge__label">${titre}</span>
      <strong>${data.prediction}</strong>
    </div>
    <div class="confiance">
      <span>Confiance du modèle</span>
      <strong>${(data.confiance * 100).toFixed(1)}%</strong>
    </div>
    <div class="jauge"><span style="width:${data.confiance * 100}%"></span></div>
    <h3 class="sous-titre">Probabilités par famille</h3>
    <ul class="probabilites">${lignes}</ul>
  `;
}

function afficherErreur(message) {
  resultat.innerHTML = `<div class="erreur">${message}</div>`;
}

formulaire.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  try {
    const reponse = await fetch("api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: valuesDuFormulaire() }),
    });
    const data = await reponse.json();
    if (!reponse.ok) {
      afficherErreur(data.erreur || "Erreur lors de la prédiction.");
      return;
    }
    afficherResultat(data);
  } catch (erreur) {
    afficherErreur("Serveur inaccessible : " + erreur.message);
  }
});

document.getElementById("defaut").addEventListener("click", () => {
  donnees.features.forEach((feature) => {
    formulaire.elements.namedItem(feature.nom).value = feature.defaut;
  });
});

document.getElementById("effacer").addEventListener("click", () => {
  donnees.features.forEach((feature) => {
    formulaire.elements.namedItem(feature.nom).value = "";
  });
  resultat.innerHTML = `
    <div class="vide">
      <div class="vide__icone">◎</div>
      <p>En attente d'un flux…</p>
      <span>Lancez une analyse pour voir la prédiction.</span>
    </div>`;
});

chargerFeatures();
