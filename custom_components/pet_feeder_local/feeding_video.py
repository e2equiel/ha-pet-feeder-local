"""Durable Frigate-to-Telegram notifications, separate from feeder control."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import json
import logging
import math
import re
import secrets
import time
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import probatio as vol
from aiohttp import ClientError, ClientSession
from homeassistant.components import persistent_notification
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .video_collage import CollageRenderer, timeline_offset

_LOGGER = logging.getLogger(__name__)
SERVICE = "queue_feeding_video"
_ERRORS = (ClientError, TimeoutError, HomeAssistantError, ValueError, KeyError, OSError, IndexError)


class FeedingVideoNotifications:
    """Keep ownership of every export until it is removed by its Frigate ID."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session: ClientSession = async_get_clientsession(hass)
        self.store: Store[dict[str, Any]] = Store(hass, 1, DOMAIN + ".feeding_videos")
        self.data: dict[str, Any] = {"seen": [], "jobs": []}
        self.save_lock = asyncio.Lock()
        self.worker: asyncio.Task[None] | None = None
        self.stopping = False
        self.renderer = CollageRenderer(hass)

    async def async_setup(self) -> None:
        self.data = await self.store.async_load() or self.data
        try:
            await self.renderer.async_prune({job["key"] for job in self.data["jobs"]})
        except OSError:
            _LOGGER.warning("Temporary video pruning failed; owned cleanup remains queued")
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self.hass.services.async_register(DOMAIN, SERVICE, self.async_enqueue,
            schema=vol.Schema({
                vol.Required("event_id"): str, vol.Required("occurred_at"): str,
                vol.Required("frigate_url"): str, vol.Required("camera"): str,
                vol.Required("telegram_config_entry_id"): str,
                vol.Optional("feeder_name", default="Pet feeder"): str,
                vol.Optional("caption", default="Scheduled feeding · 25× · no audio"): str,
                vol.Optional("detail_cameras", default=[]): vol.All([str], vol.Length(max=2)),
                vol.Optional("record_detail_cameras", default=False): bool,
                vol.Optional("caption_options", default=[]): vol.All(
                    [vol.All(str, vol.Length(min=1, max=500))], vol.Length(max=100)),
                vol.Optional("pre_seconds", default=15): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                vol.Optional("post_seconds", default=225): vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
            }), supports_response=SupportsResponse.OPTIONAL)
        self._start_worker()

    async def _save(self) -> None:
        async with self.save_lock:
            await self.store.async_save(copy.deepcopy(self.data))

    def _start_worker(self) -> None:
        if self.data["jobs"] and self.worker is None and not self.stopping:
            self.worker = self.hass.async_create_background_task(self._run(), DOMAIN + " feeding videos")

    async def async_stop(self, _event: Event) -> None:
        self.stopping = True
        if self.worker is not None:
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker

    async def async_enqueue(self, call: ServiceCall) -> dict[str, Any]:
        d = call.data
        details = d.get("detail_cameras", [])
        choices = d.get("caption_options", [])
        event_id = d["event_id"]
        url = urlsplit(d["frigate_url"])
        occurred = dt_util.parse_datetime(d["occurred_at"])
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", event_id)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", d["camera"])
            or (details and (len(details) != 2 or len(set([d["camera"], *details])) != 3
                or any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", camera) for camera in details)))
            or (d.get("record_detail_cameras") and not details)
            or len(choices) > 100 or any(not c.strip() or len(c) > 500 for c in choices)
            or occurred is None or occurred.tzinfo is None):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_video_request")
        stamp = occurred.timestamp()
        age = dt_util.utcnow().timestamp() - stamp
        if not -10 <= age <= 600:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="stale_video_event")
        if event_id in self.data["seen"]:
            return {"queued": False, "duplicate": True}
        if len(self.data["jobs"]) >= 16:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="video_queue_full")
        endpoint = d["frigate_url"].rstrip("/")
        for job in self.data["jobs"]:
            if (job["phase"] == "waiting" and abs(stamp-job["occurred"]) <= 45
                and (job["base"], job["camera"], job["telegram"]) ==
                    (endpoint, d["camera"], d["telegram_config_entry_id"])):
                if job.get("detail_cameras", []) != details:
                    continue
                if job.get("record_detail_cameras", False) != d.get("record_detail_cameras", False):
                    continue
                job["start"] = min(job["start"], stamp-d["pre_seconds"])
                job["end"] = max(job["end"], stamp+d["post_seconds"])
                if d["feeder_name"] not in job["feeders"]:
                    job["feeders"].append(d["feeder_name"])
                break
        else:
            key = hashlib.sha256(event_id.encode()).hexdigest()[:24]
            job = {"key": key, "name": "PF Notify " + key, "base": endpoint,
                "camera": d["camera"], "telegram": d["telegram_config_entry_id"],
                "occurred": stamp, "start": stamp-d["pre_seconds"], "end": stamp+d["post_seconds"],
                "caption": self._caption(d), "feeders": [d["feeder_name"]],
                "detail_cameras": list(details),
                "record_detail_cameras": d.get("record_detail_cameras", False),
                "phase": "waiting", "export_id": None}
            self.data["jobs"].append(job)
        self.data["seen"] = (self.data["seen"] + [event_id])[-256:]
        await self._save()
        await self._capture_details(job)
        self._start_worker()
        return {"queued": True, "duplicate": False, "job_id": job["key"]}

    def _caption(self, data: Any) -> str:
        """Persist a shuffled deck; merging/retrying never consumes a new phrase."""
        options = list(dict.fromkeys(c.strip() for c in data.get("caption_options", [])))
        if not options:
            return str(data["caption"])
        identity = hashlib.sha256(json.dumps([data["telegram_config_entry_id"], options]).encode()).hexdigest()[:24]
        decks = self.data.setdefault("caption_decks", {})
        if identity not in decks and len(decks) >= 16:
            decks.pop(next(iter(decks)))
        deck = decks.setdefault(identity, {"remaining": [], "last": None})
        if not deck["remaining"]:
            deck["remaining"] = options.copy()
            secrets.SystemRandom().shuffle(deck["remaining"])
            if len(options) > 1 and deck["remaining"][-1] == deck["last"]:
                deck["remaining"][0], deck["remaining"][-1] = deck["remaining"][-1], deck["remaining"][0]
        phrase = str(deck["remaining"].pop())
        deck["last"] = phrase
        return phrase

    async def _capture_details(self, job: dict[str, Any]) -> None:
        """Retain a finite recording window immediately, independently of rendering."""
        if not job.get("record_detail_cameras") or job["end"] <= dt_util.utcnow().timestamp():
            return
        for camera in job.get("detail_cameras", []):
            attempted = job.setdefault("capture_attempted", [])
            if camera in attempted:
                continue
            # Persist before POST. An uncertain request is never blindly repeated;
            # every server-side recording window has its own finite duration.
            attempted.append(camera)
            await self._save()
            now = dt_util.utcnow().timestamp()
            try:
                pre = max(0, math.ceil(now - job["start"]))
                if pre > 60:
                    raise ValueError("Recording prebuffer has already elapsed")
                response = await self._request(job, f"events/{camera}/feeding_window/create", {
                    "include_recording": True, "pre_capture": pre,
                    "duration": max(1, math.ceil(job["end"] - now) + 45),
                    "sub_label": "PF Notify " + job["key"]})
                if not response.get("success") or not response.get("event_id"):
                    raise HomeAssistantError("Frigate did not acknowledge the recording window")
                job.setdefault("capture_events", {})[camera] = response["event_id"]
                await self._save()
            except _ERRORS:
                self._warn(job, "A detail-camera recording window could not be confirmed. Incomplete footage will use the overhead fallback.")

    async def _request(self, job: dict[str, Any], path: str, body: dict[str, Any] | None = None,
                       *, missing_ok: bool = False) -> Any:
        if body is None:
            path += ("&" if "?" in path else "?") + "notification_read=" + str(time.monotonic_ns())
        async with asyncio.timeout(30):
            async with self.session.request("GET" if body is None else "POST",
                job["base"] + "/api/" + path, json=body, allow_redirects=False) as response:
                if missing_ok and response.status == 404:
                    return None
                if not 200 <= response.status < 300:
                    raise HomeAssistantError(f"Frigate returned HTTP {response.status}")
                return await response.json()

    def _warn(self, job: dict[str, Any], message: str) -> None:
        _LOGGER.warning("Feeding video %s: %s", job["key"], message)
        persistent_notification.async_create(self.hass, message,
            title="Pet Feeder Local video", notification_id=DOMAIN + "_video_" + job["key"])

    async def _find_export(self, job: dict[str, Any]) -> dict[str, Any] | None:
        exports = await self._request(job, "exports")
        matches = [e for e in exports if e["camera"] == job["camera"] and e["name"] == job["name"]]
        if not matches:
            # A queued/running export may not have a catalog record yet.
            active = await self._request(job, "jobs/export")
            matches = [e for e in active if e["camera"] == job["camera"] and e["name"] == job["name"]]
        if len(matches) > 1:
            raise HomeAssistantError("Multiple exports have the same notification identity")
        return matches[0] if matches else None

    async def _cleanup(self, job: dict[str, Any]) -> bool:
        if job.get("local_video"):
            await self.renderer.async_cleanup(job["key"])
            return True
        if not job["export_id"]:
            export = await self._find_export(job)
            if export is None:
                # An uncertain create request can still be queued. Keep ownership
                # for ten minutes; never issue the create request a second time.
                return dt_util.utcnow().timestamp() > float(job["end"]) + 600
            job["export_id"] = export["id"]
            await self._save()
        export = await self._request(job, "exports/" + job["export_id"], missing_ok=True)
        if export is None:
            active = await self._request(job, "jobs/export/" + job["export_id"], missing_ok=True)
            if active and active.get("status") in ("queued", "running"):
                return False
            return True
        if export["camera"] != job["camera"] or export["name"] != job["name"]:
            raise HomeAssistantError("Export ownership mismatch; deletion refused")
        if export.get("in_progress"):
            return False
        result = await self._request(job, "exports/delete", {"ids": [job["export_id"]]})
        if not result.get("success"):
            raise HomeAssistantError("Frigate refused export cleanup")
        return True

    async def _process(self, job: dict[str, Any]) -> bool:
        if job["phase"] == "waiting":
            await self._capture_details(job)
            while (remaining := job["end"] + 20-dt_util.utcnow().timestamp()) > 0:
                await asyncio.sleep(min(remaining, 30))
            if job.get("detail_cameras") and not job.get("collage_fallback"):
                job["phase"], job["local_video"] = "rendering", True
                await self._save()
        if job["phase"] == "rendering":
            start, end = math.floor(job["start"]), math.ceil(job["end"])
            cameras = [job["camera"], *job["detail_cameras"]]
            try:
                offsets = []
                for camera in cameras:
                    recordings = await self._request(job, f"{camera}/recordings?after={start}&before={end}")
                    vod = await self._request(job, f"vod/{camera}/start/{start}/end/{end}")
                    offsets.append(timeline_offset(camera, recordings, vod, start, end))
                await self.renderer.async_render(job["key"], job["base"], cameras, offsets, start, end)
            except _ERRORS:
                await self.renderer.async_cleanup(job["key"])
                job["local_video"], job["collage_fallback"], job["phase"] = False, True, "waiting"
                self._warn(job, "Collage unavailable or recording timeline incomplete. Sending the overhead view instead.")
                await self._save()
                return False
            job["phase"] = "ready"
            await self._save()
        if job["phase"] == "ready":
            await self._send(job, {"file": str(self.renderer.path(job["key"]))})
        if job["phase"] == "waiting":
            job["phase"] = "creating"
            await self._save()
            # Explicit custom endpoint: the normal 0.18 API no longer takes
            # the legacy playback_factor argument used by older HA clients.
            result = await self._request(job,
                f"export/custom/{job['camera']}/start/{job['start']}/end/{job['end']}",
                {"name": job["name"], "source": "recordings", "ffmpeg_input_args": "-an",
                 "ffmpeg_output_args": "-vf setpts=0.04*PTS -r 30 -an -b:v 2500k -maxrate 3500k -bufsize 7000k",
                 "cpu_fallback": True})
            export_id = result.get("export_id")
            if not result.get("success") or not isinstance(export_id, str) or not re.fullmatch(r"[\w-]+", export_id):
                raise HomeAssistantError("Frigate did not return an export identity")
            job["export_id"], job["phase"] = export_id, "exporting"
            await self._save()
        if job["phase"] == "creating":
            recovered = await self._find_export(job)
            if recovered is None:
                if dt_util.utcnow().timestamp() <= float(job["end"]) + 600:
                    return False
                self._warn(job, "Export creation was uncertain and no matching export appeared. No create retry was issued.")
                return True
            job["export_id"], job["phase"] = recovered["id"], "exporting"
            await self._save()
        if job["phase"] == "exporting":
            async with asyncio.timeout(180):
                while True:
                    export = await self._request(job, "exports/" + job["export_id"], missing_ok=True)
                    if export is not None and not export.get("in_progress"):
                        break
                    status = await self._request(job, "jobs/export/" + job["export_id"], missing_ok=True)
                    if status and status.get("status") in ("failed", "cancelled"):
                        raise HomeAssistantError("Frigate export failed")
                    await asyncio.sleep(2)
            path = PurePosixPath(export["video_path"])
            if (export["camera"] != job["camera"] or export["name"] != job["name"]
                or path.parent != PurePosixPath("/media/frigate/exports") or path.suffix != ".mp4"):
                raise HomeAssistantError("Export ownership or path mismatch")
            await self._send(job, {"url": job["base"] + "/exports/" + path.name})
        elif job["phase"] == "sending":
            self._warn(job, "HA stopped during a Telegram send. Delivery is uncertain; the video was not resent.")
        job["phase"] = "cleanup"
        await self._save()
        return await self._cleanup(job)

    async def _send(self, job: dict[str, Any], source: dict[str, str]) -> None:
        # Persist before Telegram. An interrupted send is never blindly repeated.
        job["phase"] = "sending"
        await self._save()
        async with asyncio.timeout(120):
            response = await self.hass.services.async_call("telegram_bot", "send_video", {
                "config_entry_id": job["telegram"], **source, "parse_mode": "plain_text",
                "caption": job["caption"] + "\n" + ", ".join(job["feeders"])},
                blocking=True, return_response=True)
        if not response or not response.get("chats"):
            raise HomeAssistantError("Telegram did not return a delivery response")
        job["phase"] = "sent"
        await self._save()

    async def _run(self) -> None:
        try:
            while self.data["jobs"]:
                job = self.data["jobs"][0]
                try:
                    done = await (self._cleanup(job) if job["phase"] == "cleanup" else self._process(job))
                except _ERRORS as err:
                    self._warn(job, f"Video notification failed ({type(err).__name__}). Cleanup will continue; no automatic resend.")
                    job["phase"] = "cleanup"
                    await self._save()
                    done = False
                if done:
                    self.data["jobs"].remove(job)
                    await self._save()
                else:
                    # An unavailable Frigate or in-progress export does not block
                    # later meals forever. Keep the cleanup job durably queued.
                    self.data["jobs"].append(self.data["jobs"].pop(0))
                    await self._save()
                    await asyncio.sleep(30)
        finally:
            self.worker = None
