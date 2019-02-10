"""
Support for the Thermosmart thermostat.

For more details about this component, please refer to the documentation at
???
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['thermosmart_hass==0.4.0']

_LOGGER = logging.getLogger(__name__)

AUTH_CALLBACK_NAME = 'api:thermosmart'
AUTH_CALLBACK_PATH = '/api/thermosmart'

API_CLIENT_ID =  'api-rob-b130d8f5123bf24b'
API_CLIENT_SECRET = 'c1d91661eef0bc4fa2ac67fd' 

CONFIGURATOR_DESCRIPTION = "To link your Thermosmart account, " \
                           "click the link, login, and authorize:"
CONFIGURATOR_LINK_NAME = "Link Thermosmart account"
CONFIGURATOR_SUBMIT_CAPTION = "I authorized successfully"

UPDATE_TIME = timedelta(seconds=30)

DEFAULT_CACHE_PATH = '.thermosmart-token-cache'
DEFAULT_NAME = 'Thermosmart'
DEPENDENCIES = ['http']
DOMAIN = 'thermosmart'
AUTH_DATA = 'thermosmart_auth'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

def request_configuration(hass, config, oauth):
    """Request Thermomosmart autorization"""
    configurator = hass.components.configurator
    hass.data[AUTH_DATA] = configurator.request_config(
        DEFAULT_NAME, lambda _: None,
        link_name=CONFIGURATOR_LINK_NAME,
        link_url=oauth.get_authorize_url(),
        description=CONFIGURATOR_DESCRIPTION,
        submit_caption=CONFIGURATOR_SUBMIT_CAPTION)

def setup(hass, config):
    """Set up the Thermosmart."""
    from thermosmart_hass import oauth2 as oauth2
    
    callback_url = '{}{}'.format(hass.config.api.base_url, AUTH_CALLBACK_PATH)
    cache = hass.config.path(DEFAULT_CACHE_PATH)
    oauth = oauth2.ThermosmartOAuth(
        API_CLIENT_ID, API_CLIENT_SECRET,                            
        callback_url, cache_path=cache
    )
    token_info = oauth.get_cached_token()
    if not token_info:
        _LOGGER.info("No token, requesting authorization.")
        hass.http.register_view(ThermosmartAuthCallbackView(
            config, oauth))
        request_configuration(hass, config, oauth)
        return True
    if hass.data.get(AUTH_DATA):
        _LOGGER.info("Token found.")
        configurator = hass.components.configurator
        configurator.request_done(hass.data.get(AUTH_DATA))
        del hass.data[AUTH_DATA]

    hass.data[DOMAIN] = ThermoSmartData(token_info)

    discovery.load_platform(
        hass, 'climate', DOMAIN, 
        {CONF_NAME: config[DOMAIN].get(CONF_NAME,None)}, config
    )

    if hass.data[DOMAIN].thermosmart.opentherm():
        discovery.load_platform(
            hass, 'sensor', DOMAIN, 
            {CONF_NAME: config[DOMAIN].get(CONF_NAME,None)}, config
        )
    
    return True

class ThermosmartAuthCallbackView(HomeAssistantView):
    """Thermosmart Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, config, oauth):
        """Initialize."""
        self.config = config
        self.oauth = oauth

    @callback
    def get(self, request):
        """Receive authorization token."""
        hass = request.app['hass']
        self.oauth.get_access_token(request.query['code'])
        hass.async_add_job(
            setup, hass, self.config)

class ThermoSmartData:
    """Get the latest data from Thermosmart."""
    def __init__(self, token_info):
        import thermosmart_hass as tsmart
        self.thermosmart = tsmart.ThermoSmart(token=token_info['access_token'])

    @Throttle(UPDATE_TIME)
    def update(self):
        """Get the latest update from Thermosmart."""
        self.thermosmart.update()
