import os

USERNAME_ENV = "LEVA_PADOVA_USERNAME"
PASSWORD_ENV = "LEVA_PADOVA_PASSWORD"


def _load_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"La variabile d'ambiente {var_name} non è impostata")
    return value


class Secrets:
    username = _load_env(USERNAME_ENV)
    password = _load_env(PASSWORD_ENV)
