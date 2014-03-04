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
from gi.repository import Pango

from sugar3 import profile
from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.icon import Icon
from sugar3.graphics.icon import get_surface
from sugar3.graphics.palette import Palette
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuItemSeparator
from sugar3.graphics.toolbutton import ToolButton

from jarabe.model import notifications
from jarabe.view.pulsingicon import PulsingIcon
from jarabe.frame.frameinvoker import FrameWidgetInvoker


class NotificationBox(Gtk.VBox):

    MAX_ITEMS = 5
    MAX_WIDTH = 70

    def __init__(self, name):
        Gtk.VBox.__init__(self)
        self._name = name

        self._notifications_menu = Gtk.VBox()
        self._notifications_menu.show()

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.add(self._notifications_menu)
        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                         Gtk.PolicyType.AUTOMATIC)
        self._scrolled_window.show()

        separator = PaletteMenuItemSeparator()
        separator.show()

        clear_item = PaletteMenuItem(_('Clear notifications'), 'dialog-cancel')
        clear_item.connect('activate', self.__clear_cb)
        clear_item.show()

        self.add(self._scrolled_window)
        self.add(separator)
        self.add(clear_item)

        self._service = notifications.get_service()
        for entry in self._service.retrieve_by_name(self._name):
            self._add(entry['summary'], entry['body'])
        self._service.notification_received.connect(
            self.__notification_received_cb)

    def _update_scrolled_size(self):
        entries = self._notifications_menu.get_children()
        req1, req2 = entries[0].get_preferred_size()
        height = min(self.MAX_ITEMS, len(entries)) * req2.height
        self._scrolled_window.set_size_request(-1, height)

    def _add(self, summary, body):
        icon = Icon()
        icon.props.icon_name = 'emblem-notification'
        icon.props.icon_size = Gtk.IconSize.SMALL_TOOLBAR
        icon.props.xo_color = \
            XoColor('%s,%s' % (style.COLOR_WHITE.get_svg(),
                               style.COLOR_BLACK.get_svg()))
        icon.show()

        summary_label = Gtk.Label()
        summary_label.set_max_width_chars(self.MAX_WIDTH)
        summary_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_label.set_alignment(0, 0.5)
        summary_label.set_markup('<b>%s</b>' % summary)
        summary_label.show()

        body_label = Gtk.Label()
        body_label.set_max_width_chars(self.MAX_WIDTH)
        body_label.set_ellipsize(Pango.EllipsizeMode.END)
        body_label.set_alignment(0, 0.5)
        body_label.set_text(body)
        body_label.show()

        grid = Gtk.Grid()
        grid.set_border_width(style.DEFAULT_SPACING) 
        grid.set_column_spacing(style.DEFAULT_SPACING)
        grid.set_row_spacing(0)
        grid. set_row_homogeneous(True)
        grid.attach(icon, 0, 0, 1, 2)
        grid.attach(summary_label, 1, 0, 1, 1)
        grid.attach(body_label, 1, 1, 1, 1)
        grid.show()

        self._notifications_menu.add(grid)
        self._update_scrolled_size()
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


class NotificationButton(ToolButton):

    def __init__(self, name):
        ToolButton.__init__(self)
        self._name = name
        self._icon = None
        self.set_palette_invoker(FrameWidgetInvoker(self))
        self.palette_invoker.cache_palette = False
        self.connect('clicked', self.__clicked_cb)

    def set_icon(self, icon):
        self._icon = icon
        self._icon.show()
        self.set_icon_widget(self._icon)

    def show_badge(self):
        if self._icon:
            self._icon.show_badge()

    def hide_badge(self):
        if self._icon:
            self._icon.hide_badge()

    def create_palette(self):
        notification_box = NotificationBox(self._name)
        palette = Palette(self._name)
        palette.set_group_id('frame')
        palette.set_content(notification_box)
        self.set_palette(palette)

    def __clicked_cb(self, button):
        self.create_palette()
        self.palette.popup(immediate=True, state=Palette.SECONDARY) 


class NotificationPulsingIcon(PulsingIcon):

    def __init__(self, filename=None, name=None, colors=None):
        PulsingIcon.__init__(self)
        self._badge = None

        if filename:
            self.props.icon_filename = filename
        elif name:
            self.props.icon_name = name
        else:
            self.props.icon_name = 'application-octet-stream'

        if not colors:
            colors = profile.get_color()
        self.props.base_color = colors
        self.props.pulse_color = \
            XoColor('%s,%s' % (style.COLOR_BUTTON_GREY.get_svg(),
                               style.COLOR_TOOLBAR_GREY.get_svg()))

    def show_badge(self):
        self._badge = get_surface(icon_name='emblem-notification',
                                  width=22, height=22)

    def hide_badge(self):
        self._badge = None

    def do_draw(self, cr):
        PulsingIcon.do_draw(self, cr)
        if self._badge:
            cr.set_source_surface(self._badge, 22, 22)
            cr.paint()


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
