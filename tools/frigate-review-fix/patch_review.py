"""Publish manual-event review changes immediately in Frigate 0.18.3."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ORIGINAL_SHA256 = "4ef0a07ecd6af46ceb2ae91e33e06f91c178e6a0ddc463c4115fe2ee0c3be6a3"
PATCHED_SHA256 = "01c862e6297fd4e2e693f4d048d96696c79c4ac75f45c54b81cce0050c08cbf0"


def patched_source(source: str) -> str:
    before = '''                elif topic == DetectionTypeEnum.api or topic == DetectionTypeEnum.lpr:
                    if manual_info["state"] == ManualEventState.complete:'''
    after = '''                elif topic == DetectionTypeEnum.api or topic == DetectionTypeEnum.lpr:
                    previous_manual_data = current_segment.get_data(False)
                    if manual_info["state"] == ManualEventState.complete:'''
    if source.count(before) != 1:
        raise ValueError("Unexpected manual-event branch")
    source = source.replace(before, after)
    before = '''                            logger.error(
                                f"Event with ID {event_id} has a set duration and can not be ended manually."
                            )
            else:'''
    after = '''                            logger.error(
                                f"Event with ID {event_id} has a set duration and can not be ended manually."
                            )
                    # Recording retention reads the persisted review severity.
                    # Publish manual changes even when no tracked object changes.
                    self._publish_segment_update(
                        current_segment, self.config.cameras[camera], None, [],
                        previous_manual_data,
                    )
            else:'''
    if source.count(before) != 1:
        raise ValueError("Unexpected manual-event branch ending")
    result = source.replace(before, after)
    compile(result, "frigate-review-maintainer", "exec")
    return result


def apply(path: Path) -> bool:
    current = path.read_bytes()
    digest = hashlib.sha256(current).hexdigest()
    if digest == PATCHED_SHA256:
        return False
    if digest != ORIGINAL_SHA256:
        raise ValueError("Unsupported Frigate source: refusing to modify it")
    result = patched_source(current.decode()).encode()
    if hashlib.sha256(result).hexdigest() != PATCHED_SHA256:
        raise ValueError("Unexpected patch result: source was not modified")
    path.write_bytes(result)
    return True


if __name__ == "__main__":
    changed = apply(Path(sys.argv[1]))
    print("Frigate manual-review publication fix applied" if changed else "Fix already present")
