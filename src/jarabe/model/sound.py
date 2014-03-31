# Copyright (C) 2006-2008 Red Hat, Inc.
# Copyright (C) 2014 Emil Dudev
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

from gi.repository import Gio

from gi.repository import SugarExt
from sugar3 import dispatch


VOLUME_STEP = 10
_PLAYBACK = 0
_CAPTURE = 1

muted_changed = dispatch.Signal()
volume_changed = dispatch.Signal()

_volume = SugarExt.VolumeAlsa.new(_PLAYBACK)

def get_muted():
    return _volume.get_mute()


def get_volume():
    return _volume.get_volume()


def set_volume(new_volume):
    _volume.set_volume(new_volume)

    volume_changed.send(None)
    save()


def set_muted(new_state):
    _volume.set_mute(new_state)

    muted_changed.send(None)
    save()


def save():
    settings = Gio.Settings('org.sugarlabs.sound')
    settings.set_int('volume', get_volume())


def restore():
    settings = Gio.Settings('org.sugarlabs.sound')
    set_volume(settings.get_int('volume'))


class CaptureSound(object):
    _volume = SugarExt.VolumeAlsa.new(_CAPTURE)

    muted_changed = dispatch.Signal()
    volume_changed = dispatch.Signal()

    def get_muted(self):
        return self._volume.get_mute()

    def get_volume(self):
        return self._volume.get_volume()

    def set_volume(self, new_volume):
        self._volume.set_volume(new_volume)

        self.volume_changed.send(None)

    def set_muted(self, new_state):
        self._volume.set_mute(new_state)

        muted_changed.send(None)


capture_sound = CaptureSound()
