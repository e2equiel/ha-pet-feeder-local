"""Client for the feeder's authenticated local API.

Feeding is deliberately a single request. A network timeout is an unknown
outcome, not permission to dispense a second time.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4


class FeederError(Exception):
    """Base local feeder error."""


class InvalidAuth(FeederError):
    """The device rejected the API token."""


class RequestRejected(FeederError):
    """The API rejected a request before accepting an operation."""


class ScheduleConflict(FeederError):
    """The MCU schedule changed since it was read."""


class ScheduleVerificationError(FeederError):
    """The MCU readback does not match the requested schedule."""


class FeedOutcomeUnknown(FeederError):
    """A feeding request may have reached the device; do not retry it."""


@dataclass(frozen=True)
class Meal:
    """One MCU meal; weekdays use Sunday bit 0 through Saturday bit 6."""

    weekdays: int
    hour: int
    minute: int
    portions: int
    enabled: bool

    def __post_init__(self) -> None:
        for field, minimum, maximum in (
            (self.weekdays, 0, 127), (self.hour, 0, 23),
            (self.minute, 0, 59), (self.portions, 1, 10),
        ):
            if type(field) is not int or not minimum <= field <= maximum:
                raise ValueError("Meal field outside the supported MCU range")
        if type(self.enabled) is not bool:
            raise ValueError("Meal enabled must be a boolean")

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Meal:
        return cls(**{key: data[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Schedule:
    """Fresh MCU schedule plus its concurrency revision."""

    revision: str
    meals: tuple[Meal, ...]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Schedule:
        meals = tuple(Meal.from_json(item) for item in data["meals"])
        if len(meals) > 8 or not isinstance(data.get("revision"), str):
            raise ValueError("Invalid MCU schedule response")
        return cls(data["revision"], meals)


class FeederClient:
    """An API client using a Home Assistant-managed aiohttp session."""

    def __init__(self, session: Any, base_url: str, token: str) -> None:
        url = urlsplit(base_url)
        if (
            url.scheme not in ("http", "https") or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError("Enter the feeder's local HTTP address")
        if not token or "\r" in token or "\n" in token:
            raise ValueError("Invalid API token")
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def _request(
        self, method: str, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with asyncio.timeout(5):
            async with self._session.request(
                method, self._base_url + "/api/v1/" + path,
                headers={"Authorization": "Bearer " + self._token},
                json=data, allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("The feeder rejected the API token")
                if response.status == 409:
                    raise ScheduleConflict("The MCU schedule changed; reload it")
                if 400 <= response.status < 500:
                    raise RequestRejected(f"Feeder rejected the request: HTTP {response.status}")
                if response.status >= 300:
                    raise FeederError(f"Feeder returned HTTP {response.status}")
                result = await response.json()
                if not isinstance(result, dict):
                    raise FeederError("Invalid feeder response")
                return result

    async def async_get_info(self) -> dict[str, Any]:
        return await self._request("GET", "info")

    async def async_get_status(self) -> dict[str, Any]:
        return await self._request("GET", "status")

    async def async_get_schedule(self) -> Schedule:
        return Schedule.from_json(await self._request("GET", "schedules"))

    async def async_feed(self, portions: int, operation_id: str | None = None) -> str:
        if type(portions) is not int or not 1 <= portions <= 10:
            raise ValueError("Portions must be an integer between 1 and 10")
        operation_id = operation_id or str(uuid4())
        if not 1 <= len(operation_id) <= 64 or not all(
            character.isascii() and (character.isalnum() or character in "-_")
            for character in operation_id
        ):
            raise ValueError("Invalid operation ID")
        try:
            result = await self._request(
                "POST", "feed", {"portions": portions, "operation_id": operation_id}
            )
        except (InvalidAuth, RequestRejected, ScheduleConflict):
            raise
        except Exception as err:
            raise FeedOutcomeUnknown(
                "The feeding outcome is unknown; check the feeder before serving again"
            ) from err
        if result.get("operation_id") != operation_id or result.get("accepted") is not True:
            raise FeedOutcomeUnknown("The feeder did not confirm this operation ID")
        return operation_id

    async def async_set_schedule(
        self, meals: tuple[Meal, ...], expected_revision: str
    ) -> Schedule:
        if len(meals) > 8 or not all(isinstance(meal, Meal) for meal in meals):
            raise ValueError("A maximum of eight MCU meals is supported")
        if not expected_revision:
            raise ValueError("A fresh MCU revision is required")
        result = await self._request(
            "PUT", "schedules",
            {"expected_revision": expected_revision,
             "meals": [asdict(meal) for meal in meals]},
        )
        verified = Schedule.from_json(result)
        if result.get("verified") is not True or verified.meals != meals:
            raise ScheduleVerificationError("The MCU schedule readback did not match")
        return verified
