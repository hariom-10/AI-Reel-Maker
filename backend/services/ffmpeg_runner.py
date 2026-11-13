import tempfile
import subprocess
from typing import Callable, Optional, Sequence


def run_ffmpeg(
    command: Sequence[str],
    duration: float,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    loglevel: str = "error",
) -> str:
    """Run FFmpeg with progress updates and terminate promptly when cancelled."""
    invocation = [
        command[0],
        "-hide_banner",
        "-loglevel",
        loglevel,
        "-nostats",
        "-progress",
        "pipe:1",
        *command[1:],
    ]
    with tempfile.TemporaryFile() as error_stream:
        process = subprocess.Popen(
            invocation,
            stdout=subprocess.PIPE,
            stderr=error_stream,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        last_percent = -1

        try:
            if process.stdout is None:
                raise RuntimeError("FFmpeg progress stream was not created.")

            for line in process.stdout:
                if not progress_callback or not line.startswith("out_time_ms="):
                    continue
                try:
                    elapsed = int(line.partition("=")[2]) / 1_000_000
                except ValueError:
                    continue
                percent = min(99, max(0, int(elapsed / max(duration, 0.1) * 100)))
                if percent != last_percent:
                    progress_callback(percent, "Rendering video...")
                    last_percent = percent

            return_code = process.wait()
            error_stream.seek(0)
            diagnostics = error_stream.read().decode("utf-8", errors="replace")
            if return_code:
                raise subprocess.CalledProcessError(
                    return_code,
                    invocation,
                    output=diagnostics[-4000:],
                )
            return diagnostics
        except BaseException:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
