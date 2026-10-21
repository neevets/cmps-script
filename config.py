import json
from pathlib import Path

DEFAULT_CONFIG = {
    "moodle": {
        "base_url": "",
        "token": "",
        "cookie": "",
        "use_cookie": True,
        "verify_ssl": True,
    },
    "schedule": {
        "deadline_hours": 48,
        "lookahead_days": 14,
        "timezone": "Europe/Madrid",
    },
    "whatsapp": {
        "provider": "callmebot",
        "api_key": "",
        "announce_recipients": [],
        "group_a_recipients": [],
        "group_b_recipients": [],
    },
    "routing": {
        "default": "announce",
        "courses": {},
    },
    "storage": {
        "database_path": "data/state.sqlite3",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str = "config.json") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Copia config.example.json a config.json y rellénalo."
        )

    with config_path.open("r", encoding="utf-8") as file:
        user_config = json.load(file)

    config = deep_merge(DEFAULT_CONFIG, user_config)

    if not config["moodle"]["base_url"]:
        raise ValueError("moodle.base_url es obligatorio")

    if config["moodle"]["use_cookie"] and not config["moodle"]["cookie"]:
        raise ValueError("moodle.cookie es obligatorio cuando use_cookie es true")

    if not config["moodle"]["use_cookie"] and not config["moodle"]["token"]:
        raise ValueError("moodle.token es obligatorio cuando use_cookie es false")

    if config["whatsapp"]["provider"] == "callmebot" and not config["whatsapp"]["api_key"]:
        raise ValueError("whatsapp.api_key es obligatorio para CallMeBot")

    return config
