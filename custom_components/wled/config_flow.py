"""Config flow to configure the WLED integration."""
from typing import Any, Dict, Optional

import voluptuous as vol
from wled import WLED, WLEDConnectionError

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_ZEROCONF,
    ConfigFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN  # pylint: disable=unused-import


class WLEDFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WLED config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="cannot_connect")

        # Hostname is format: wled-livingroom.local.
        host = user_input["hostname"].rstrip(".")
        name, _ = host.rsplit(".")

        self.context.update(
            {
                CONF_HOST: user_input["host"],
                CONF_NAME: name,
                CONF_MAC: user_input["properties"].get(CONF_MAC),
                "title_placeholders": {"name": name},
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow(user_input, True)

    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None, prepare: bool = False
    ) -> Dict[str, Any]:
        """Config flow handler for WLED."""
        source = self.context.get("source")

        # Request user input, unless we are preparing discovery flow
        if user_input is None and not prepare:
            if source == SOURCE_ZEROCONF:
                return self._show_confirm_dialog()
            return self._show_setup_form()

        if source == SOURCE_ZEROCONF:
            user_input[CONF_HOST] = self.context.get(CONF_HOST)
            user_input[CONF_MAC] = self.context.get(CONF_MAC)

        if user_input.get(CONF_MAC) is None or not prepare:
            session = async_get_clientsession(self.hass)
            wled = WLED(user_input[CONF_HOST], session=session)
            try:
                device = await wled.update()
            except WLEDConnectionError:
                if source == SOURCE_ZEROCONF:
                    return self.async_abort(reason="cannot_connect")
                return self._show_setup_form({"base": "cannot_connect"})
            user_input[CONF_MAC] = device.info.mac_address

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_MAC])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        title = user_input[CONF_HOST]
        if source == SOURCE_ZEROCONF:
            title = self.context.get(CONF_NAME)

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=title,
            data={CONF_HOST: user_input[CONF_HOST], CONF_MAC: user_input[CONF_MAC]},
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    def _show_confirm_dialog(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the confirm dialog to the user."""
        name = self.context.get(CONF_NAME)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": name},
            errors=errors or {},
        )
