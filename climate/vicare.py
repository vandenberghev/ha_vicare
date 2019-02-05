"""
ViCare climate device.
"""

import logging
from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF,
    STATE_OFF, STATE_HEAT, STATE_ECO, STATE_AUTO, STATE_UNKNOWN)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['PyViCare==0.0.22']

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE | SUPPORT_OPERATION_MODE
CONF_CIRCUIT = 'circuit'

VICARE_MODE_DHW = 'dhw'
VICARE_MODE_DHWANDHEATING = 'dhwAndHeating'
VICARE_MODE_FORCEDREDUCED = 'forcedReduced'
VICARE_MODE_FORCEDNORMAL = 'forcedNormal'
VICARE_MODE_OFF = 'standby'

#VICARE_PROGRAM_ACTIVE = 'active'
#VICARE_PROGRAM_COMFORT = 'comfort'
#VICARE_PROGRAM_ECO = 'eco'
VICARE_PROGRAM_EXTERNAL = 'external'
#VICARE_PROGRAM_HOLIDAY = 'holiday'
#VICARE_PROGRAM_NORMAL = 'normal'
#VICARE_PROGRAM_REDUCED = 'reduced'
#VICARE_PROGRAM_STANDBY = 'standby'

VALUE_UNKNOWN = 'unknown'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CIRCUIT, default=0): cv.positive_int
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    from PyViCare import ViCareSession
    t = ViCareSession(config.get(CONF_USERNAME), config.get(CONF_PASSWORD), "/tmp/vicare_token.save", config.get(CONF_CIRCUIT))
    add_entities([
        ViCareClimate('vicare', t)
    ])


class ViCareClimate(ClimateDevice):
    """Representation of a demo climate device."""

    def __init__(self, name, api):
        """Initialize the climate device."""
        self._name = name
        self._api = api
        self._support_flags = SUPPORT_FLAGS
        self._unit_of_measurement = TEMP_CELSIUS
        self._on = None
        self._away = None
        self._target_temperature = None
        self._operation_list = [STATE_OFF, STATE_HEAT, STATE_ECO, STATE_AUTO]
        self._current_mode = VALUE_UNKNOWN
        self._current_temperature = None
        self._current_program = VALUE_UNKNOWN
        self._previous_mode = VICARE_MODE_FORCEDREDUCED

    def update(self):
        _room_temperature = self._api.getRoomTemperature() 
        if _room_temperature is not None and _room_temperature != "error":
            self._current_temperature = _room_temperature
        else:
            self._current_temperature = -1
        self._current_program = self._api.getActiveProgram()
        _active_mode = self._api.getActiveMode()
        self._current_mode = _active_mode
        self._target_temperature = self._api.getCurrentDesiredTemperature()
        self._away = (_active_mode == VICARE_MODE_FORCEDREDUCED)
        self._on = (_active_mode == VICARE_MODE_DHWANDHEATING or _active_mode == VICARE_MODE_FORCEDREDUCED or _active_mode == VICARE_MODE_FORCEDNORMAL)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._current_mode == VICARE_MODE_DHW:
            return STATE_UNKNOWN #todo: can the HA states be extended?
        elif self._current_mode == VICARE_MODE_DHWANDHEATING:
            return STATE_AUTO
        elif self._current_mode == VICARE_MODE_FORCEDNORMAL:
            return STATE_HEAT
        elif self._current_mode == VICARE_MODE_FORCEDREDUCED:
            return STATE_ECO
        elif self._current_mode == VICARE_MODE_OFF:
            return STATE_OFF
        else:
            return STATE_UNKNOWN

    def set_operation_mode(self, operation_mode):
        if operation_mode in self._operation_list:
            """ 1st Activate externam program """
            self._api.activateProgram(VICARE_PROGRAM_EXTERNAL)
            """ 2nd: set new mode """
            if operation_mode == STATE_HEAT:
                self._api.setMode(VICARE_MODE_FORCEDNORMAL)
            elif operation_mode == STATE_ECO:
                self._api.setMode(VICARE_MODE_FORCEDREDUCED)
            elif operation_mode == STATE_AUTO:
                self._api.setMode(VICARE_MODE_DHWANDHEATING)
            elif operation_mode == STATE_OFF:
                self._api.setMode(VICARE_MODE_OFF)
            else:
                _LOGGER.error(
                    "An error occurred while setting operation mode. "
                    "Unknown operation mode: %s", operation_mode)
        else:
            _LOGGER.error(
                "An error occurred while setting operation mode. "
                "Unsupported operation mode: %s", operation_mode)

        self.aync_schedule_update_ha_state(True)
    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    # @property
    # def current_hold_mode(self):
        # """Return hold mode setting."""
        # return self._hold

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        else:
            return
        
        if self._current_mode == VICARE_MODE_DHWANDHEATING:
            self._api.setProgramTemperature(self._current_program, self._target_temperature)
        elif self._current_mode == VICARE_MODE_FORCEDNORMAL:
            self._api.setReducedTemperature(self._target_temperature)
        elif self._current_mode == VICARE_MODE_FORCEDREDUCED:
            self._api.setReducedTemperature(self._target_temperature)
        else:
            _LOGGER.error(
                "Cannot set the temperature for mode '%s'", self._current_mode)
                
        self.aync_schedule_update_ha_state(True)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self._previous_mode = self._current_mode
        self._api.setMode(VICARE_MODE_FORCEDREDUCED)
        self.aync_schedule_update_ha_state(True)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self._api.setMode(self._previous_mode)
        self.aync_schedule_update_ha_state(True)

    def turn_on(self):
        """Turn on."""
        self._on = True
        self._api.setMode(self._previous_mode)
        self.aync_schedule_update_ha_state(True)

    def turn_off(self):
        """Turn off."""
        self._on = False
        self._previous_mode = self._current_mode
        self._api.setMode(VICARE_MODE_OFF)
        self.aync_schedule_update_ha_state(True)
