import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vcal.announcements.morning_announcements import TextBuilder
from vcal.cal.google_calendar import Event, WeatherForecast

select_option_call_count = 0

def fake_select_option(opts):
    global select_option_call_count
    select_option_call_count += 1
    if select_option_call_count == 1:
        return Mock(text="Prelude text.")
    return Mock(text="Selected fact")

def test_get_morning_announcements_text_includes_weather_and_facts(monkeypatch):
    # Create three events: two normal and one weather forecast
    e1 = Event(owner="cal", summary="Meeting", description="")
    e2 = Event(owner="cal", summary="Appointment", description="")
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="")

    events = [weather, e1, e2]

    monkeypatch.setattr(
        "vcal.announcements.morning_announcements.select_option",
        fake_select_option,
    )

    # Provide a minimal settings object with needed attributes
    settings = Mock()
    settings.enabled_prelude_options = []
    settings.prelude_probability = 1.0
    settings.unused_facts = ["fact1"]
    settings.save = Mock()

    tb = TextBuilder(events, settings)

    text = tb.get_morning_announcements_text()

    expected = [ "Good morning!",
        "Prelude text.",
        "The weather forecast for today is: Min 10 Max 20.",
        "Todays events are:",
        "Meeting.",
        "Appointment.",
        "Your fun fact for today is:",
        "Selected fact",
        "Have a lovely day.",
    ]

    assert text == expected
