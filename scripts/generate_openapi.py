#!/usr/bin/env python3
"""
Script pour générer le fichier openapi.json depuis l'API FastAPI
"""
import sys
from pathlib import Path
import json

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api.main import app


def generate_openapi_json():
    """Génère le fichier openapi.json depuis l'application FastAPI"""

    # Récupérer le schéma OpenAPI
    openapi_schema = app.openapi()

    # Chemin de sortie
    output_path = Path(__file__).parent.parent / 'openapi.json'

    # Écrire le fichier JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"✓ Schéma OpenAPI généré: {output_path}")
    print(f"  Version: {openapi_schema.get('info', {}).get('version', 'unknown')}")
    print(f"  Titre: {openapi_schema.get('info', {}).get('title', 'unknown')}")

    # Afficher les endpoints avec rapport_paiement
    paths_with_rapport = []
    for path, methods in openapi_schema.get('paths', {}).items():
        for method, details in methods.items():
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                params = details.get('requestBody', {}).get('content', {}).get('multipart/form-data', {}).get('schema', {}).get('properties', {})
                if 'rapport_paiement' in params:
                    paths_with_rapport.append(f"{method.upper()} {path}")

    if paths_with_rapport:
        print(f"\n✓ Endpoints avec paramètre 'rapport_paiement':")
        for endpoint in paths_with_rapport:
            print(f"  - {endpoint}")
    else:
        print(f"\n⚠️  Aucun endpoint trouvé avec paramètre 'rapport_paiement'")

    return output_path


if __name__ == '__main__':
    try:
        output_file = generate_openapi_json()
        print(f"\n✅ Fichier OpenAPI généré avec succès!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur lors de la génération: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
