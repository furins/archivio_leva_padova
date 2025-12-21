import os

USERNAME_ENV = "LEVA_PADOVA_USERNAME"
PASSWORD_ENV = "LEVA_PADOVA_PASSWORD"


class _EnvVar:
    def __init__(self, var_name: str):
        self.var_name = var_name

    def __get__(self, instance, owner):
        value = os.getenv(self.var_name)
        if not value:
            raise RuntimeError(
                f"La variabile d'ambiente {self.var_name} non è impostata"
            )
        return value


class Secrets:
    username = _EnvVar(USERNAME_ENV)
    password = _EnvVar(PASSWORD_ENV)
