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


def apply_cntlm_configs(user, password, domain, host, port):
    import sys
    import subprocess

    try:
        # we need create the config file with the password the first time
        # generate the hash, and create a new config file
        # with the hash instead of the pass

        # 1) create config file with password
        temp_file_name = _create_cntlm_config_file(user, password, domain,
                                                   host, port)

        # 2) generate the hash
        output = subprocess.check_output([
            'su', '-c', 'echo %s | /sbin/cntlm -H -c %s' % (password,
                                                            temp_file_name)])
        logging.error('first temp config file created %s', temp_file_name)
        # FIXME: commented for debug
        #os.unlink(temp_file_name)

        hash_lines = []
        for line in output.split('\n'):
            if not line.startswith('Password:'):
                hash_lines.append(line)

        # 3) create config file with the hash
        temp_file_name = _create_cntlm_config_file(user, password, domain,
                                                   host, port, hash_lines)
        logging.error('second    temp config file created %s', temp_file_name)

        # 4) copy as root to /etc/cntlm.conf
        subprocess.check_call(['su', '-c',
                               'cp %s /etc/cntlm.conf' % temp_file_name])
        # FIXME: commented for debug
        #os.unlink(temp_file_name)

        # 5) restart the service
        subprocess.check_call(['su', '-c', 'systemctl restart cntlm.service'])

    except:
        logging.error('Exception trying to configure cntlm service: %s',
                      sys.exc_info()[0])

    # save the parameters in gconf
    client = GConf.Client.get_default()
    client.set_string('/desktop/sugar/network/proxy/cntlm_user', user)
    client.set_string('/desktop/sugar/network/proxy/cntlm_password', password)
    client.set_string('/desktop/sugar/network/proxy/cntlm_domain', domain)
    client.set_string('/desktop/sugar/network/proxy/cntlm_host', host)
    client.set_string('/desktop/sugar/network/proxy/cntlm_port', port)


def _create_cntlm_config_file(user, password, domain, host, port,
                              hash_lines=None):
    import tempfile
    config_file_content = \
        'Username	%s\n' \
        'Domain		%s\n' \
        'Proxy		%s:%s\n' \
        'NoProxy		localhost, 127.0.0.*, 10.*, 192.168.*\n' \
        'Listen		127.0.0.1:3128\n' \
        'Gateway	yes\n' % (user, domain, host, port)

    with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_config:
        temp_config.write(config_file_content)
        # create with hash or password
        if hash_lines:
            for line in hash_lines:
                temp_config.write('%s\n' % line)
        else:
            temp_config.write('Password	%s\n' % password)

        file_name = temp_config.name

    return file_name


def get_cntlm_parameters():
    client = GConf.Client.get_default()
    user = client.get_string('/desktop/sugar/network/proxy/cntlm_user')
    if user is None:
        user =  ''
    password = client.get_string(
        '/desktop/sugar/network/proxy/cntlm_password')
    if password is None:
        password = ''
    domain = client.get_string('/desktop/sugar/network/proxy/cntlm_domain')
    if domain is None:
        domain = ''
    host = client.get_string('/desktop/sugar/network/proxy/cntlm_host')
    if host is None:
        host = ''
    port = client.get_string('/desktop/sugar/network/proxy/cntlm_port')
    if port is None:
        port = ''
    return (user, password, domain, host, port)


def get_proxy_profile_type():
    client = GConf.Client.get_default()
    return client.get_string('/desktop/sugar/network/proxy/profile_type')


def set_proxy_profile_type(profile_type):
    if profile_type is None:
        profile_type = ''
    client = GConf.Client.get_default()
    client.set_string('/desktop/sugar/network/proxy/profile_type',
                      profile_type)


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
