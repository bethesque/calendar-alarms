import types
from typing import get_args, get_origin

from pydantic import BaseModel

from homeaudio.audio.admin_ui import AdminRoutes
from homeaudio.audio.settings import AppSettings


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
    dummy_settings = types.SimpleNamespace(
        google_calendar_settings=types.SimpleNamespace(calendars=[])
    )
    admin_routes = AdminRoutes.__new__(AdminRoutes)
    attr_configs = admin_routes.attr_configs(dummy_settings)

    valid_paths = _all_field_paths(AppSettings)

    unknown_keys = sorted(set(attr_configs) - valid_paths)

    assert not unknown_keys, (
        f"attr_configs references paths that don't exist on AppSettings: {unknown_keys}"
    )
