import logging
import requests
import json
from datetime import datetime
from datetime import timedelta
import voluptuous as vol
from pprint import pprint

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_RESOURCES)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(days=1)

SENSOR_PREFIX = 'Waste '

SENSOR_TYPES = {
    'gelbersack': ['Gelber Sack', '', 'mdi:recycle'],
    'restabfall': ['Rest Müll', '', 'mdi:recycle'],
    'papiertonne': ['Papier Tonne', '', 'mdi:recycle'],
    'biotonne': ['Bio Müll', '', 'mdi:recycle'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug("Setup Abfall API retriever")

    try:
        data = AbfallData()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [
                sensor_type.title(), '', 'mdi:flash']

        entities.append(AbfallSensor(data, sensor_type))

    add_entities(entities)

class AbfallData(object):
    
    def __init__(self):
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        _LOGGER.debug("Updating Abfall dates using remote API")
        try:
            r = requests.get(
                "https://www.wuerzburg.de/themen/umwelt-verkehr/vorsorge-entsorgung/abfallkalender/index.html?_func=evList&_mod=events&ev[start]=2018-12-24&ev[end]=2019-12-31&ev[cat]=&ev[subcat]=&ev[addr]=19943&ev[search]=&_y=2019&_m=01&recon=3vh5q416tm9ich27uec858i6ge&_dc=1546356725630"
                )

            response = json.loads(r.text)
            data = response['contents']

            gelberSack = []
            restAbfall = []
            papierTonne =[]
            bioTonne = []

            for element in data:
                item = data[element]

                if item['title'] == 'Gelber Sack':
                    gelberSack.append(datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S'))
                elif item['title'] == 'Papier':
                    papierTonne.append(datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S'))
                elif item['title'] == 'Bioabfall':
                    bioTonne.append(datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S'))
                elif item['title'] == 'Restmüll':
                    restAbfall.append(datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S'))

            gelberSack.sort(key=lambda date: date)
            papierTonne.sort(key=lambda date: date)
            bioTonne.sort(key=lambda date: date)
            restAbfall.sort(key=lambda date: date)

            nextDates = {}
                        
            for nextDate in gelberSack:
                if nextDate > datetime.now():
                    nextDates["gelberSack"] = nextDate
                    break

            for nextDate in papierTonne:
                if nextDate > datetime.now():
                    nextDates["papierTonne"] = nextDate
                    break

            for nextDate in bioTonne:
                if nextDate > datetime.now():
                    nextDates['bioTonne'] = nextDate
                    break

            for nextDate in restAbfall:
                if nextDate > datetime.now():
                    nextDates["restAbfall"] = nextDate
                    break
                       
            self.data = nextDates

        except requests.exceptions.RequestException as exc:
            _LOGGER.error("Error occurred while fetching data: %r", exc)
            self.data = None
            return False

class AbfallSensor(Entity):

    def __init__(self, data, sensor_type):
        self.data = data
        self.type = sensor_type
        self._name = SENSOR_PREFIX + SENSOR_TYPES[self.type][0]
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._state = None
        self._attributes = {}
        
    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes

    def update(self):
        self.data.update()
        abfallData = self.data.data

        try:
            if self.type == 'gelbersack':
                self._state = abfallData.get("gelberSack")

            elif self.type == 'restabfall':
                self._state = abfallData.get("restAbfall")

            elif self.type == 'papiertonne':
                self._state = abfallData.get("papierTonne")

            elif self.type == 'biotonne':
                self._state = abfallData.get("bioTonne")

            if self._state is not None:
                weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                self._attributes['days'] = (self._state.date() - datetime.now().date()).days
                if self._attributes['days'] == 0:
                  printtext = "heute"
                elif self._attributes['days'] == 1:
                  printtext = "morgen"
                else:
                  printtext = 'in {} Tagen'.format(self._attributes['days'])
                self._attributes['display_text'] = self._state.strftime('{}, %d.%m.%Y ({})').format(weekdays[self._state.weekday()],printtext) 
        
        except ValueError:
            self._state = None
