#!/usr/bin/env python3
"""
Registre des châssis : consultation et annulation d'un RFCV.

Un RFCV annulé par la société d'inspection (ex. éclaté en plusieurs RFCV) garde ses châssis dans
le registre : les nouveaux RFCV qui les reprennent sont alors refusés en doublon. Annuler le RFCV
déplace ses châssis dans l'historique des annulations (motif et date conservés).

Exemples :
    python registre.py annuler RCSA6014576 --motif "Annulé par la société d'inspection, éclaté en 6014621 et ..."
    python registre.py annuler 6014576 --motif "..." --chassis LC6PCJK20T0B14898 LC6PCJK20T0B14903
    python registre.py annulations [--rfcv 6014576]
    python registre.py restaurer RCSA6014576        # erreur d'annulation : remet les châssis
    python registre.py chercher LC6PCJK20T0B14898
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from chassis_registry import ChassisRegistry, get_registry


def _registry(db: str | None) -> ChassisRegistry:
    return ChassisRegistry(db) if db else get_registry()


def cmd_annuler(args) -> int:
    reg = _registry(args.db)
    try:
        cancelled = reg.cancel_rfcv(args.rfcv, args.motif, args.chassis)
    except ValueError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    if not cancelled:
        print(f"Aucun châssis enregistré pour le RFCV {args.rfcv} : rien à annuler.", file=sys.stderr)
        return 1
    print(f"RFCV {args.rfcv} annulé : {len(cancelled)} châssis libéré(s) ({args.motif}).")
    if args.chassis:
        missing = sorted({c.upper() for c in args.chassis} - set(cancelled))
        if missing:
            print(f"Non trouvés pour ce RFCV : {', '.join(missing)}", file=sys.stderr)
    return 0


def cmd_restaurer(args) -> int:
    r = _registry(args.db).restore_rfcv(args.rfcv)
    if not r["restored"] and not r["conflicts"]:
        print(f"Aucune annulation en cours pour le RFCV {args.rfcv}.", file=sys.stderr)
        return 1
    print(f"RFCV {args.rfcv} restauré : {len(r['restored'])} châssis.")
    if r["conflicts"]:
        print(f"{len(r['conflicts'])} châssis repris entre-temps par un autre RFCV, non restaurés : "
              + ", ".join(r["conflicts"][:10]) + (" …" if len(r["conflicts"]) > 10 else ""), file=sys.stderr)
    return 0


def cmd_annulations(args) -> int:
    rows = _registry(args.db).get_cancelled(rfcv_number=args.rfcv)
    if not rows:
        print("Aucune annulation.")
        return 0
    groups: dict = {}
    for r in rows:
        key = (r["rfcv_number"], r["cancelled_at"], r["reason"], r["restored_at"])
        groups.setdefault(key, []).append(r["chassis_number"])
    for (rfcv, at, reason, restored), chassis in groups.items():
        state = f"restauré le {restored[:10]}" if restored else "annulé"
        print(f"{rfcv}  {len(chassis)} châssis  {state}  ({at[:10]})  motif : {reason}")
        if args.details:
            for c in chassis:
                print(f"    {c}")
    return 0


def cmd_chercher(args) -> int:
    reg = _registry(args.db)
    entry = reg.get_entry(args.chassis)
    history = reg.get_cancelled(chassis_number=args.chassis)
    if entry:
        print(f"{entry['chassis_number']} : {entry['table']}, RFCV {entry['rfcv_number']}, "
              f"fichier {entry['filename']}, enregistré le {entry['registered_at'][:10]}")
    else:
        print(f"{args.chassis.upper()} : absent du registre actif")
    for h in history:
        state = f", restauré le {h['restored_at'][:10]}" if h["restored_at"] else ""
        print(f"  annulé le {h['cancelled_at'][:10]} (RFCV {h['rfcv_number']}{state}) : {h['reason']}")
    return 0 if entry or history else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Registre des châssis : consultation et annulation d'un RFCV",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--db", help="Base SQLite du registre (défaut : data/chassis_registry.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("annuler", help="Annuler un RFCV : ses châssis ne bloquent plus un nouveau RFCV")
    a.add_argument("rfcv", help="N° RFCV (RCSA6014576 ou 6014576)")
    a.add_argument("--motif", required=True, help="Motif de l'annulation (conservé dans l'historique)")
    a.add_argument("--chassis", nargs="+", help="Limiter l'annulation à ces châssis du RFCV")
    a.set_defaults(func=cmd_annuler)

    r = sub.add_parser("restaurer", help="Annuler une annulation (remet les châssis du RFCV)")
    r.add_argument("rfcv")
    r.set_defaults(func=cmd_restaurer)

    h = sub.add_parser("annulations", help="Historique des annulations")
    h.add_argument("--rfcv", help="Filtrer sur un RFCV")
    h.add_argument("--details", action="store_true", help="Lister les châssis")
    h.set_defaults(func=cmd_annulations)

    c = sub.add_parser("chercher", help="État d'un châssis : registre actif et annulations")
    c.add_argument("chassis")
    c.set_defaults(func=cmd_chercher)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
