"""Timeline integrity, resource boundaries and interrupted-file ownership."""
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.pet_feeder_local.video_collage import (
    CollageRenderer,
    RecordingSpan,
    collage_command,
    recording_intervals,
    timeline_offset,
)

KEY = "a" * 24
FULL_SPANS = [[RecordingSpan(1000, 1240, 0)] for _ in range(3)]


def test_public_media_mapping_never_becomes_the_video_cache(hass):
    public = hass.config.path("www", "images")
    for media in [{"images": public}, {"local": public}]:
        hass.config.media_dirs = media
        assert CollageRenderer(hass).directory == Path("/media/.pet_feeder_local_videos")


async def test_a_media_symlink_into_the_public_web_root_is_rejected(hass, tmp_path):
    public = tmp_path / "www"; public.mkdir()
    alias = tmp_path / "media"; alias.symlink_to(public, target_is_directory=True)
    renderer = CollageRenderer(hass); renderer.directory = alias / ".pet_feeder_local_videos"
    with patch.object(hass.config, "path", return_value=str(public)), \
         patch.object(hass.config, "is_allowed_path", return_value=True):
        with pytest.raises(HomeAssistantError):
            await renderer.async_render(KEY, "http://nvr", ["a", "b", "c"], FULL_SPANS, 1000, 1240)


def timeline(camera="overhead", start=1000, end=1240):
    stamp = datetime.fromtimestamp(start - 2, UTC)
    path = stamp.strftime("/media/frigate/recordings/%Y-%m-%d/%H/") + camera + stamp.strftime("/%M.%S.mp4")
    return ([{"start_time": start - 5, "end_time": start - 3},
             {"start_time": start - 2, "end_time": end}],
            {"sequences": [{"clips": [{"path": path}]}], "durations": [(end-start+2)*1000]})


def test_keyframe_preroll_is_trimmed_on_a_common_wall_clock():
    rows, vod = timeline()
    assert timeline_offset("overhead", rows, vod, 1000, 1240) == 2
    args = collage_command("ffmpeg", "http://nvr.local:5000", ["overhead", "left", "right"],
                           [[RecordingSpan(1000, 1240, offset)] for offset in [2, 1, 3]],
                           1000, 1240, Path("out.mp4"), Path("slate.png"))
    inputs = [args[i + 1] for i, arg in enumerate(args) if arg == "-i"]
    assert len(inputs) == 3 and all("/start/1000/end/1240/" in url for url in inputs)
    graph = args[args.index("-filter_complex") + 1]
    assert graph.count("setpts=0.04*(PTS-STARTPTS)") == 3
    assert "hstack=inputs=2" in graph and "vstack=inputs=2" in graph
    assert "1280:720" in graph and graph.count("640:360") >= 2
    assert "-an" in args and args[args.index("-t") + 1] == "9.600"
    assert args[args.index("-filter_complex_threads") + 1] == "1"


def test_gap_and_missing_camera_preserve_the_shared_timeline():
    start, end = 1000, 1240
    coverage = [{"start_time": 995, "end_time": 1009}, {"start_time": 1018, "end_time": 1127},
                {"start_time": 1128, "end_time": 1241}]
    intervals = recording_intervals(coverage, start, end)
    assert intervals == [(1000, 1009), (1018, 1127), (1128, 1240)]
    _, first_vod = timeline("left", 1000, 1009)
    assert timeline_offset("left", coverage, first_vod, 1000, 1009) == 2
    assert recording_intervals(coverage, 1009, 1018) == []
    plans = [[RecordingSpan(start, end, 0)], [RecordingSpan(a, b, 0) for a, b in intervals], []]
    args = collage_command("ffmpeg", "http://nvr", ["top", "left", "right"], plans,
                           start, end, Path("out.mp4"), Path("slate.png"))
    inputs = [args[i + 1] for i, arg in enumerate(args) if arg == "-i"]
    assert inputs.count("slate.png") == 3
    assert any("/left/start/1018/end/1127/" in url for url in inputs)
    assert not any("/right/" in url for url in inputs)
    graph = args[args.index("-filter_complex") + 1]
    assert "concat=n=5:v=1:a=0,settb=1/30,setpts=N[v1]" in graph
    assert "trim=end_frame=288" in graph


@pytest.mark.parametrize("problem", ["gap", "tail", "camera", "vod_short", "vod_late"])
def test_missing_recordings_never_silently_shift_a_pane(problem):
    rows, vod = timeline()
    if problem == "gap": rows[1]["start_time"] = 1002
    if problem == "tail": rows[1]["end_time"] = 1230
    if problem == "camera": vod["sequences"][0]["clips"][0]["path"] = vod["sequences"][0]["clips"][0]["path"].replace("overhead", "another")
    if problem == "vod_short": vod["durations"] = [10000]
    if problem == "vod_late": vod["sequences"][0]["clips"][0]["clipFrom"] = 4000
    with pytest.raises(ValueError): timeline_offset("overhead", rows, vod, 1000, 1240)


async def test_orphans_are_pruned_without_touching_active_or_unrelated_files(hass, tmp_path):
    renderer = CollageRenderer(hass); renderer.directory = tmp_path / "cache"
    await renderer.async_prune(set())
    renderer.directory.mkdir()
    renderer.path(KEY).write_bytes(b"old")
    renderer.path(KEY, partial=True).write_bytes(b"partial")
    renderer.path("b" * 24).write_bytes(b"active")
    (renderer.directory / "personal.mp4").write_bytes(b"keep")
    (renderer.directory / ("c" * 24 + ".mp4")).mkdir()
    await renderer.async_prune({"b" * 24})
    assert not renderer.path(KEY).exists() and renderer.path("b" * 24).read_bytes() == b"active"
    assert (renderer.directory / "personal.mp4").read_bytes() == b"keep"
    await renderer.async_cleanup("b" * 24)
    await renderer.async_cleanup("b" * 24)
    with pytest.raises(ValueError): renderer.path("../personal")


async def render(hass, tmp_path, *, size=1500, returncode=0, failure=None, allowed=True):
    renderer = CollageRenderer(hass); renderer.directory = tmp_path
    process = Mock(returncode=returncode, communicate=AsyncMock(side_effect=failure, return_value=(b"", b"")),
                   wait=AsyncMock())
    async def spawn(*args, **kwargs):
        def create():
            with renderer.path(KEY, partial=True).open("wb") as file: file.truncate(size)
        await hass.async_add_executor_job(create)
        return process
    with patch.object(hass.config, "is_allowed_path", return_value=allowed), \
         patch("custom_components.pet_feeder_local.video_collage.get_ffmpeg_manager", return_value=SimpleNamespace(binary="ffmpeg")), \
         patch("custom_components.pet_feeder_local.video_collage.asyncio.create_subprocess_exec", side_effect=spawn) as launch:
        result = await renderer.async_render(KEY, "http://nvr.local:5000", ["a", "b", "c"], FULL_SPANS, 1000, 1240)
    return renderer, process, result, launch


async def test_finished_video_is_atomically_renamed_and_cleaned(hass, tmp_path):
    renderer, process, result, launch = await render(hass, tmp_path)
    assert result.read_bytes() == bytes(1500)
    assert not renderer.path(KEY, partial=True).exists()
    assert launch.call_count == 1 and process.communicate.await_count == 1
    assert launch.call_args.kwargs["stderr"] == asyncio.subprocess.DEVNULL
    await renderer.async_cleanup(KEY)
    assert not result.exists()


@pytest.mark.parametrize("changes", [{"returncode": 1}, {"size": 2}, {"size": 48_000_000}, {"allowed": False}])
async def test_invalid_output_and_unapproved_file_path_are_not_sent(hass, tmp_path, changes):
    with pytest.raises(HomeAssistantError): await render(hass, tmp_path, **changes)


async def test_cancellation_kills_and_reaps_the_encoder(hass, tmp_path):
    process = Mock(returncode=None, communicate=AsyncMock(side_effect=asyncio.CancelledError), wait=AsyncMock())
    renderer = CollageRenderer(hass); renderer.directory = tmp_path
    with patch.object(hass.config, "is_allowed_path", return_value=True), \
         patch("custom_components.pet_feeder_local.video_collage.get_ffmpeg_manager", return_value=SimpleNamespace(binary="ffmpeg")), \
         patch("custom_components.pet_feeder_local.video_collage.asyncio.create_subprocess_exec", return_value=process):
        with pytest.raises(asyncio.CancelledError):
            await renderer.async_render(KEY, "http://nvr", ["a", "b", "c"], FULL_SPANS, 1000, 1240)
    process.kill.assert_called_once(); process.wait.assert_awaited_once()
