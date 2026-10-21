import logging
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)


class CallMeBotSender:
    def __init__(self, config):
        self.api_key = config["api_key"]
        self.session = requests.Session()

    def send(self, message: str, recipients: list[str]):
        for phone in recipients:
            url = (
                "https://api.callmebot.com/whatsapp.php"
                f"?phone={quote(phone)}"
                f"&text={quote(message)}"
                f"&apikey={quote(self.api_key)}"
            )

            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                log.info("Mensaje enviado a %s", phone)
            except requests.RequestException as error:
                log.error("Error enviando a %s: %s", phone, error)
