#!/usr/bin/env python
import sys


def main():
    # Variable d'environnement, puis .env, puis dev avec avertissement : config/bootstrap.py.
    from config.bootstrap import configure_settings_module

    configure_settings_module()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Vérifiez qu'il est installé et que "
            "votre environnement virtuel est activé."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
