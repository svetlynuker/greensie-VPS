"""Založení uživatele v appce Greensie.
Spouštět z adresáře backend/ (s aktivním venv):
    python -m scripts.create_user
"""
import argparse

from app.auth.models import User
from app.auth.permissions import hash_heslo
from app.database import Base, SessionLocal, engine


def main():
    parser = argparse.ArgumentParser(description="Založí nového uživatele appky Greensie")
    parser.add_argument("--jmeno", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--heslo", required=True)
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Nastaví uživatele jako supersprávce (plný přístup ke všemu)",
    )
    parser.add_argument(
        "--extra-pravo",
        action="append",
        default=[],
        help="Individuální právo navíc (např. 'financie'), lze zadat vícekrát",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == args.email).first():
            print(f"Uživatel s e-mailem {args.email} už existuje.")
            return
        user = User(
            jmeno=args.jmeno,
            email=args.email,
            heslo_hash=hash_heslo(args.heslo),
            je_admin=args.admin,
            extra_prava=args.extra_pravo,
        )
        db.add(user)
        db.commit()
        print(f"Uživatel {args.email} (admin={args.admin}) založen.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
