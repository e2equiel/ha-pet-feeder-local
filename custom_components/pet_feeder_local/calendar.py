"""Display weekly MCU meals. Editing uses the bounded schedule editor card."""
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FeederConfigEntry
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([MealCalendar(entry.runtime_data)])


class MealCalendar(FeederEntity, CalendarEntity):

    def __init__(self, coordinator: FeederCoordinator) -> None:
        super().__init__(coordinator, "calendar")

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        day = dt_util.as_local(start).date()
        last = dt_util.as_local(end).date()
        # Keep unexpectedly broad calendar queries bounded.
        if (last - day).days > 366:
            raise ValueError("Request no more than one year at a time")
        while day <= last:
            weekday = (day.weekday() + 1) % 7
            for index, meal in enumerate(self.coordinator.schedule.meals):
                if not meal.enabled or not meal.weekdays & (1 << weekday):
                    continue
                when = datetime(day.year, day.month, day.day, meal.hour, meal.minute,
                                tzinfo=dt_util.DEFAULT_TIME_ZONE)
                if when < end and when + timedelta(minutes=1) > start:
                    events.append(CalendarEvent(
                        start=when, end=when + timedelta(minutes=1),
                        summary=f"{meal.portions} portion{'s' if meal.portions != 1 else ''}",
                        description="Executed by the feeder MCU, including when HA is offline.",
                        uid=f"meal-{index}-{day.isoformat()}",
                    ))
            day += timedelta(days=1)
        return sorted(events, key=lambda event: str(event.start))

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        events = self._events(now, now + timedelta(days=8))
        return events[0] if events else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return self._events(start_date, end_date)
