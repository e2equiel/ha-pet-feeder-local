"""Bounded, on-demand composition of three Frigate recording timelines."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
_KEY = re.compile(r"[0-9a-f]{24}")


def timeline_offset(camera: str, recordings: list[dict[str, Any]], vod: dict[str, Any],
                    start: int, end: int) -> float:
    """Reject missing footage and account for Frigate's preceding keyframe."""
    cursor = float(start)
    for row in sorted(recordings, key=lambda row: row["start_time"]):
        if row["end_time"] <= cursor:
            continue
        if row["start_time"] > cursor + .35:
            raise ValueError("Recording timeline has a gap")
        cursor = max(cursor, row["end_time"])
    if cursor < end - .35:
        raise ValueError("Recording timeline ends before the requested interval")
    clip = vod["sequences"][0]["clips"][0]
    path = PurePosixPath(clip["path"])
    date, hour, name, filename = path.parts[-4:]
    if name != camera:
        raise ValueError("VOD camera mismatch")
    beginning = datetime.strptime(date + " " + hour + ":" + filename,
        "%Y-%m-%d %H:%M.%S.mp4").replace(tzinfo=UTC).timestamp() + clip.get("clipFrom", 0) / 1000
    offset = start - beginning
    available = sum(vod["durations"]) / 1000 - offset
    # Small inter-segment packet gaps can sum to less than one output frame
    # after 25x playback. Real wall-clock gaps were rejected above.
    if offset < -.35 or available < end - start - .8:
        raise ValueError("VOD does not cover the requested interval")
    return float(max(0., offset))


def collage_command(binary: str, base: str, cameras: list[str], offsets: list[float],
                    start: int, end: int, output: Path) -> list[str]:
    """Use one common wall-clock interval and 25x playback for every pane."""
    args = [binary, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-filter_complex_threads", "1"]
    filters = []
    duration = end - start
    for index, (camera, offset) in enumerate(zip(cameras, offsets, strict=True)):
        args += ["-threads", "1", "-rw_timeout", "15000000", "-protocol_whitelist", "http,tcp",
            "-i", f"{base}/vod/{camera}/start/{start}/end/{end}/index.m3u8"]
        width, height = (1280, 720) if index == 0 else (640, 360)
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS,trim=start={offset:.3f}:duration={duration},"
            f"setpts=0.04*(PTS-STARTPTS),fps=30,scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.04[v{index}]")
    filters += ["[v1][v2]hstack=inputs=2:shortest=1[bottom]",
        "[v0][bottom]vstack=inputs=2:shortest=1,format=yuv420p[out]"]
    return args + ["-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-threads", "2", "-b:v", "2500k", "-maxrate", "3500k", "-bufsize", "7000k",
        "-t", f"{duration / 25:.3f}", "-fs", "48000000", "-movflags", "+faststart", str(output)]


class CollageRenderer:
    """Own only hashed temporary files in a private HA media directory."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        media = hass.config.media_dirs
        root = media.get("local") or next(iter(media.values()), hass.config.path("media"))
        self.directory = Path(root) / ".pet_feeder_local_videos"

    def path(self, key: str, *, partial: bool = False) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError("Invalid video identity")
        return self.directory / (key + (".part" if partial else "") + ".mp4")

    async def async_prune(self, active: set[str]) -> None:
        """Remove orphaned files from interrupted, already completed jobs."""
        def prune() -> None:
            if self.directory.is_dir():
                for path in self.directory.iterdir():
                    key = path.name.removesuffix(".mp4").removesuffix(".part")
                    if _KEY.fullmatch(key) and key not in active and path.is_file():
                        path.unlink()
        await self.hass.async_add_executor_job(prune)

    async def async_cleanup(self, key: str) -> None:
        def clean() -> None:
            self.path(key).unlink(missing_ok=True)
            self.path(key, partial=True).unlink(missing_ok=True)
        await self.hass.async_add_executor_job(clean)

    async def async_render(self, key: str, base: str, cameras: list[str], offsets: list[float],
                           start: int, end: int) -> Path:
        output, partial = self.path(key), self.path(key, partial=True)
        if not await self.hass.async_add_executor_job(self.hass.config.is_allowed_path, str(output)):
            raise HomeAssistantError("The HA media directory is not allowed for Telegram files")
        await self.hass.async_add_executor_job(lambda: self.directory.mkdir(parents=True, exist_ok=True, mode=0o700))
        await self.async_cleanup(key)
        args = collage_command(get_ffmpeg_manager(self.hass).binary, base, cameras, offsets, start, end, partial)
        began = time.monotonic()
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        try:
            async with asyncio.timeout(180):
                await process.communicate()
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode:
            raise HomeAssistantError("Collage encoding failed")
        def finish() -> None:
            if not 1000 <= partial.stat().st_size < 48_000_000:
                raise HomeAssistantError("Collage size is outside the supported limit")
            partial.replace(output)
        await self.hass.async_add_executor_job(finish)
        _LOGGER.info("Feeding collage %s rendered in %.1fs", key, time.monotonic() - began)
        return output
