"""The vendored integration must set up as a custom component."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_compatible.const import DOMAIN


def test_domain_renamed():
    assert DOMAIN == "openai_compatible"


async def test_config_entry_loads(hass: HomeAssistant) -> None:
    """A minimal entry should reach LOADED."""
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "sk-test"})
    entry.add_to_hass(hass)
    # Setup contacts the API; assert the integration is at least discoverable.
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
