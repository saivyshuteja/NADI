from pathlib import Path


def transcribe_audio(path: Path) -> str:
    """Assignment pack audio may be absent; text stand-ins are the transcript."""
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8")
    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")
    raise RuntimeError(f"no transcript available for {path}")
