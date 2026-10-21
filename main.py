import logging
from datetime import datetime, timedelta, timezone

from config import load_config
from moodle.client import MoodleClient
from notifications.callmebot import CallMeBotSender
from notifications.router import NotificationRouter
from storage.state import StateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cmps-script")


def format_event(event, now):
    due = datetime.fromtimestamp(event.due_at, tz=timezone.utc)
    remaining = due - now
    hours = max(1, int(remaining.total_seconds() // 3600))

    if hours <= 24:
        urgency = "🔴"
        when = f"en {hours} h"
    else:
        urgency = "🟠"
        when = f"en {hours // 24} días"

    kind = "Examen/Cuestionario" if event.is_exam else "Tarea/Actividad"

    lines = [
        f"{urgency} *Moodle — entrega {when}*",
        "",
        f"*{event.title}*",
        f"Curso: {event.course}",
        f"Tipo: {kind}",
        f"Fecha límite: {due.astimezone().strftime('%d/%m/%Y %H:%M')}",
    ]

    if event.url:
        lines.append("")
        lines.append(event.url)

    return "\n".join(lines)


def main():
    config = load_config()
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=config["schedule"]["deadline_hours"])

    client = MoodleClient(config["moodle"])
    events = client.get_upcoming_events(
        lookahead_days=config["schedule"]["lookahead_days"]
    )

    pending = [event for event in events if now <= event.due_at <= deadline]
    log.info("Encontrados %d eventos próximos; %d dentro del umbral", len(events), len(pending))

    if not pending:
        return

    store = StateStore(config["storage"]["database_path"])
    router = NotificationRouter(config["routing"])
    sender = CallMeBotSender(config["whatsapp"])

    try:
        for event in pending:
            if store.is_notified(event.key):
                continue

            message = format_event(event, now)
            recipients = router.recipients_for(event.course, config["whatsapp"])

            if not recipients:
                log.warning("Sin destinatarios para el curso: %s", event.course)
                continue

            sender.send(message, recipients)
            store.mark_notified(event.key)
            log.info("Notificado: %s — %s", event.course, event.title)
    finally:
        store.close()


if __name__ == "__main__":
    main()
