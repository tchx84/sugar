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
import os
from ConfigParser import ConfigParser

from gettext import gettext as _
from gi.repository import GConf
from gi.repository import NMClient

from jarabe.model import network


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
        nm_client = NMClient.Client()
        return nm_client.wireless_get_enabled()
    except:
        raise ReadError(_('State is unknown.'))


def print_radio():
    print ('off', 'on')[get_radio()]


def set_radio(state):
    """Turn Radio 'on' or 'off'
    state : 'on/off'
    """
    try:
        state = state or state == 'on' or state == 1
        nm_client = NMClient.Client()
        nm_client.wireless_set_enabled(state)
    except:
        raise ValueError(_('Error in specified radio argument use on/off.'))


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
