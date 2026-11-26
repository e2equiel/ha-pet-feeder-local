"""Notification ownership, merging, restart recovery and failure cleanup."""

import asyncio
import copy
import math
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientConnectionError
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.pet_feeder_local.feeding_video import SERVICE, FeedingVideoNotifications
from .test_video_collage import timeline


def call(event_id="event-1", feeder="Feeder 1", **changes):
    return ServiceCall(
        None,
        "pet_feeder_local",
        SERVICE,
        {
            "event_id": event_id,
            "feeder_name": feeder,
            "occurred_at": (dt_util.utcnow() - timedelta(seconds=300)).isoformat(),
            "frigate_url": "http://frigate.local:5000",
            "camera": "comederos",
            "telegram_config_entry_id": "telegram-entry",
            "caption": "Synthetic test",
            "pre_seconds": 15,
            "post_seconds": 225,
            **changes,
        },
    )


async def manager(hass):
    m = FeedingVideoNotifications(hass)
    m.store.async_load = AsyncMock(return_value=None)
    m.store.async_save = AsyncMock()
    m._start_worker = Mock()
    await m.async_setup()
    return m


async def test_caption_deck_survives_restart_and_merging_consumes_no_phrase(hass):
    m = await manager(hass)
    options = ["Dinner is served", "The buffet is open", "A meal for the crew"]
    first = call(caption_options=options)
    await m.async_enqueue(first)
    chosen = m.data["jobs"][0]["caption"]
    snapshot = copy.deepcopy(m.data["caption_decks"])
    await m.async_enqueue(call("merged", "Feeder 3", occurred_at=first.data["occurred_at"], caption_options=options))
    assert m.data["caption_decks"] == snapshot
    assert (await m.async_enqueue(first))["duplicate"]
    resumed = FeedingVideoNotifications(hass)
    resumed.store.async_load = AsyncMock(return_value=copy.deepcopy(m.data))
    resumed.store.async_save = AsyncMock(); resumed._start_worker = Mock()
    await resumed.async_setup()
    phrases = [chosen]
    for index in range(2):
        phrases.append(resumed._caption({"caption_options": options, "telegram_config_entry_id": "telegram-entry"}))
    assert len(set(phrases)) == 3
    # At a new cycle boundary the last phrase still must not repeat.
    deck = next(iter(resumed.data["caption_decks"].values()))
    deck["remaining"], deck["last"] = [], options[-1]
    with patch("custom_components.pet_feeder_local.feeding_video.secrets.SystemRandom"):
        assert resumed._caption(first.data) != options[-1]
    resumed.data["caption_decks"] = {str(n): {} for n in range(16)}
    resumed._caption(first.data)
    assert len(resumed.data["caption_decks"]) == 16


@pytest.mark.parametrize("changes", [
    {"detail_cameras": ["one"]}, {"detail_cameras": ["one", "one"]},
    {"detail_cameras": ["one", "../two"]}, {"detail_cameras": ["one", "comederos"]},
    {"caption_options": ["  "]}, {"caption_options": ["x" * 501]}, {"caption_options": ["x"] * 101},
    {"record_detail_cameras": True},
])
async def test_invalid_collage_and_caption_plans_do_not_reach_network(hass, changes):
    m = await manager(hass)
    with pytest.raises(ServiceValidationError): await m.async_enqueue(call(**changes))
    assert not m.data["jobs"]


async def test_different_collage_and_capture_plans_do_not_merge(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    await m.async_enqueue(call("collage", detail_cameras=["left", "right"]))
    await m.async_enqueue(call("capture", detail_cameras=["left", "right"], record_detail_cameras=True))
    assert len(m.data["jobs"]) == 3


async def test_collage_sends_one_local_file_and_cleans_only_owned_files(hass):
    m = await manager(hass)
    await m.async_enqueue(call(detail_cameras=["left", "right"]))
    job = m.data["jobs"][0]; start, end = math.floor(job["start"]), math.ceil(job["end"])
    responses = []
    for camera in ["comederos", "left", "right"]: responses.extend(timeline(camera, start, end))
    m._request = AsyncMock(side_effect=responses)
    m.renderer.async_render = AsyncMock(); m.renderer.async_cleanup = AsyncMock()
    sent = []
    async def telegram(service):
        sent.append(service.data)
        assert job["phase"] == "sending"
        return {"chats": [{"message_id": 1}]}
    hass.services.async_register("telegram_bot", "send_video", telegram, supports_response=SupportsResponse.OPTIONAL)
    assert await m._process(job)
    assert len(sent) == 1 and sent[0]["file"].endswith(job["key"] + ".mp4") and "url" not in sent[0]
    assert m._request.await_count == 6  # Read-only timeline inspection, no export POSTs.
    m.renderer.async_cleanup.assert_awaited_once_with(job["key"])
    m.renderer.async_render.assert_awaited_once()
    job["phase"] = "ready"; m.renderer.async_render.reset_mock()
    assert await m._process(job)
    m.renderer.async_render.assert_not_awaited()  # Persisted ready file after restart.


async def test_missing_footage_falls_back_instead_of_shifting_or_dropping_notification(hass):
    m = await manager(hass)
    await m.async_enqueue(call(detail_cameras=["left", "right"]))
    job = m.data["jobs"][0]
    m._request = AsyncMock(side_effect=[[], {"sequences": []}])
    m.renderer.async_cleanup = AsyncMock()
    assert await m._process(job) is False
    assert job["collage_fallback"] and job["phase"] == "waiting" and not job["local_video"]
    async def telegram(service): return {"chats": [{"message_id": 1}]}
    hass.services.async_register("telegram_bot", "send_video", telegram, supports_response=SupportsResponse.OPTIONAL)
    video = exported(job)
    m._request = AsyncMock(side_effect=[{"success": True, "export_id": "comederos_test"}, video, video, {"success": True}])
    assert await m._process(job)


async def test_capture_windows_start_immediately_once_and_expire_without_ha(hass):
    m = await manager(hass)
    m._request = AsyncMock(side_effect=[{"success": True, "event_id": "capture-left"},
                                        {"success": True, "event_id": "capture-right"}])
    moment = (dt_util.utcnow() - timedelta(seconds=20)).isoformat()
    await m.async_enqueue(call(detail_cameras=["left", "right"], record_detail_cameras=True, occurred_at=moment))
    job = m.data["jobs"][0]
    assert job["capture_events"] == {"left": "capture-left", "right": "capture-right"}
    assert m._request.await_count == 2
    for args in m._request.await_args_list:
        assert args.args[2]["include_recording"] and 35 <= args.args[2]["pre_capture"] <= 36
        assert 249 <= args.args[2]["duration"] <= 251
    await m._capture_details(job)
    assert m._request.await_count == 2
    job["capture_attempted"] = ["left"]
    m._request = AsyncMock(return_value={"success": True, "event_id": "capture-right"})
    await m._capture_details(job)
    assert m._request.await_count == 1 and "/right/" in m._request.await_args.args[1]


@pytest.mark.parametrize("responses", [
    [HomeAssistantError("uncertain"), {"success": False}],
    [{"success": True}, {"success": False}],
])
async def test_unknown_capture_requests_are_not_blindly_repeated(hass, responses):
    m = await manager(hass); m._request = AsyncMock(side_effect=responses)
    await m.async_enqueue(call(detail_cameras=["left", "right"], record_detail_cameras=True,
                              occurred_at=dt_util.utcnow().isoformat()))
    await m._capture_details(m.data["jobs"][0])
    assert m._request.await_count == 2 and len(m.data["jobs"]) == 1


async def test_capture_prebuffer_expiry_never_creates_a_fake_past_window(hass):
    m = await manager(hass); m._request = AsyncMock()
    await m.async_enqueue(call(detail_cameras=["left", "right"], record_detail_cameras=True,
                              occurred_at=(dt_util.utcnow()-timedelta(seconds=70)).isoformat()))
    m._request.assert_not_awaited()


async def test_pruning_failure_does_not_disable_feeder_controls_or_saved_jobs(hass):
    m = FeedingVideoNotifications(hass)
    m.store.async_load = AsyncMock(return_value=None)
    m.renderer.async_prune = AsyncMock(side_effect=OSError())
    m._start_worker = Mock()
    await m.async_setup()
    assert hass.services.has_service("pet_feeder_local", SERVICE)


def exported(job, **changes):
    return {
        "id": "comederos_test",
        "camera": "comederos",
        "name": job["name"],
        "video_path": "/media/frigate/exports/comederos_test.mp4",
        "in_progress": False,
        **changes,
    }


async def test_simultaneous_feeders_merge_but_other_meals_remain_separate(hass):
    m = await manager(hass)
    a = call()
    first = await m.async_enqueue(a)
    await m.async_enqueue(call("event-2", "Feeder 3", occurred_at=a.data["occurred_at"]))
    assert len(m.data["jobs"]) == 1 and m.data["jobs"][0]["feeders"] == ["Feeder 1", "Feeder 3"]
    assert (await m.async_enqueue(a))["duplicate"]
    await m.async_enqueue(call("event-3", camera="other_camera"))
    assert len(m.data["jobs"]) == 2 and first["queued"]
    assert m.store.async_save.await_count == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"frigate_url": "http://user:password@frigate.local"},
        {"frigate_url": "file:///tmp"},
        {"camera": "../other"},
        {"event_id": "bad\nvalue"},
        {"occurred_at": "bad"},
        {"occurred_at": "2026-01-01T08:00:00"},
        {"occurred_at": "2020-01-01T08:00:00+00:00"},
    ],
)
async def test_invalid_requests_are_rejected_before_network_or_queueing(hass, changes):
    m = await manager(hass)
    with pytest.raises(ServiceValidationError):
        await m.async_enqueue(call(**changes))
    assert not m.data["jobs"]


async def test_queue_bound_is_explicit(hass):
    m = await manager(hass)
    m.data["jobs"] = [{}] * 16
    with pytest.raises(HomeAssistantError):
        await m.async_enqueue(call())


async def test_real_workflow_contract_and_exact_id_cleanup(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    video = exported(job)
    sent = []

    async def telegram(service):
        sent.append(service.data)
        assert job["phase"] == "sending"  # Durable before transmission.
        return {"chats": [{"message_id": 123, "chat_id": 1}]}

    hass.services.async_register("telegram_bot", "send_video", telegram, supports_response=SupportsResponse.OPTIONAL)
    m._request = AsyncMock(
        side_effect=[{"success": True, "export_id": "comederos_test"}, video, video, {"success": True}]
    )
    assert await m._process(job)
    assert len(sent) == 1 and sent[0]["url"].endswith("/exports/comederos_test.mp4")
    assert sent[0]["parse_mode"] == "plain_text"
    create = m._request.await_args_list[0]
    assert create.args[1].startswith("export/custom/comederos/")
    assert create.args[2]["ffmpeg_input_args"] == "-an"
    assert "setpts=0.04*PTS" in create.args[2]["ffmpeg_output_args"]
    assert "-maxrate 3500k" in create.args[2]["ffmpeg_output_args"]
    assert m._request.await_args_list[-1].args[2] == {"ids": ["comederos_test"]}


async def test_send_failure_is_not_retried_and_cleanup_still_runs(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    video = exported(job)
    sends = AsyncMock(side_effect=HomeAssistantError("Telegram unavailable"))
    hass.services.async_register("telegram_bot", "send_video", sends, supports_response=SupportsResponse.OPTIONAL)
    m._request = AsyncMock(
        side_effect=[{"success": True, "export_id": "comederos_test"}, video, video, {"success": True}]
    )
    with patch("custom_components.pet_feeder_local.feeding_video.asyncio.sleep", new=AsyncMock()):
        await m._run()
    assert sends.await_count == 1 and not m.data["jobs"]


async def test_restart_during_send_only_cleans_up(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    job["phase"], job["export_id"] = "sending", "comederos_test"
    m._request = AsyncMock(side_effect=[exported(job), {"success": True}])
    assert await m._process(job)
    assert all(not x.args[1].startswith("export/custom/") for x in m._request.await_args_list)


async def test_cleanup_never_deletes_unrelated_export_and_retries_in_progress(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    job["export_id"] = "comederos_test"
    m._request = AsyncMock(return_value=exported(job, name="User archive"))
    with pytest.raises(HomeAssistantError):
        await m._cleanup(job)
    assert m._request.await_count == 1
    m._request = AsyncMock(return_value=exported(job, in_progress=True))
    assert await m._cleanup(job) is False
    m._request = AsyncMock(return_value=None)
    assert await m._cleanup(job) is True


async def test_unknown_create_is_reconciled_without_duplicate_post(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    job["phase"] = "creating"
    m._request = AsyncMock(return_value=[])
    assert await m._process(job) is False
    assert [c.args[1] for c in m._request.await_args_list] == ["exports", "jobs/export"]
    job["end"] -= 700
    assert await m._process(job) is True
    job["phase"] = "cleanup"
    assert await m._cleanup(job) is True


async def test_stopped_worker_is_cancelled_without_discarding_job(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    m.worker = asyncio.create_task(asyncio.sleep(100))
    await m.async_stop(None)
    assert m.worker.cancelled() and m.data["jobs"]


async def test_create_network_failure_preserves_owned_cleanup_job(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    m._request = AsyncMock(side_effect=ClientConnectionError())
    with pytest.raises(ClientConnectionError):
        await m._process(job)
    assert job["phase"] == "creating" and job["export_id"] is None


async def test_unsupported_or_empty_telegram_response_does_not_count_as_sent(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    video = exported(job)

    async def telegram(service):
        return {"chats": []}

    hass.services.async_register("telegram_bot", "send_video", telegram, supports_response=SupportsResponse.OPTIONAL)
    m._request = AsyncMock(side_effect=[{"success": True, "export_id": "comederos_test"}, video])
    with pytest.raises(HomeAssistantError):
        await m._process(job)
    assert job["phase"] == "sending"


async def test_http_status_redirect_boundary_and_read_cache_busting(hass):
    from .test_api import Response, Session

    m = await manager(hass)
    job = {"base": "http://frigate.local:5000"}
    m.session = Session(Response(data={"ok": True}))
    assert await m._request(job, "exports") == {"ok": True}
    args, kwargs = m.session.calls[0]
    assert "notification_read=" in args[1] and kwargs["allow_redirects"] is False
    await m._request(job, "left/recordings?after=1000&before=1240")
    assert "after=1000&before=1240&notification_read=" in m.session.calls[1][0][1]
    m.session = Session(Response(status=404))
    assert await m._request(job, "exports/missing", missing_ok=True) is None
    for status in (302, 500):
        m.session = Session(Response(status=status))
        with pytest.raises(HomeAssistantError):
            await m._request(job, "exports")


async def test_worker_start_and_saved_queue_recovery(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    m._run = AsyncMock()
    FeedingVideoNotifications._start_worker(m)
    await m.worker
    m._run.assert_awaited_once()
    m.worker = None
    m.data["jobs"] = []


async def test_cleanup_recovers_export_id_and_refusal_is_retained(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    video = exported(job)
    m._request = AsyncMock(side_effect=[[video], video, {"success": False}])
    with pytest.raises(HomeAssistantError):
        await m._cleanup(job)
    assert job["export_id"] == video["id"]
    job["export_id"] = None
    m._request = AsyncMock(return_value=[video, video])
    with pytest.raises(HomeAssistantError):
        await m._find_export(job)


async def test_create_recovery_pending_export_and_capture_wait(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    video = exported(job)

    async def telegram(service):
        return {"chats": [{"message_id": 1}]}

    hass.services.async_register("telegram_bot", "send_video", telegram, supports_response=SupportsResponse.OPTIONAL)
    fixed = dt_util.utcnow()
    clock = {"now": fixed}

    async def advance(seconds):
        clock["now"] += timedelta(seconds=seconds)

    job["end"] = fixed.timestamp() + 5
    m._request = AsyncMock(
        side_effect=[{"success": True, "export_id": "comederos_test"}, None, {}, video, video, {"success": True}]
    )
    with (
        patch("custom_components.pet_feeder_local.feeding_video.dt_util.utcnow", side_effect=lambda: clock["now"]),
        patch("custom_components.pet_feeder_local.feeding_video.asyncio.sleep", side_effect=advance),
    ):
        assert await m._process(job)
    job["phase"], job["export_id"] = "creating", None
    m._request = AsyncMock(side_effect=[[video], video, video, {"success": True}])
    assert await m._process(job)


@pytest.mark.parametrize("response", [{"success": False}, {"success": True, "export_id": "../../bad"}])
async def test_rejected_export_creation_cannot_send_video(hass, response):
    m = await manager(hass)
    await m.async_enqueue(call())
    m._request = AsyncMock(return_value=response)
    with pytest.raises(HomeAssistantError):
        await m._process(m.data["jobs"][0])


async def test_failed_export_and_unowned_path_cannot_send_video(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    job["phase"], job["export_id"] = "exporting", "comederos_test"
    m._request = AsyncMock(side_effect=[None, {"status": "failed"}])
    with pytest.raises(HomeAssistantError):
        await m._process(job)
    m._request = AsyncMock(return_value=exported(job, video_path="/tmp/not-an-export.mp4"))
    with pytest.raises(HomeAssistantError):
        await m._process(job)


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_catalog_404_does_not_abandon_an_export_that_can_finish_later(hass, status):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    job["export_id"] = "comederos_test"
    m._request = AsyncMock(side_effect=[None, {"status": status}])
    assert await m._cleanup(job) is False
    assert job in m.data["jobs"] and job["export_id"] == "comederos_test"
    # The same retained ID is deleted after the worker eventually finishes.
    m._request = AsyncMock(side_effect=[exported(job), {"success": True}])
    assert await m._cleanup(job) is True
    assert m._request.await_args.args[2] == {"ids": ["comederos_test"]}


async def test_lost_create_response_recovers_the_owned_active_job_before_a_file_exists(hass):
    m = await manager(hass)
    await m.async_enqueue(call())
    job = m.data["jobs"][0]
    active = {"id": "comederos_test", "camera": job["camera"], "name": job["name"], "status": "queued"}
    m._request = AsyncMock(side_effect=[[], [active], None, active])
    assert await m._cleanup(job) is False
    assert job["export_id"] == "comederos_test"
