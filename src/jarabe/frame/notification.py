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

import logging
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuItemSeparator

from jarabe.model import notifications
from jarabe.view.pulsingicon import PulsingIcon


class NotificationBox(Gtk.VBox):

    def __init__(self, name):
        Gtk.VBox.__init__(self)
        self._name = name

        upper_separator = PaletteMenuItemSeparator()
        lower_separator = PaletteMenuItemSeparator()

        clear_item = PaletteMenuItem(_('Clear notifications'), 'dialog-cancel')
        clear_item.connect('activate', self.__clear_cb)

        options_menu = PaletteMenuBox()
        options_menu.append_item(upper_separator)
        options_menu.append_item(clear_item)
        options_menu.append_item(lower_separator)

        # TODO use Gtk.ScrolledWindow to handle expansion
        self._notifications_menu = PaletteMenuBox()

        self.add(options_menu)
        self.add(self._notifications_menu)

        self._service = notifications.get_service()
        for entry in self._service.retrieve_by_name(self._name):
            self._add(entry['summary'], entry['body'])
        self._service.notification_received.connect(
            self.__notification_received_cb)

    def _add(self, summary, body):
        # TODO the size of Items does not look right
        item = PaletteMenuItem('', 'emblem-notification')
        item.set_label('<b>%s</b>\n%s' % (summary, body))
        self._notifications_menu.append_item(item)
        self.show()

    def __clear_cb(self, clear_item):
        logging.debug('NotificationBox.__clear_cb')
        for item in self._notifications_menu.get_children():
            self._notifications_menu.remove(item)
        self._service.clear_by_name(self._name)
        self.hide()

    def __notification_received_cb(self, **kwargs):
        logging.debug('NotificationBox.__notification_received_cb')
        if kwargs.get('app_name', '') == self._name:
            self._add(kwargs.get('summary', ''), kwargs.get('body', ''))


class NotificationIcon(Gtk.EventBox):
    __gtype_name__ = 'SugarNotificationIcon'

    __gproperties__ = {
        'xo-color': (object, None, None, GObject.PARAM_READWRITE),
        'icon-name': (str, None, None, None, GObject.PARAM_READWRITE),
        'icon-filename': (str, None, None, None, GObject.PARAM_READWRITE),
    }

    _PULSE_TIMEOUT = 3

    def __init__(self, **kwargs):
        self._icon = PulsingIcon(pixel_size=style.STANDARD_ICON_SIZE)
        Gtk.EventBox.__init__(self, **kwargs)
        self.props.visible_window = False

        self._icon.props.pulse_color = \
            XoColor('%s,%s' % (style.COLOR_BUTTON_GREY.get_svg(),
                               style.COLOR_TRANSPARENT.get_svg()))
        self._icon.props.pulsing = True
        self.add(self._icon)
        self._icon.show()

        GObject.timeout_add_seconds(self._PULSE_TIMEOUT,
                                    self.__stop_pulsing_cb)

        self.set_size_request(style.GRID_CELL_SIZE, style.GRID_CELL_SIZE)

    def __stop_pulsing_cb(self):
        self._icon.props.pulsing = False
        return False

    def do_set_property(self, pspec, value):
        if pspec.name == 'xo-color':
            if self._icon.props.base_color != value:
                self._icon.props.base_color = value
        elif pspec.name == 'icon-name':
            if self._icon.props.icon_name != value:
                self._icon.props.icon_name = value
        elif pspec.name == 'icon-filename':
            if self._icon.props.file != value:
                self._icon.props.file = value

    def do_get_property(self, pspec):
        if pspec.name == 'xo-color':
            return self._icon.props.base_color
        elif pspec.name == 'icon-name':
            return self._icon.props.icon_name
        elif pspec.name == 'icon-filename':
            return self._icon.props.file

    def _set_palette(self, palette):
        self._icon.palette = palette

    def _get_palette(self):
        return self._icon.palette

    palette = property(_get_palette, _set_palette)


class NotificationWindow(Gtk.Window):
    __gtype_name__ = 'SugarNotificationWindow'

    def __init__(self, **kwargs):

        Gtk.Window.__init__(self, **kwargs)

        self.set_decorated(False)
        self.set_resizable(False)
        self.connect('realize', self._realize_cb)

    def _realize_cb(self, widget):
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_window().set_accept_focus(False)

        color = Gdk.color_parse(style.COLOR_TOOLBAR_GREY.get_html())
        self.modify_bg(Gtk.StateType.NORMAL, color)
