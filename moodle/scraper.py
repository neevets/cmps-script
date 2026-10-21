"""Utilidades auxiliares para futuras mejoras del scraper."""

EXAM_KEYWORDS = ("quiz", "cuestionario", "examen", "test")


def looks_like_exam(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in EXAM_KEYWORDS)
