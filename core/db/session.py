"""
Builds the DSN the DB test suite connects with.
"""


def build_dsn(host: str, port: str, name: str, user: str, password: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
