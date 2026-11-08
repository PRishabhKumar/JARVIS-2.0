from .config import PathScope
from .registry import ToolRegistry
from .agents import (
    system_agent,
    process_agent,
    filesystem_agent,
    network_agent,
    inventory_agent,
    archive_agent,
    app_agent,
    clipboard_agent,
    screen_agent,
    audio_control_agent,
    power_agent,
    display_agent,
    wireless_agent,
)


def build_registry(settings):
    scope = PathScope(settings.roots, [settings.state_dir])
    registry = ToolRegistry()
    for module in (
        system_agent,
        process_agent,
        filesystem_agent,
        network_agent,
        inventory_agent,
        archive_agent,
        app_agent,
        clipboard_agent,
        screen_agent,
        audio_control_agent,
        power_agent,
        display_agent,
        wireless_agent,
    ):
        module.register(registry, settings, scope)
    return registry
