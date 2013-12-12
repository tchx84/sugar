# Copyright (C) 2010, Paraguay Educa <tecnologia@paraguayeduca.org>
# Copyright (C) 2010, Plan Ceibal <comunidad@plan.ceibal.edu.uy>
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

from gi.repository import GObject
from gi.repository import GLib

import os
import subprocess

from gettext import gettext as _

BACKUP_OF_CURRENT_SYSTEM_NOT_FOUND = 1

SCRIPT_EXIT_CODES_AND_MESSAGES = {}
SCRIPT_EXIT_CODES_AND_MESSAGES[BACKUP_OF_CURRENT_SYSTEM_NOT_FOUND] = \
    _('No journal-backup has been taken for this XO. \n'
      'Please ensure that you have a valid backup residing on the drive.')


class ProcessManagement(GObject.GObject):

    __gtype_name__ = 'ProcessManagement'

    __gsignals__ = {
        'process-management-running': (GObject.SignalFlags.RUN_FIRST, None,
                                       ([str])),
        'process-management-started': (GObject.SignalFlags.RUN_FIRST, None,
                                       ([])),
        'process-management-finished': (GObject.SignalFlags.RUN_FIRST, None,
                                        ([])),
        'process-management-failed': (GObject.SignalFlags.RUN_FIRST, None,
                                      ([str]))
    }

    def __init__(self):
        GObject.GObject.__init__(self)
        self._running = False
        self._process = None

    def do_process(self, cmd):
        self._run_cmd_async(cmd)

    def _check_process_output(self):
        status = self._process.poll()
        if status is None:
            self.emit('process-management-running', '')
            GLib.timeout_add_seconds(5, self._check_process_output)
        else:
            if status == 0:
                self.emit('process-management-finished')
            else:
                if int(status) in SCRIPT_EXIT_CODES_AND_MESSAGES:
                    self.emit('process-management-failed',
                              SCRIPT_EXIT_CODES_AND_MESSAGES[status])
                else:
                    self.emit('process-management-failed', str(status))

    def _notify_process_status(self):
        GObject.idle_add(self._check_process_output)

    def _run_cmd_async(self, cmd):
        if not self._running:
            try:
                self._process = subprocess.Popen(cmd)

            except Exception:
                self.emit('process-management-failed',
                          _("Error - Call process: ") + str(cmd))
            else:
                self._notify_process_status()
                self._running = True
                self.emit('process-management-started')


def find_and_absolutize(script_name):
    paths = os.environ['PATH'].split(':')
    for path in paths:
        looking_path = path + '/' + script_name
        if os.path.isfile(looking_path):
            return looking_path
    return None
