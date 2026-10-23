import types
from typing import get_args, get_origin

from pydantic import BaseModel

import homeaudio.audio.admin_ui as admin_ui_module
from homeaudio.audio.admin_ui import AdminRoutes
from homeaudio.audio.settings import AppSettings, AvailableGoogleCalendars, CalendarSetting, GoogleCalendar, GoogleCalendarSettings, SnapcastSettings, SnapclientConfig


def _unwrap_optional(annotation):
    origin = get_origin(annotation)
    if origin in (types.UnionType,):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _all_field_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    """All dotted paths reachable on `model`, matching the attr_configs key format
    (e.g. "some_settings.items.[]" for a list field, "[]." recursing into item fields)."""
    paths = set()
    for name, field_info in model.model_fields.items():
        path = f"{prefix}{name}"
        paths.add(path)

        annotation = _unwrap_optional(field_info.annotation)
        if get_origin(annotation) is list:
            item_type = _unwrap_optional(get_args(annotation)[0])
            list_path = f"{path}.[]"
            paths.add(list_path)
            if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                paths |= _all_field_paths(item_type, f"{list_path}.")
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            paths |= _all_field_paths(annotation, f"{path}.")

    return paths


def test_attr_configs_keys_exist_on_app_settings():
    """attr_configs is keyed by dotted paths into AppSettings, matched against the
    generated form schema at runtime. If a field is renamed/moved without updating
    attr_configs to match, the config for it silently stops being applied instead of
    raising an error - so assert every key still resolves to a real AppSettings field."""
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    admin_routes.calendar_select_props = {"options": []}
    admin_routes.available_calendar_select_props = {"options": []}
    admin_routes.player_select_props = {"options": []}
    attr_configs = admin_routes.attr_configs(None)

    valid_paths = _all_field_paths(AppSettings)

    unknown_keys = sorted(set(attr_configs) - valid_paths)

    assert not unknown_keys, (
        f"attr_configs references paths that don't exist on AppSettings: {unknown_keys}"
    )


def _fake_app_settings_class(previous, validated):
    """A stand-in for AppSettings supporting both AppSettings() (-> previous) and
    AppSettings.model_validate(data) (-> validated), without touching real config files."""

    class _FakeAppSettings:
        def __new__(cls):
            return previous

        @classmethod
        def model_validate(cls, data):
            return validated

    return _FakeAppSettings


def _fake_settings():
    settings = types.SimpleNamespace()
    settings.saved = False
    settings.save = lambda: setattr(settings, "saved", True)
    return settings


def test_save_settings_validates_and_saves(monkeypatch):
    previous = _fake_settings()
    validated = _fake_settings()
    monkeypatch.setattr(admin_ui_module, "AppSettings", _fake_app_settings_class(previous, validated))

    admin_routes = AdminRoutes.__new__(AdminRoutes)

    result = admin_routes._save_settings({})

    assert result is validated
    assert validated.saved is True


def test_calendar_options_uses_the_available_calendar_name_as_the_label():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[GoogleCalendar(id="family-id", name="Family")])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[CalendarSetting(id="family-id", name="Our family")])

    options = admin_routes._calendar_options(available_calendars, google_calendar_settings)

    assert options == [{"value": "family-id", "label": "Family"}]


def test_calendar_options_falls_back_to_the_configured_calendar_name_when_not_available():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[CalendarSetting(id="old-id", name="Old")])

    options = admin_routes._calendar_options(available_calendars, google_calendar_settings)

    assert options == [{"value": "old-id", "label": "Old"}]


def test_calendar_options_puts_calendars_with_matching_id_and_name_first_then_sorts_by_name():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[GoogleCalendar(id="family-id", name="Family")])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[
        CalendarSetting(id="weather-id", name="Weather"),
        CalendarSetting(id="zed@example.com", name="zed@example.com"),
        CalendarSetting(id="family-id", name="Our family"),
        CalendarSetting(id="amy@example.com", name="amy@example.com"),
    ])

    options = admin_routes._calendar_options(available_calendars, google_calendar_settings)

    assert [option["value"] for option in options] == ["amy@example.com", "zed@example.com", "family-id", "weather-id"]


def test_available_calendar_options_lists_the_available_google_calendars():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[GoogleCalendar(id="family-id", name="Family"), GoogleCalendar(id="weather-id", name="Weather")])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[CalendarSetting(id="family-id", name="Our family")])

    options = admin_routes._available_calendar_options(available_calendars, google_calendar_settings)

    assert options == [{"value": "family-id", "label": "Family"}, {"value": "weather-id", "label": "Weather"}]


def test_available_calendar_options_includes_configured_calendars_that_are_no_longer_available():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[GoogleCalendar(id="family-id", name="Family")])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[CalendarSetting(id="old-id", name="Old")])

    options = admin_routes._available_calendar_options(available_calendars, google_calendar_settings)

    assert options == [{"value": "family-id", "label": "Family"}, {"value": "old-id", "label": "Old"}]


def test_available_calendar_options_puts_calendars_with_matching_id_and_name_first_then_sorts_by_name():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    available_calendars = AvailableGoogleCalendars.model_construct(calendars=[
        GoogleCalendar(id="weather-id", name="Weather"),
        GoogleCalendar(id="zed@example.com", name="zed@example.com"),
        GoogleCalendar(id="family-id", name="Family"),
        GoogleCalendar(id="amy@example.com", name="amy@example.com"),
    ])
    google_calendar_settings = GoogleCalendarSettings.model_construct(calendars=[])

    options = admin_routes._available_calendar_options(available_calendars, google_calendar_settings)

    assert [option["value"] for option in options] == ["amy@example.com", "zed@example.com", "family-id", "weather-id"]


def test_player_options_lists_all_snapclients_including_disabled_ones():
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    snapcast_settings = SnapcastSettings.model_construct(snapclients=[
        SnapclientConfig(name="kaypi", display_name="Kay's room"),
        SnapclientConfig(name="officepi", display_name="Office", enabled=False),
    ])

    options = admin_routes._player_options(snapcast_settings)

    assert options == [{"value": "kaypi", "label": "Kay's room"}, {"value": "officepi", "label": "Office"}]
