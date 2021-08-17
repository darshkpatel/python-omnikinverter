"""Asynchronous Python client for the Omnik Inverter."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import async_timeout
from aiohttp.client import ClientError, ClientResponseError, ClientSession
from yarl import URL

from .exceptions import OmnikInverterConnectionError, OmnikInverterError
from .models import Inverter


@dataclass
class OmnikInverter:
    """Main class for handling connections with the Omnik Inverter."""

    def __init__(
        self, host: str, request_timeout: int = 10, session: ClientSession | None = None
    ) -> None:
        """Initialize connection with the Omnik Inverter.

        Args:
            host: Hostname or IP address of the Omnik Inverter.
            request_timeout: An integer with the request timeout in seconds.
            session: Optional, shared, aiohttp client session.
        """
        self._session = session
        self._close_session = False

        self.host = host
        self.request_timeout = request_timeout

    async def request(
        self,
        uri: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a P1 Monitor device.

        Args:
            uri: Request URI, without '/', for example, 'status'
            params: Extra options to improve or limit the response.

        Returns:
            A Python dictionary (text) with the response from
            the Omnik Inverter.

        Raises:
            OmnikInverterConnectionError: An error occurred while communicating
                with the Omnik Inverter.
            OmnikInverterError: Received an unexpected response from the Omnik Inverter.
        """
        url = URL.build(scheme="http", host=self.host, path="/").join(URL(uri))

        headers = {
            "Accept": "text/html, application/xhtml+xml, application/xml",
        }

        if self._session is None:
            self._session = ClientSession()
            self._close_session = True

        try:
            with async_timeout.timeout(self.request_timeout):
                response = await self._session.request(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
        except asyncio.TimeoutError as exception:
            raise OmnikInverterConnectionError(
                "Timeout occurred while connecting to Omnik Inverter device"
            ) from exception
        except (ClientError, ClientResponseError) as exception:
            raise OmnikInverterConnectionError(
                "Error occurred while communicating with Omnik Inverter device"
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        if "application/x-javascript" not in content_type:
            text = await response.text()
            raise OmnikInverterError(
                "Unexpected response from the Omnik Inverter device",
                {"Content-Type": content_type, "response": text},
            )

        return await response.text()

    async def inverter(self) -> Inverter:
        """Get the latest values from you Omnik Inverter.

        Returns:
            A Inverter data object from the Omnik Inverter.
        """
        data = await self.request("js/status.js")
        return Inverter.from_js(data)

    async def close(self) -> None:
        """Close open client session."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> OmnikInverter:
        """Async enter.

        Returns:
            The P1 Monitor object.
        """
        return self

    async def __aexit__(self, *_exc_info) -> None:
        """Async exit.

        Args:
            _exc_info: Exec type.
        """
        await self.close()
