# Copyright (C) 2008, OLPC
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Pango

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert


CLASS = 'Network'
ICON = 'module-network'
TITLE = _('Network')

_APPLY_TIMEOUT = 3000


class SettingBox(Gtk.HBox):
    """
    Base class for "lines" on the screen representing configuration
    settings.
    """
    def __init__(self, name, size_group=None):
        Gtk.HBox.__init__(self, spacing=style.DEFAULT_SPACING)
        label = Gtk.Label(name)
        label.modify_fg(Gtk.StateType.NORMAL,
                        style.COLOR_SELECTION_GREY.get_gdk_color())
        label.set_alignment(1, 0.5)
        if size_group is not None:
            size_group.add_widget(label)
        self.pack_start(label, False, False, 0)
        label.show()


class ComboSettingBox(Gtk.VBox):
    """
    Container for sets of different settings selected by a top-level
    setting.

    Renders the top level setting as a ComboBox.  Only the currently
    active set is shown on screen.
    """
    def __init__(self, name, setting, setting_key,
                 option_sets, size_group=None):
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)

        setting_box = SettingBox(name, size_group)
        self.pack_start(setting_box, False, False, 0)
        setting_box.show()

        model = Gtk.ListStore(str, str, object)
        combo_box = Gtk.ComboBox(model=model)
        combo_box.connect('changed', self.__combo_changed_cb)
        setting_box.pack_start(combo_box, True, True, 0)
        combo_box.show()

        cell_renderer = Gtk.CellRendererText()
        cell_renderer.props.ellipsize = Pango.EllipsizeMode.MIDDLE
        cell_renderer.props.ellipsize_set = True
        combo_box.pack_start(cell_renderer, True)
        combo_box.add_attribute(cell_renderer, 'text', 0)
        combo_box.props.id_column = 1

        self._settings_box = Gtk.VBox()
        self._settings_box.show()
        self.pack_start(self._settings_box, False, False, 0)

        for optset in option_sets:
            model.append(optset)

        setting.bind(setting_key, combo_box, 'active-id',
                     Gio.SettingsBindFlags.DEFAULT)

    def __combo_changed_cb(self, combobox):
        giter = combobox.get_active_iter()
        new_box = combobox.get_model().get(giter, 2)[0]
        current_box = self._settings_box.get_children()
        if current_box:
            self._settings_box.remove(current_box[0])

        self._settings_box.add(new_box)
        new_box.show()


class OptionalSettingsBox(Gtk.VBox):
    """
    Container for settings (de)activated by a top-level setting.

    Renders the top level setting as a CheckButton. The settings are only
    shown on screen if the top-level setting is enabled.
    """
    def __init__(self, name, setting, setting_key, contents_box):
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)

        check_button = Gtk.CheckButton()
        check_button.props.label = name
        check_button.connect('toggled', self.__button_toggled_cb, contents_box)
        check_button.show()
        self.pack_start(check_button, True, True, 0)
        self.pack_start(contents_box, False, False, 0)

        setting.bind(setting_key, check_button, 'active',
                     Gio.SettingsBindFlags.DEFAULT)

    def __button_toggled_cb(self, check_button, contents_box):
        contents_box.set_visible(check_button.get_active())


class HostPortSettingBox(SettingBox):
    """
    A configuration line for a combined host name and port setting.
    """
    def __init__(self, name, setting, size_group=None):
        SettingBox.__init__(self, name, size_group)

        host_entry = Gtk.Entry()
        self.pack_start(host_entry, True, True, 0)
        host_entry.show()

        setting.bind('host', host_entry, 'text', Gio.SettingsBindFlags.DEFAULT)

        # port number 0 means n/a
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10)
        port_spinbutton = Gtk.SpinButton(adjustment=adjustment, climb_rate=0.1)
        self.pack_start(port_spinbutton, False, False, 0)
        port_spinbutton.show()

        setting.bind('port', port_spinbutton, 'value',
                     Gio.SettingsBindFlags.DEFAULT)


class StringSettingBox(SettingBox):
    """
    A configuration line for a string setting.
    """
    def __init__(self, name, setting, setting_key, size_group=None):
        SettingBox.__init__(self, name, size_group)

        entry = Gtk.Entry()
        self.pack_start(entry, True, True, 0)
        entry.show()

        setting.bind(setting_key, entry, 'text', Gio.SettingsBindFlags.DEFAULT)


class Network(SectionView):
    def __init__(self, model, alerts):
        SectionView.__init__(self)

        self._model = model
        self.restart_alerts = alerts
        self._jabber_sid = 0
        self._jabber_valid = True
        self._radio_valid = True
        self._jabber_change_handler = None
        self._radio_change_handler = None
        self._network_configuration_reset_handler = None
        self._proxy_settings = {}

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)
        group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        self._radio_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._jabber_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled)
        scrolled.show()

        workspace = Gtk.VBox()
        scrolled.add_with_viewport(workspace)
        workspace.show()

        separator_wireless = Gtk.HSeparator()
        workspace.pack_start(separator_wireless, False, True, 0)
        separator_wireless.show()

        label_wireless = Gtk.Label(label=_('Wireless'))
        label_wireless.set_alignment(0, 0)
        workspace.pack_start(label_wireless, False, True, 0)
        label_wireless.show()
        box_wireless = Gtk.VBox()
        box_wireless.set_border_width(style.DEFAULT_SPACING * 2)
        box_wireless.set_spacing(style.DEFAULT_SPACING)

        radio_info = Gtk.Label(label=
                               _('Turn off the wireless radio to save battery'
                                 ' life'))
        radio_info.set_alignment(0, 0)
        radio_info.set_line_wrap(True)
        radio_info.show()
        box_wireless.pack_start(radio_info, False, True, 0)

        box_radio = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._button = Gtk.CheckButton()
        self._button.set_alignment(0, 0)
        box_radio.pack_start(self._button, False, True, 0)
        self._button.show()

        label_radio = Gtk.Label(label=_('Radio'))
        label_radio.set_alignment(0, 0.5)
        box_radio.pack_start(label_radio, False, True, 0)
        label_radio.show()

        box_wireless.pack_start(box_radio, False, True, 0)
        box_radio.show()

        self._radio_alert = InlineAlert()
        self._radio_alert_box.pack_start(self._radio_alert, False, True, 0)
        box_radio.pack_end(self._radio_alert_box, False, True, 0)
        self._radio_alert_box.show()
        if 'radio' in self.restart_alerts:
            self._radio_alert.props.msg = self.restart_msg
            self._radio_alert.show()

        history_info = Gtk.Label(label=_('Discard network history if you have'
                                         ' trouble connecting to the network'))
        history_info.set_alignment(0, 0)
        history_info.set_line_wrap(True)
        history_info.show()
        box_wireless.pack_start(history_info, False, True, 0)

        box_clear_history = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._clear_history_button = Gtk.Button()
        self._clear_history_button.set_label(_('Discard network history'))
        box_clear_history.pack_start(
            self._clear_history_button, False, True, 0)
        if not self._model.have_networks():
            self._clear_history_button.set_sensitive(False)
        self._clear_history_button.show()
        box_wireless.pack_start(box_clear_history, False, True, 0)
        box_clear_history.show()

        workspace.pack_start(box_wireless, False, True, 0)
        box_wireless.show()

        separator_mesh = Gtk.HSeparator()
        workspace.pack_start(separator_mesh, False, False, 0)
        separator_mesh.show()

        label_mesh = Gtk.Label(label=_('Collaboration'))
        label_mesh.set_alignment(0, 0)
        workspace.pack_start(label_mesh, False, True, 0)
        label_mesh.show()
        box_mesh = Gtk.VBox()
        box_mesh.set_border_width(style.DEFAULT_SPACING * 2)
        box_mesh.set_spacing(style.DEFAULT_SPACING)

        server_info = Gtk.Label(_("The server is the equivalent of what"
                                  " room you are in; people on the same server"
                                  " will be able to see each other, even when"
                                  " they aren't on the same network."))
        server_info.set_alignment(0, 0)
        server_info.set_line_wrap(True)
        box_mesh.pack_start(server_info, False, True, 0)
        server_info.show()

        box_server = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        label_server = Gtk.Label(label=_('Server:'))
        label_server.set_alignment(1, 0.5)
        label_server.modify_fg(Gtk.StateType.NORMAL,
                               style.COLOR_SELECTION_GREY.get_gdk_color())
        box_server.pack_start(label_server, False, True, 0)
        group.add_widget(label_server)
        label_server.show()
        self._entry = Gtk.Entry()
        self._entry.set_alignment(0)
        self._entry.set_size_request(int(Gdk.Screen.width() / 3), -1)
        box_server.pack_start(self._entry, False, True, 0)
        self._entry.show()
        box_mesh.pack_start(box_server, False, True, 0)
        box_server.show()

        self._jabber_alert = InlineAlert()
        label_jabber_error = Gtk.Label()
        group.add_widget(label_jabber_error)
        self._jabber_alert_box.pack_start(label_jabber_error, False, True, 0)
        label_jabber_error.show()
        self._jabber_alert_box.pack_start(self._jabber_alert, False, True, 0)
        box_mesh.pack_end(self._jabber_alert_box, False, True, 0)
        self._jabber_alert_box.show()
        if 'jabber' in self.restart_alerts:
            self._jabber_alert.props.msg = self.restart_msg
            self._jabber_alert.show()

        workspace.pack_start(box_mesh, False, True, 0)
        box_mesh.show()

        separator_proxy = Gtk.HSeparator()
        workspace.pack_start(separator_proxy, False, False, 0)
        separator_proxy.show()

        self._add_proxy_section(workspace)

        self.setup()

    def _add_proxy_section(self, workspace):
        label_proxy = Gtk.Label(_('Proxy'))
        label_proxy.set_alignment(0, 0)
        workspace.pack_start(label_proxy, False, True, 0)
        label_proxy.show()

        box_proxy = Gtk.VBox()
        box_proxy.set_border_width(style.DEFAULT_SPACING * 2)
        box_proxy.set_spacing(style.DEFAULT_SPACING)
        workspace.pack_start(box_proxy, False, True, 0)
        box_proxy.show()

        # GSettings schemas for proxy:
        schemas = ['org.gnome.system.proxy',
                   'org.gnome.system.proxy.http',
                   'org.gnome.system.proxy.https',
                   'org.gnome.system.proxy.ftp',
                   'org.gnome.system.proxy.socks']

        for schema in schemas:
            proxy_setting = Gio.Settings.new(schema)

            # We are not going to apply the settings immediatly.
            # We'll apply them if the user presses the "accept"
            # button, or we'll revert them if the user presses the
            # "cancel" button.
            proxy_setting.delay()

            self._proxy_settings[schema] = proxy_setting

        size_group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        automatic_proxy_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)
        manual_proxy_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)

        option_sets = [('None', 'none', Gtk.VBox()),
                       ('Manual', 'manual', manual_proxy_box),
                       ('Automatic', 'auto', automatic_proxy_box)]

        box_mode = ComboSettingBox(
            _('Method:'), self._proxy_settings['org.gnome.system.proxy'],
            'mode', option_sets, size_group)

        box_proxy.pack_start(box_mode, False, False, 0)
        box_mode.show()

        url_box = StringSettingBox(
            _('Configuration URL:'),
            self._proxy_settings['org.gnome.system.proxy'], 'autoconfig-url',
            size_group)

        automatic_proxy_box.pack_start(url_box, True, True, 0)
        url_box.show()

        wpad_help_text = _('Web Proxy Autodiscovery is used when a'
                           ' Configuration URL is not provided. This is not'
                           ' recommended for untrusted public networks.')
        automatic_proxy_help = Gtk.Label(wpad_help_text)
        automatic_proxy_help.set_alignment(0, 0)
        automatic_proxy_help.set_line_wrap(True)
        automatic_proxy_help.show()
        automatic_proxy_box.pack_start(automatic_proxy_help, True, True, 0)

        box_http = HostPortSettingBox(
            _('HTTP Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.http'], size_group)

        manual_proxy_box.pack_start(box_http, False, False, 0)
        box_http.show()

        auth_contents_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)

        auth_box = OptionalSettingsBox(
            _('Use authentication'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'use-authentication', auth_contents_box)

        manual_proxy_box.pack_start(auth_box, False, False, 0)
        auth_box.show()

        proxy_http_setting = Gio.Settings.new('org.gnome.system.proxy.http')
        proxy_http_setting.delay()

        box_username = StringSettingBox(
            _('Username:'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'authentication-user', size_group)

        auth_contents_box.pack_start(box_username, False, False, 0)
        box_username.show()

        box_password = StringSettingBox(
            _('Password:'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'authentication-password', size_group)

        auth_contents_box.pack_start(box_password, False, False, 0)
        box_password.show()

        box_https = HostPortSettingBox(
            _('HTTPS Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.https'], size_group)

        manual_proxy_box.pack_start(box_https, False, False, 0)
        box_https.show()

        box_ftp = HostPortSettingBox(
            _('FTP Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.ftp'],
            size_group)

        manual_proxy_box.pack_start(box_ftp, False, False, 0)
        box_ftp.show()

        box_socks = HostPortSettingBox(
            _('SOCKS Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.socks'], size_group)

        manual_proxy_box.pack_start(box_socks, False, False, 0)
        box_socks.show()

    def setup(self):
        self._entry.set_text(self._model.get_jabber())
        try:
            radio_state = self._model.get_radio()
        except self._model.ReadError, detail:
            self._radio_alert.props.msg = detail
            self._radio_alert.show()
        else:
            self._button.set_active(radio_state)

        self._jabber_valid = True
        self._radio_valid = True
        self.needs_restart = False
        self._radio_change_handler = self._button.connect(
            'toggled', self.__radio_toggled_cb)
        self._jabber_change_handler = self._entry.connect(
            'changed', self.__jabber_changed_cb)
        self._network_configuration_reset_handler =  \
            self._clear_history_button.connect(
                'clicked', self.__network_configuration_reset_cb)

    def undo(self):
        self._button.disconnect(self._radio_change_handler)
        self._entry.disconnect(self._jabber_change_handler)
        self._model.undo()
        self._jabber_alert.hide()
        self._radio_alert.hide()
        for setting in self._proxy_settings.values():
            setting.revert()

    def apply(self):
        for setting in self._proxy_settings.values():
            setting.apply()

    def _validate(self):
        if self._jabber_valid and self._radio_valid:
            self.props.is_valid = True
        else:
            self.props.is_valid = False

    def __radio_toggled_cb(self, widget, data=None):
        radio_state = widget.get_active()
        try:
            self._model.set_radio(radio_state)
        except self._model.ReadError, detail:
            self._radio_alert.props.msg = detail
            self._radio_valid = False
        else:
            self._radio_valid = True
            if self._model.have_networks():
                self._clear_history_button.set_sensitive(True)

        self._validate()
        return False

    def __jabber_changed_cb(self, widget, data=None):
        if self._jabber_sid:
            GObject.source_remove(self._jabber_sid)
        self._jabber_sid = GObject.timeout_add(_APPLY_TIMEOUT,
                                               self.__jabber_timeout_cb,
                                               widget)

    def __jabber_timeout_cb(self, widget):
        self._jabber_sid = 0
        if widget.get_text() == self._model.get_jabber:
            return
        try:
            self._model.set_jabber(widget.get_text())
        except self._model.ReadError, detail:
            self._jabber_alert.props.msg = detail
            self._jabber_valid = False
            self._jabber_alert.show()
            self.restart_alerts.append('jabber')
        else:
            self._jabber_valid = True
            self._jabber_alert.hide()

        self._validate()
        return False

    def __network_configuration_reset_cb(self, widget):
        # FIXME: takes effect immediately, not after CP is closed with
        # confirmation button
        self._model.clear_networks()
        if not self._model.have_networks():
            self._clear_history_button.set_sensitive(False)
