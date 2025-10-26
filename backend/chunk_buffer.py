from dataclasses import dataclass
from collections import deque

@dataclass
class Segment:
    start: float
    end: float
    text: str

class ChunkBuffer:
    def __init__(self, maxlen: int = 2000):
        self._segments: deque[Segment] = deque(maxlen=maxlen)

    def add(self, start: float, end: float, text: str) -> None:
        t = (text or "").strip()
        if not t:
            return
        if any(s.text == t for s in list(self._segments)[-5:]):
            return
        self._segments.append(Segment(float(start), float(end), t))

    def to_txt(self) -> str:
        return " ".join(s.text for s in self._segments)

    def to_srt(self) -> str:
        def fmt(ts: float) -> str:
            ts = float(ts)
            h = int(ts // 3600)
            m = int((ts % 3600) // 60)
            s = int(ts % 60)
            ms = int((ts - int(ts)) * 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"
        lines = []
        for i, seg in enumerate(self._segments, start=1):
            lines.append(str(i))
            lines.append(f"{fmt(seg.start)} --> {fmt(seg.end)}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)
