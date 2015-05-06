# Copyright (C) 2015, Martin Abente Lahaye - tch@sugarlabs.org
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

import logging

from gi.repository import GLib
from gi.repository import GObject


_instance = None


def get_instance():
    global _instance
    if _instance is None:
        _instance = Brightness()
    return _instance


class Brightness(GObject.GObject):

    changed_signal = GObject.Signal('changed', arg_types=([int]))

    def __init__(self):
        GObject.GObject.__init__(self)
        self._path = None
        self._max_brightness = None

    def _get_helper(self):
        # XXX determine installation path programmatically
        return '/usr/libexec/sugar-backlight-helper'

    def _helper_read(self, option):
        cmd = '%s --%s' % (self._get_helper(), option)
        logging.debug(cmd)
        result, output, error, status = GLib.spawn_command_line_sync(cmd)
        logging.debug(output)
        return output

    def _helper_write(self, option, value):
        cmd = 'pkexec %s --%s %d' % (self._get_helper(), option, value)
        logging.debug(cmd)
        result, output, error, status = GLib.spawn_command_line_sync(cmd)
        logging.debug(result)

    def set_brightness(self, value):
        self._helper_write('set-brightness', value)

    def get_path(self):
        if self._path is None:
            self._path = str(self._helper_read('get-path'))
        return self._path

    def get_brightness(self):
        return int(self._helper_read('get-brightness'))

    def get_max_brightness(self):
        if self._max_brightness is None:
            self._max_brightness = int(self._helper_read('get-max-brightness'))
        return self._max_brightness
