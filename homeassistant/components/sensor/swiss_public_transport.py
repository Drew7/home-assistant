"""
Support for transport.opendata.ch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_public_transport/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['python_opendata_transport==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_DEPARTURE_TIME1 = 'next_departure'
ATTR_DEPARTURE_TIME2 = 'next_on_departure'
ATTR_DURATION = 'duration'
ATTR_PLATFORM = 'platform'
ATTR_REMAINING_TIME = 'remaining_time'
ATTR_START = 'start'
ATTR_TARGET = 'destination'
ATTR_TRAIN_NUMBER = 'train_number'
ATTR_TRANSFERS = 'transfers'

CONF_ATTRIBUTION = "Data provided by transport.opendata.ch"
CONF_DESTINATION = 'to'
CONF_START = 'from'

DEFAULT_NAME = 'Next Departure'

ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(seconds=90)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_START): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Swiss public transport sensor."""
    name = config.get(CONF_NAME)
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    connection = SwissPublicTransportSensor(hass, start, destination, name)
    yield from connection.async_update()

    if connection.state is None:
        _LOGGER.error(
            "Check at http://transport.opendata.ch/examples/stationboard.html "
            "if your station names are valid")
        return False

    async_add_devices([connection])


class SwissPublicTransportSensor(Entity):
    """Implementation of an Swiss public transport sensor."""

    def __init__(self, hass, start, destination, name):
        """Initialize the sensor."""
        from opendata_transport import OpendataTransport

        self.hass = hass
        self._name = name
        self._from = start
        self._to = destination
        self._websession = async_get_clientsession(self.hass)
        self._opendata = OpendataTransport(
            self._from, self._to, self.hass.loop, self._websession)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._opendata.connections[0]['departure'] \
            if self._opendata is not None else None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._opendata is None:
            return

        remaining_time = dt_util.parse_datetime(
            self._opendata.connections[0]['departure']) -\
            dt_util.as_local(dt_util.utcnow())

        attr = {
            ATTR_TRAIN_NUMBER: self._opendata.connections[0]['number'],
            ATTR_PLATFORM: self._opendata.connections[0]['platform'],
            ATTR_TRANSFERS: self._opendata.connections[0]['transfers'],
            ATTR_DURATION: self._opendata.connections[0]['duration'],
            ATTR_DEPARTURE_TIME1: self._opendata.connections[1]['departure'],
            ATTR_DEPARTURE_TIME2: self._opendata.connections[2]['departure'],
            ATTR_START: self._opendata.from_name,
            ATTR_TARGET: self._opendata.to_name,
            ATTR_REMAINING_TIME: '{}'.format(remaining_time),
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }
        return attr

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from opendata.ch and update the states."""
        from opendata_transport.exceptions import OpendataTransportError

        try:
            yield from self._opendata.async_get_data()
        except OpendataTransportError:
            _LOGGER.error("Unable to retrieve data from transport.opendata.ch")
            self._opendata = None
