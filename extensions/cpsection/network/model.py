# Copyright (C) 2008 One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import logging

import dbus
import uuid
import os
from ConfigParser import ConfigParser

from gettext import gettext as _
from gi.repository import GConf

from jarabe.model import network


_NM_SERVICE = 'org.freedesktop.NetworkManager'
_NM_PATH = '/org/freedesktop/NetworkManager'
_NM_IFACE = 'org.freedesktop.NetworkManager'

KEYWORDS = ['network', 'jabber', 'radio', 'server']


class ReadError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def get_jabber():
    client = GConf.Client.get_default()
    return client.get_string('/desktop/sugar/collaboration/jabber_server')


def print_jabber():
    print get_jabber()


def set_jabber(server):
    """Set the jabber server
    server : e.g. 'olpc.collabora.co.uk'
    """
    client = GConf.Client.get_default()
    client.set_string('/desktop/sugar/collaboration/jabber_server', server)

    return 0


def get_radio():
    try:
        bus = dbus.SystemBus()
        obj = bus.get_object(_NM_SERVICE, _NM_PATH)
        nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
    except dbus.DBusException:
        raise ReadError('%s service not available' % _NM_SERVICE)

    state = nm_props.Get(_NM_IFACE, 'WirelessEnabled')
    if state in (0, 1):
        return state
    else:
        raise ReadError(_('State is unknown.'))


def print_radio():
    print ('off', 'on')[get_radio()]


def set_radio(state):
    """Turn Radio 'on' or 'off'
    state : 'on/off'
    """
    if state == 'on' or state == 1:
        try:
            bus = dbus.SystemBus()
            obj = bus.get_object(_NM_SERVICE, _NM_PATH)
            nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
        except dbus.DBusException:
            raise ReadError('%s service not available' % _NM_SERVICE)
        nm_props.Set(_NM_IFACE, 'WirelessEnabled', True)
    elif state == 'off' or state == 0:
        try:
            bus = dbus.SystemBus()
            obj = bus.get_object(_NM_SERVICE, _NM_PATH)
            nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
        except dbus.DBusException:
            raise ReadError('%s service not available' % _NM_SERVICE)
        nm_props.Set(_NM_IFACE, 'WirelessEnabled', False)
    else:
        raise ValueError(_('Error in specified radio argument use on/off.'))

    return 0


def clear_registration():
    """Clear the registration with the schoolserver
    """
    client = GConf.Client.get_default()
    client.set_string('/desktop/sugar/backup_url', '')
    return 1


def clear_networks():
    """Clear saved passwords and network configurations.
    """
    try:
        connections = network.get_connections()
    except dbus.DBusException:
        logging.debug('NetworkManager not available')
        return
    connections.clear()


def have_networks():
    try:
        connections = network.get_connections()
        return len(connections.get_list()) > 0
    except dbus.DBusException:
        logging.debug('NetworkManager not available')
        return False


def get_publish_information():
    client = GConf.Client.get_default()
    publish = client.get_bool('/desktop/sugar/collaboration/publish_gadget')
    return publish


def print_publish_information():
    print get_publish_information()


def set_publish_information(value):
    """ If set to true, Sugar will make you searchable for
    the other users of the Jabber server.
    value: 0/1
    """
    try:
        value = (False, True)[int(value)]
    except:
        raise ValueError(_('Error in specified argument use 0/1.'))

    client = GConf.Client.get_default()
    client.set_bool('/desktop/sugar/collaboration/publish_gadget', value)
    return 0


def get_connectivity_profiles():
    """
    To simplify the use of complex proxy or connectivity configurations
    the deployments can use a file to create template configurations.
    """

    connectivity_profiles = {}
    profiles_path = '/etc/sugar_connection_profiles.ini'

    if os.path.exists(profiles_path):
        cp = ConfigParser()
        cp.readfp(open(profiles_path))
        for section in cp.sections():
            # check mandatory fields
            if not cp.has_option(section, 'type'):
                logging.error(
                    'Connectivity profile file %s section "%s",'
                    ' do not have type',
                    profiles_path, section)
                break
            if cp.get(section, 'type') not in ('proxy', 'connectivity'):
                logging.error(
                    'Connectivity profile file %s section "%s", type should'
                    ' be "proxy" or "connectivity"', profiles_path, section)
                break

            if not cp.has_option(section, 'title'):
                logging.error(
                    'Connectivity profile file %s section "%s",'
                    ' do not have title',
                    profiles_path, section)
                break

            options = {}
            for option in cp.options(section):
                options[option] = cp.get(section, option)
            connectivity_profiles[section] = options

    return connectivity_profiles


def get_proxy_profile_name():
    client = GConf.Client.get_default()
    return client.get_string('/desktop/sugar/network/proxy/profile_name')


def set_proxy_profile_name(profile_name):
    if profile_name is None:
        profile_name = ''
    client = GConf.Client.get_default()
    client.set_string('/desktop/sugar/network/proxy/profile_name',
                      profile_name)


def parameter_as_boolean(profile, parameter):
    value = False
    if parameter in profile:
        value = profile[parameter].upper() in ('1', 'TRUE', 'YES')
    return value


class HiddenNetworkManager():

    def __init__(self, conn_profiles={}):
        client = GConf.Client.get_default()
        self.enabled = client.get_bool(
            '/desktop/sugar/extensions/network/conf_hidden_ssid')
        if not self.enabled:
            logging.debug('Hidden network configuration disabled')
            return
        try:
            self._bus = dbus.SystemBus()
            self._netmgr = network.get_manager()
        except dbus.DBusException:
            logging.debug('NetworkManager not available')
            return

        self._netmgr.GetDevices(reply_handler=self.__get_devices_reply_cb,
                                error_handler=self.__get_devices_error_cb)

        # get the list of connectivity profiles of type "connectivity"
        self.network_profiles = []
        logging.debug('profiles %s', conn_profiles)
        for profile_key in conn_profiles:
            profile = conn_profiles[profile_key]
            if profile['type'] == 'connectivity':
                self.network_profiles.append(profile)
        self.selected_profile = None

    def __get_devices_reply_cb(self, devices_o):
        logging.debug('__get_devices_reply_cb len(devices) = %d',
                      len(devices_o))
        for dev_o in devices_o:
            self._check_device(dev_o)

    def __get_devices_error_cb(self, err):
        logging.error('Failed to get devices: %s', err)

    def _check_device(self, device_o):
        device = self._bus.get_object(network.NM_SERVICE, device_o)
        props = dbus.Interface(device, dbus.PROPERTIES_IFACE)

        device_type = props.Get(network.NM_DEVICE_IFACE, 'DeviceType')
        if device_type == network.NM_DEVICE_TYPE_WIFI:
            state = props.Get(network.NM_DEVICE_IFACE, 'State')
            if state == 100:  # Activated
                self._active_device = device_o

    def _get_device_path_error_cb(self, err):
        logging.error('Failed to get device type: %s', err)

    def create_and_connect_by_ssid(self, ssid):
        connection = network.find_connection_by_ssid(ssid)
        if connection is None:
            # Th connection do not exists
            settings = network.Settings()
            settings.connection.id = ssid
            settings.connection.type = \
                network.NM_CONNECTION_TYPE_802_11_WIRELESS
            settings.connection.uuid = str(uuid.uuid4())
            settings.connection.autoconnect = True

            settings.wireless.ssid = dbus.ByteArray(ssid)
            settings.wireless.hidden = True
            logging.debug('AddAndActivateConnection')
            self._netmgr.AddAndActivateConnection(
                settings.get_dict(),
                self._active_device, '/',
                reply_handler=self._add_connection_reply_cb,
                error_handler=self._add_connection_error_cb)
        else:
            logging.debug('ActivateConnection')
            self._netmgr.ActivateConnection(
                connection.get_path(),
                self._active_device, '/')

    def create_and_connect_by_profile(self):
        """
        A profile is a dictionary with a format like this
        profile {'title': 'Queensland', 'type': 'connectivity',
            'connection.id': 'QDETA-X',
            'connection.type': '802-11-wireless',
            '802-1x.eap': 'peap',
            '802-1x.identity': 'uuuuu',
            '802-1x.password': 'pppppp',
            '802-1x.phase2-auth': 'mschapv2',
            '802-11-wireless.security': '802-11-wireless-security',
            '802-11-wireless.ssid': 'QDETA-X',
            '802-11-wireless-security.key-mgmt': 'wpa-eap',
            'ipv4.method': 'auto',
                }
        """
        if self.selected_profile is None:
            logging.error('No profile selected')
            return

        profile = self.selected_profile
        connection = network.find_connection_by_ssid(profile['connection.id'])
        if connection is None:
            # Th connection do not exists
            settings = network.Settings()
            settings.connection.id = profile['connection.id']
            settings.connection.type = profile['connection.type']
            settings.connection.uuid = str(uuid.uuid4())
            settings.connection.autoconnect = True

            settings.wireless.ssid = dbus.ByteArray(
                profile['802-11-wireless.ssid'])
            settings.wireless.hidden = True

            if '802-11-wireless.security' in profile and \
                    profile['802-11-wireless.security'].upper() not in \
                    ('', 'NONE'):
                settings.wireless_security = network.WirelessSecurity()
                settings.wireless_security.key_mgmt = \
                    profile['802-11-wireless-security.key-mgmt']

                if settings.wireless_security.key_mgmt == 'wpa-eap':
                    settings.wpa_eap_setting = network.EapSecurity()
                    settings.wpa_eap_setting.eap = profile['802-1x.eap']
                    settings.wpa_eap_setting.identity = profile[
                        '802-1x.identity']
                    settings.wpa_eap_setting.password = profile[
                        '802-1x.password']
                    settings.wpa_eap_setting.phase2_auth = profile[
                        '802-1x.phase2-auth']

            if 'ipv4.method' in profile and \
                    profile['ipv4.method'].upper() not in ('', 'NONE'):
                settings.ip4_config = network.IP4Config()
                settings.ip4_config.method = profile['ipv4.method']

            logging.error('createby_profile %s', settings.get_dict())

            self._netmgr.AddAndActivateConnection(
                settings.get_dict(),
                self._active_device, '/',
                reply_handler=self._add_connection_reply_cb,
                error_handler=self._add_connection_error_cb)
        else:
            self._netmgr.ActivateConnection(
                connection.get_path(),
                self._active_device, '/')

    def _add_connection_reply_cb(self, netmgr, connection):
        logging.debug('Added connection: %s', connection)

    def _add_connection_error_cb(self, err):
        logging.error('Failed to add connection: %s', err)
