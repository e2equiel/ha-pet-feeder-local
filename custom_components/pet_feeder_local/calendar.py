"""Display weekly MCU meals. Editing uses the bounded schedule editor card."""
from datetime import datetime, timedelta
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util
from .entity import FeederEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MealCalendar(entry.runtime_data)])


class MealCalendar(FeederEntity, CalendarEntity):
    _attr_name = "Feeding schedule"

    def __init__(self, coordinator):
        super().__init__(coordinator, "calendar")

    def _events(self, start, end):
        events = []
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
        return sorted(events, key=lambda event: event.start)

    @property
    def event(self):
        now = dt_util.now()
        events = self._events(now, now + timedelta(days=8))
        return events[0] if events else None

    async def async_get_events(self, hass, start_date, end_date):
        return self._events(start_date, end_date)
