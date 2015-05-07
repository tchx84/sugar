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

import os
import logging

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GObject


_instance = None


def get_instance():
    global _instance
    if _instance is None:
        _instance = Brightness()
    return _instance


class Brightness(GObject.GObject):

    MONITOR_RATE = 1000

    changed_signal = GObject.Signal('changed', arg_types=([int]))

    def __init__(self):
        GObject.GObject.__init__(self)
        self._path = None
        self._helper_path = None
        self._max_brightness = None
        self._monitor = None
        self._start_monitoring()

    def _start_monitoring(self):
        if not self.get_path():
            return

        self._monitor = Gio.File.new_for_path(self.get_path()) \
            .monitor_file(Gio.FileMonitorFlags.WATCH_HARD_LINKS, None)
        self._monitor.set_rate_limit(self.MONITOR_RATE)
        self._monitor_changed_hid = \
            self._monitor.connect('changed', self.__externally_changed_cb)

    def __externally_changed_cb(self, monitor, child, other_file, event):
        if event == Gio.FileMonitorEvent.CHANGED:
            self.changed_signal.emit(self.get_brightness())

    def _get_helper(self):
        if self._helper_path is None and 'PATH' in os.environ:
            for path in os.environ['PATH'].split(os.pathsep):
                helper_path = os.path.join(path, 'sugar-backlight-helper')
                if os.path.exists(helper_path):
                    self._helper_path = helper_path
                    break
        return self._helper_path

    def _helper_read(self, option):
        cmd = '%s --%s' % (self._get_helper(), option)
        logging.debug(cmd)
        result, output, error, status = GLib.spawn_command_line_sync(cmd)
        logging.debug(output)
        return output.rstrip('\0\n')

    def _helper_write(self, option, value):
        cmd = 'pkexec %s --%s %d' % (self._get_helper(), option, value)
        logging.debug(cmd)
        result, output, error, status = GLib.spawn_command_line_sync(cmd)
        logging.debug(result)

    def set_brightness(self, value):
        # ignore external changes for a while
        self._monitor.handler_block(self._monitor_changed_hid)

        self._helper_write('set-brightness', value)
        self.changed_signal.emit(value)

        # listen to external changes after already checked
        GLib.timeout_add(self.MONITOR_RATE * 2,
            self._monitor.handler_unblock, self._monitor_changed_hid)

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
