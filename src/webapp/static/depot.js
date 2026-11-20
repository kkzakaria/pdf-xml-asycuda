// Écran de dépôt : liste les PDF choisis (ou glissés) et met à jour le bouton.
// Sans JavaScript, le champ fichier natif fonctionne tel quel.
(function () {
  var champ = document.getElementById("fichiers");
  var zone = document.getElementById("zone-depot");
  var liste = document.getElementById("fichiers-choisis");
  var bouton = document.getElementById("deposer");
  if (!champ || !zone || !liste || !bouton) return;

  function taille(octets) {
    return octets < 1024 * 1024 ? Math.round(octets / 1024) + " Ko" : (octets / 1048576).toFixed(1) + " Mo";
  }

  function afficher() {
    var fichiers = Array.prototype.slice.call(champ.files || []);
    liste.textContent = "";
    liste.hidden = fichiers.length === 0;
    fichiers.forEach(function (f) {
      var ligne = document.createElement("li");
      ligne.className = "flex items-center gap-3 px-4 py-3 border-t border-[#EEF0F7] first:border-t-0";
      var nom = document.createElement("span");
      nom.className = "font-semibold break-all";
      nom.textContent = f.name;
      var poids = document.createElement("span");
      poids.className = "text-xs text-encre-3";
      poids.textContent = taille(f.size);
      ligne.appendChild(nom);
      ligne.appendChild(poids);
      liste.appendChild(ligne);
    });
    var n = fichiers.length;
    bouton.lastChild.textContent = n > 1 ? "Créer " + n + " dossiers" : n === 1 ? "Créer 1 dossier" : "Déposer";
  }

  champ.addEventListener("change", afficher);
  ["dragenter", "dragover"].forEach(function (type) {
    zone.addEventListener(type, function (e) { e.preventDefault(); zone.classList.add("border-karta-bleu", "bg-karta-pale"); });
  });
  ["dragleave", "drop"].forEach(function (type) {
    zone.addEventListener(type, function () { zone.classList.remove("border-karta-bleu", "bg-karta-pale"); });
  });
  function estPdf(f) {
    return f.type === "application/pdf" || /\.pdf$/i.test(f.name);
  }

  // Glisser-déposer : seuls les PDF sont retenus, comme le filtre « accept » du sélecteur
  zone.addEventListener("drop", function (e) {
    e.preventDefault();
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    var pdfs = new DataTransfer();
    var ecartes = [];
    Array.prototype.forEach.call(e.dataTransfer.files, function (f) {
      if (estPdf(f)) pdfs.items.add(f); else ecartes.push(f.name);
    });
    champ.files = pdfs.files;
    afficher();
    if (ecartes.length) {
      var avis = document.createElement("li");
      avis.className = "px-4 py-3 border-t border-[#EEF0F7] first:border-t-0 text-erreur";
      avis.textContent = "Ignoré (pas un PDF) : " + ecartes.join(", ");
      liste.appendChild(avis);
      liste.hidden = false;
    }
  });
})();
