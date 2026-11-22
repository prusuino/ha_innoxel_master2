"""Base entity of the Innoxel Master 2 integration."""
from __future__ import annotations

from collections.abc import Callable, Iterator

from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import KEY_IMPULSE, Address, Master2Error, parse_address


def _links_by_device_id() -> bool:
    """Current Home Assistant names the parent of a device by its registry id
    (`via_device_id`); older versions only know its identifier (`via_device`),
    which newer ones report as deprecated (removed in 2027.8)."""
    return "via_device_id" in DeviceInfo.__optional_keys__ | DeviceInfo.__required_keys__
from .const import DOMAIN
from .coordinator import Master2ConfigEntry, Master2Coordinator


def subentries_of_type(
    entry: Master2ConfigEntry, subentry_type: str
) -> Iterator[ConfigSubentry]:
    """Yield the channels of one type the user added to this master."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == subentry_type:
            yield subentry


def optional_address(subentry: ConfigSubentry, key: str, kind: str) -> Address | None:
    """Return a parsed optional address of a subentry."""
    text = subentry.data.get(key)
    return parse_address(text, kind) if text else None


class Master2ChannelEntity(CoordinatorEntity[Master2Coordinator]):
    """Entity for one channel (subentry) of the master.

    Home Assistant ties a device to one subentry, so every channel is its own
    device below the master and the entity takes the name of that device.
    """

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{subentry.subentry_id}"
        info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=subentry.title,
            manufacturer="Innoxel",
        )
        if _links_by_device_id() and coordinator.master_device_id:
            info["via_device_id"] = coordinator.master_device_id
        else:
            info["via_device"] = (DOMAIN, entry_id)
        self._attr_device_info = info

    async def _send_key(
        self,
        address: Address,
        action: int = KEY_IMPULSE,
        done: Callable[[], bool] | None = None,
    ) -> None:
        try:
            await self.coordinator.async_send_key(address, action, done)
        except Master2Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
