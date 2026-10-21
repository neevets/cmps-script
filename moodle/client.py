import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import MoodleEvent

log = logging.getLogger(__name__)


class MoodleClient:
    def __init__(self, config):
        self.base_url = config["base_url"].rstrip("/")
        self.token = config.get("token", "")
        self.cookie = config.get("cookie", "")
        self.use_cookie = config.get("use_cookie", True)
        self.verify_ssl = config.get("verify_ssl", True)

        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self.session.headers.update({
            "User-Agent": "cmps-script/1.0",
        })

        if self.use_cookie:
            self.session.headers["Cookie"] = self.cookie

    def _rest(self, function: str, params: dict):
        data = {
            "wstoken": self.token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
        }
        data.update(params)

        response = self.session.post(
            f"{self.base_url}/webservice/rest/server.php",
            data=data,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and payload.get("exception"):
            raise RuntimeError(f"Moodle API error: {payload}")

        return payload

    def get_upcoming_events(self, lookahead_days: int):
        if not self.use_cookie and self.token:
            return self._events_from_api(lookahead_days)

        return self._events_from_cookie(lookahead_days)

    def _events_from_api(self, lookahead_days: int):
        site = self._rest("core_webservice_get_site_info", {})
        user_id = site["userid"]

        courses = self._rest("core_enrol_get_users_courses", {"userid": user_id})
        course_names = {course["id"]: course["fullname"] for course in courses}

        now = int(time.time())
        until = now + lookahead_days * 86400

        api_params = {
            "timefrom": now,
            "timeto": until,
            "limitnum": 200,
        }
        for index, course_id in enumerate(course_names):
            api_params[f"courseids[{index}]"] = course_id

        events = self._rest(
            "core_calendar_get_action_events_by_courses",
            api_params,
        )

        result = []
        for event in events.get("events", []):
            due_at = int(event.get("timestart", 0))
            if due_at <= 0:
                continue

            course_id = event.get("courseid")
            url = event.get("url", "") or ""
            activity_type = event.get("modulename", "") or event.get("eventtype", "")

            result.append(MoodleEvent(
                course=course_names.get(course_id, f"Curso {course_id}"),
                title=event.get("name", "Actividad de Moodle"),
                due_at=due_at,
                url=url if url.startswith("http") else urljoin(self.base_url, url),
                activity_type=activity_type,
            ))

        return result

    def _events_from_cookie(self, lookahead_days: int):
        url = f"{self.base_url}/calendar/view.php?view=upcoming"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        events = []
        now = int(time.time())
        max_due = now + lookahead_days * 86400

        blocks = soup.select('[data-region="event-item"]')

        if not blocks:
            blocks = soup.select(".calendar-event-panel, .eventlist .event")

        for block in blocks:
            link = block.select_one("a[href]")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")

            time_tag = block.select_one("time[datetime]")
            if not time_tag:
                continue

            try:
                due = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            except ValueError:
                continue

            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)

            due_at = int(due.timestamp())
            if not (now <= due_at <= max_due):
                continue

            course = "Curso de Moodle"
            course_tag = block.select_one(".event-course, .course, .eventname")
            if course_tag:
                course = course_tag.get_text(strip=True)

            full_url = href if href.startswith("http") else urljoin(self.base_url, href)

            events.append(MoodleEvent(
                course=course,
                title=title,
                due_at=due_at,
                url=full_url,
                activity_type="quiz" if "/mod/quiz/" in full_url else "assignment",
            ))

        if not events:
            log.warning(
                "No se han podido extraer eventos del calendario. "
                "La estructura HTML de Moodle puede haber cambiado o la cookie puede estar caducada."
            )

        return events
