"""Tests for automatic Lovelace resource registration."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _module(name: str) -> ModuleType:
    module = ModuleType(name)
    sys.modules[name] = module
    return module


homeassistant = _module("homeassistant")
homeassistant.__path__ = []
components = _module("homeassistant.components")
components.__path__ = []
http = _module("homeassistant.components.http")
lovelace = _module("homeassistant.components.lovelace")
lovelace.__path__ = []
lovelace_const = _module("homeassistant.components.lovelace.const")
config_entries = _module("homeassistant.config_entries")
ha_const = _module("homeassistant.const")
core = _module("homeassistant.core")
helpers = _module("homeassistant.helpers")
helpers.__path__ = []
config_validation = _module("homeassistant.helpers.config_validation")
loader = _module("homeassistant.loader")


class StaticPathConfig:
    """Minimal StaticPathConfig replacement for importing the integration."""


class ConfigEntry:
    """Minimal ConfigEntry replacement for importing the integration."""


class HomeAssistant:
    """Minimal HomeAssistant replacement for importing the integration."""


http.StaticPathConfig = StaticPathConfig
lovelace_const.CONF_RESOURCE_TYPE_WS = "res_type"
lovelace_const.LOVELACE_DATA = "lovelace"
lovelace_const.MODE_STORAGE = "storage"
config_entries.ConfigEntry = ConfigEntry
ha_const.CONF_ID = "id"
ha_const.CONF_TYPE = "type"
ha_const.CONF_URL = "url"
ha_const.Platform = SimpleNamespace(SENSOR="sensor")
core.HomeAssistant = HomeAssistant
config_validation.config_entry_only_config_schema = lambda _domain: {}


async def _unused_async_get_integration(_hass, _domain):
    raise AssertionError("The test must replace async_get_integration")


loader.async_get_integration = _unused_async_get_integration

coordinator = _module("custom_components.my_station.coordinator")
coordinator.MyStationDataUpdateCoordinator = object

integration_module = importlib.import_module("custom_components.my_station")


class FakeResources:
    """Writable Lovelace resource collection with load-order assertions."""

    def __init__(self, items=None):
        self.items = list(items or [])
        self.loaded = False
        self.created = []
        self.updated = []

    async def async_get_info(self):
        self.loaded = True
        return {"resources": len(self.items)}

    def async_items(self):
        if not self.loaded:
            raise AssertionError("Resources must be loaded before inspection")
        return list(self.items)

    async def async_create_item(self, data):
        if not self.loaded:
            raise AssertionError("Resources must be loaded before creation")
        self.created.append(data)
        item = {
            "id": "created-resource",
            "type": data["res_type"],
            "url": data["url"],
        }
        self.items.append(item)
        return item

    async def async_update_item(self, item_id, updates):
        self.updated.append((item_id, updates))


class FakeHass:
    """Home Assistant data container used by registration tests."""

    def __init__(self, lovelace_data):
        self.data = {"lovelace": lovelace_data}


class ResourceRegistrationTests(unittest.IsolatedAsyncioTestCase):
    """Verify resource creation, adoption, and YAML-mode handling."""

    async def asyncSetUp(self):
        async def fake_async_get_integration(_hass, domain):
            self.assertEqual(domain, "my_station")
            return SimpleNamespace(version="9.8.7")

        integration_module.async_get_integration = fake_async_get_integration

    async def test_creates_missing_storage_resource_after_loading(self):
        resources = FakeResources()
        hass = FakeHass(
            SimpleNamespace(resource_mode="storage", resources=resources)
        )

        await integration_module._async_register_card_resource(hass)

        self.assertTrue(resources.loaded)
        self.assertEqual(
            resources.created,
            [
                {
                    "res_type": "module",
                    "url": "/my_station/my-station-card.js?v=9.8.7",
                }
            ],
        )

    async def test_adopts_existing_manual_resource(self):
        resources = FakeResources(
            [
                {
                    "id": "manual-resource",
                    "type": "js",
                    "url": "/my_station/my-station-card.js",
                }
            ]
        )
        hass = FakeHass({"mode": "storage", "resources": resources})

        await integration_module._async_register_card_resource(hass)

        self.assertEqual(resources.created, [])
        self.assertEqual(
            resources.updated,
            [
                (
                    "manual-resource",
                    {
                        "res_type": "module",
                        "url": "/my_station/my-station-card.js?v=9.8.7",
                    },
                )
            ],
        )

    async def test_does_not_modify_yaml_resources(self):
        resources = FakeResources()
        hass = FakeHass(SimpleNamespace(resource_mode="yaml", resources=resources))

        await integration_module._async_register_card_resource(hass)

        self.assertFalse(resources.loaded)
        self.assertEqual(resources.created, [])
        self.assertEqual(resources.updated, [])


if __name__ == "__main__":
    unittest.main()
