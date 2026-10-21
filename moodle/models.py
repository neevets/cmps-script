from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class MoodleEvent:
    course: str
    title: str
    due_at: int
    url: str = ""
    activity_type: str = ""

    @property
    def is_exam(self) -> bool:
        haystack = f"{self.title} {self.url} {self.activity_type}".lower()
        return any(word in haystack for word in ("quiz", "cuestionario", "examen", "test"))

    @property
    def key(self) -> str:
        raw = f"{self.course}|{self.title}|{self.due_at}|{self.url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
