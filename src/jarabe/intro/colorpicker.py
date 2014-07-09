# Copyright (C) 2007, Red Hat, Inc.
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

from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics.icon import EventIcon
from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor

import logging


class ColorPicker(Gtk.EventBox):
    def __init__(self):
        Gtk.EventBox.__init__(self)
        self._xo_color = None

        self._xo = EventIcon(pixel_size=style.XLARGE_ICON_SIZE,
                        icon_name='computer-xo')
        self._set_random_colors()
        self.connect('button-press-event', self._button_press_cb)
        self.add(self._xo)
        self._xo.show()

    def _button_press_cb(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            logging.error('selecting random color')
            self._set_random_colors()

    def get_color(self):
        return self._xo_color

    def _set_random_colors(self):
        self._xo_color = XoColor()
        self._xo.props.xo_color = self._xo_color
