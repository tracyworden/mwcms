"""CLI command to create a user in DynamoDB User_Table.

Usage: python -m app.cli.create_user <username> <password>
"""

import sys

import bcrypt

from app.api.auth.models import UserRecord, put_user


def create_user(username: str, password: str) -> None:
    """Hash the password with bcrypt and write the user record to DynamoDB."""
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = UserRecord(username=username, password_hash=password_hash)
    put_user(user)
    print(f"User '{username}' created successfully.")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m app.cli.create_user <username> <password>", file=sys.stderr)
        sys.exit(1)
    create_user(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
