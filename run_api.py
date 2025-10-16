#!/usr/bin/env python3
"""
Script de démarrage de l'API FastAPI
"""
import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import uvicorn
from api.core.config import settings


def main():
    """Lance le serveur API"""
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║  API Convertisseur PDF RFCV → XML ASYCUDA                         ║
║  Version: {settings.api_version}                                              ║
╚════════════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
