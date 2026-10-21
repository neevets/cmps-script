class NotificationRouter:
    def __init__(self, config):
        self.default = config.get("default", "announce")
        self.course_routes = {
            course.lower(): route
            for course, route in config.get("courses", {}).items()
        }

    def route_for(self, course: str) -> str:
        return self.course_routes.get(course.lower(), self.default)

    def recipients_for(self, course: str, whatsapp_config: dict) -> list[str]:
        route = self.route_for(course)

        if route == "group_a":
            return whatsapp_config.get("group_a_recipients", [])

        if route == "group_b":
            return whatsapp_config.get("group_b_recipients", [])

        if route == "all":
            return list(dict.fromkeys(
                whatsapp_config.get("announce_recipients", [])
                + whatsapp_config.get("group_a_recipients", [])
                + whatsapp_config.get("group_b_recipients", [])
            ))

        return whatsapp_config.get("announce_recipients", [])
