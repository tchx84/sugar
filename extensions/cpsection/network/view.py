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
import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Pango

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert

from jarabe.model.network import HiddenNetworkManager

CLASS = 'Network'
ICON = 'module-network'
TITLE = _('Network')

_APPLY_TIMEOUT = 3000

DEFAULT_PROXY_PORT = 8080


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

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    """
    Container for sets of different settings selected by a top-level
    setting.

    Renders the top level setting as a ComboBox.  Only the currently
    active set is shown on screen.
    """
    def __init__(self, name, option_sets, size_group=None):
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)

        setting_box = SettingBox(name, size_group)
        self.pack_start(setting_box, False, False, 0)
        setting_box.show()

        model = Gtk.ListStore(str, str, object, object)
        self.combo_box = Gtk.ComboBox(model=model)
        self.combo_box.connect('changed', self.__combo_changed_cb)
        setting_box.pack_start(self.combo_box, True, True, 0)
        self.combo_box.show()

        cell_renderer = Gtk.CellRendererText()
        cell_renderer.props.ellipsize = Pango.EllipsizeMode.MIDDLE
        cell_renderer.props.ellipsize_set = True
        self.combo_box.pack_start(cell_renderer, True)
        self.combo_box.add_attribute(cell_renderer, 'text', 0)
        self.combo_box.props.id_column = 1

        self._settings_box = Gtk.VBox()
        self._settings_box.show()
        self.pack_start(self._settings_box, False, False, 0)

        for optset in option_sets:
            model.append(optset)

    def __combo_changed_cb(self, combobox):
        self.emit('changed')


class ProxyModeCombo(ComboSettingBox):

    __gsignals__ = {
        'profile-selected': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
    }

    def __init__(self, name, setting, setting_key,
                 option_sets, size_group=None):
        ComboSettingBox.__init__(self, name, option_sets, size_group)

        setting.bind(setting_key, self.combo_box, 'active-id',
                     Gio.SettingsBindFlags.DEFAULT)

        self.connect('changed', self.__combo_changed_cb)
        # display the box with the initial value
        self.__combo_changed_cb(self)

    def __combo_changed_cb(self, combo_setting_box):
        giter = combo_setting_box.combo_box.get_active_iter()
        new_box = combo_setting_box.combo_box.get_model().get(giter, 2)[0]
        current_box = self._settings_box.get_children()
        if current_box:
            self._settings_box.remove(current_box[0])

        self._settings_box.add(new_box)
        new_box.show()

        profile = combo_setting_box.combo_box.get_model().get(giter, 3)[0]
        self.emit('profile-selected', profile)

    def set_active(self, active):
        self.combo_box.set_active(active)
        giter = self.combo_box.get_active_iter()
        profile = self.combo_box.get_model().get(giter, 3)[0]
        self.emit('profile-selected', profile)


class OptionalSettingsBox(Gtk.VBox):
    """
    Container for settings (de)activated by a top-level setting.

    Renders the top level setting as a CheckButton. The settings are only
    shown on screen if the top-level setting is enabled.
    """
    def __init__(self, name, setting, setting_key, contents_box):
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)

        self._check_button = Gtk.CheckButton()
        self._check_button.props.label = name
        self._check_button.connect('toggled', self.__button_toggled_cb,
                                   contents_box)
        self._check_button.show()
        self.pack_start(self._check_button, True, True, 0)
        self.pack_start(contents_box, False, False, 0)

        setting.bind(setting_key, self._check_button, 'active',
                     Gio.SettingsBindFlags.NO_SENSITIVITY)

    def __button_toggled_cb(self, check_button, contents_box):
        contents_box.set_visible(check_button.get_active())

    def set_active(self, active):
        self._check_button.set_active(active)

    def set_checkbox_visible(self, visible):
        if visible:
            self._check_button.show()
        else:
            self._check_button.hide()


class HostPortSettingBox(SettingBox):
    """
    A configuration line for a combined host name and port setting.
    """
    def __init__(self, name, setting, size_group=None):
        SettingBox.__init__(self, name, size_group)

        self._host_entry = Gtk.Entry()
        self.pack_start(self._host_entry, True, True, 0)
        self._host_entry.show()

        setting.bind('host', self._host_entry, 'text',
                     Gio.SettingsBindFlags.NO_SENSITIVITY)

        # port number 0 means n/a
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10)
        self._port_spinbutton = Gtk.SpinButton(adjustment=adjustment,
                                               climb_rate=0.1)
        self.pack_start(self._port_spinbutton, False, False, 0)
        self._port_spinbutton.show()

        setting.bind('port', self._port_spinbutton, 'value',
                     Gio.SettingsBindFlags.NO_SENSITIVITY)

    def set_host(self, host):
        self._host_entry.set_text(host)

    def set_port(self, port):
        self._port_spinbutton.set_value(port)


class StringSettingBox(SettingBox):
    """
    A configuration line for a string setting.
    """
    def __init__(self, name, setting, setting_key, size_group=None,
                 password_field=False):
        SettingBox.__init__(self, name, size_group)

        self._entry = Gtk.Entry()
        self.pack_start(self._entry, True, True, 0)
        self._entry.show()
        if password_field:
            self._entry.set_visibility(False)

        setting.bind(setting_key, self._entry, 'text',
                     Gio.SettingsBindFlags.NO_SENSITIVITY)

    def clear(self):
        self._entry.set_text('')


class StringBox(SettingBox):
    """
    A configuration line for a string not ussing gsettings to store it.
    """
    def __init__(self, name, size_group=None, password_field=False):
        SettingBox.__init__(self, name, size_group)

        self._entry = Gtk.Entry()
        self.pack_start(self._entry, True, True, 0)
        self._entry.show()
        if password_field:
            self._entry.set_visibility(False)

    def clear(self):
        self._entry.set_text('')

    def set_text(self, text):
        self._entry.set_text(text)

    def get_text(self):
        return self._entry.get_text()


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

        # read connectivity profiles if available
        self._connectivity_profiles = self._model.get_connectivity_profiles()

        self._hidden_conn_manager = HiddenNetworkManager(
            self._connectivity_profiles)
        if self._hidden_conn_manager.enabled:
            self._add_hidden_ssid_section(workspace)

        self._add_proxy_section(workspace)

        self.setup()

    def _add_hidden_ssid_section(self, workspace):
        separator_hidden_network = Gtk.HSeparator()
        workspace.pack_start(separator_hidden_network, False, False, 0)
        separator_hidden_network.show()

        label_hidden_network = Gtk.Label(_('Hidden Networks'))
        label_hidden_network.set_alignment(0, 0)
        workspace.pack_start(label_hidden_network, False, False, 0)
        label_hidden_network.show()
        box_hidden_network = Gtk.VBox()
        box_hidden_network.set_border_width(style.DEFAULT_SPACING * 2)
        box_hidden_network.set_spacing(style.DEFAULT_SPACING)

        size_group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        hidden_network_name_box = Gtk.VBox()
        option_sets = [('No security', '', hidden_network_name_box, None)]
        self._entries_properties = {}
        name_box = SettingBox(_("Name"), size_group)
        name_box.show()
        self._hidden_network_name_entry = Gtk.Entry()
        name_box.pack_start(self._hidden_network_name_entry, False, False, 0)
        self._hidden_network_name_entry.show()
        hidden_network_name_box.pack_start(name_box, False, False, 0)
        self._entries_properties[self._hidden_network_name_entry] = \
            '802-11-wireless.ssid'

        if len(self._hidden_conn_manager.network_profiles) > 0:

            # load the network profiles in the option_sets
            network_profiles_index = {}
            # map to relate the entry to the property to edit
            for network_profile in self._hidden_conn_manager.network_profiles:
                box = Gtk.VBox()

                # look for all the properties in the network profile
                # configured as REQUEST
                # first sort the properties (username, password, other)
                # and set better labels
                # the names of the fields are from:
                # https://projects.gnome.org/NetworkManager/developers/api/09/
                #                                            ref-settings.html
                filters = [('802-1x.identity',
                            '802-11-wireless-security.leap-username'),
                           ('802-1x.password',
                            '802-11-wireless-security.leap-password'),
                           None]
                labels = [_('Username:'), _('Password:')]
                count = 0
                for property_filter in filters:
                    for key in network_profile.keys():
                        if network_profile[key].upper() == 'REQUEST':
                            field_ok = True
                            if property_filter is not None:
                                if key not in property_filter:
                                    field_ok = False
                            else:
                                if key in filters[0] or key in filters[1]:
                                    field_ok = False
                            if field_ok:
                                if count < len(labels):
                                    label = labels[count]
                                else:
                                    label = key
                                setting_box = SettingBox(label, size_group)
                                setting_box.set_border_width(
                                    style.DEFAULT_SPACING)
                                setting_box.set_spacing(style.DEFAULT_SPACING)
                                entry = Gtk.Entry()
                                if 'password' in key:
                                    entry.set_visibility(False)
                                setting_box.pack_start(entry, True, True, 0)
                                box.pack_start(setting_box, True, True, 0)
                                self._entries_properties[entry] = key
                    count = count + 1
                box.show_all()

                option_sets.append((network_profile['title'], '',
                                    box, network_profile))
                index = len(option_sets) - 1
                network_profiles_index[network_profile['title']] = index

        self._combo_setting_box = ComboSettingBox(_('Mode:'), option_sets,
                                                  size_group)

        box_hidden_network.pack_start(self._combo_setting_box, False, False,
                                      0)
        self._combo_setting_box.show()

        self._hidden_network_params_box = Gtk.VBox()
        self._hidden_network_params_box.show()
        box_hidden_network.pack_start(self._hidden_network_params_box, False,
                                      False, 0)

        # _select_hidden_network_profile need the box already created
        self._combo_setting_box.connect('changed',
                                        self._select_hidden_network_profile)

        # show the widgets for the configured mode
        self._init_hidden_network_mode()

        btn_box = Gtk.HBox()
        create_connection_btn = Gtk.Button('Connect')
        create_connection_btn.connect('clicked', self.__connect_hidden_net_cb)
        btn_box.pack_start(create_connection_btn, False, False, 0)
        box_hidden_network.pack_start(btn_box, False, False, 0)
        btn_box.show_all()

        workspace.pack_start(box_hidden_network, False, False, 0)
        box_hidden_network.show()

    def _init_hidden_network_mode(self):
        logging.error('_init_hidden_network_mode selected_ssid = %s',
                      self._hidden_conn_manager.selected_ssid)
        logging.error('_init_hidden_network_mode selected_profile = %s',
                      self._hidden_conn_manager.selected_profile)
        if self._hidden_conn_manager.selected_ssid:
            self._combo_setting_box.combo_box.set_active(0)
            self._hidden_network_name_entry.set_text(
                self._hidden_conn_manager.selected_ssid)

        elif self._hidden_conn_manager.selected_profile:
            combo_model = self._combo_setting_box.combo_box.get_model()
            combo_iter = combo_model.get_iter_first()
            posi = 0
            while combo_iter is not None:
                logging.error('combo posi %d value = %s', posi,
                              combo_model.get(combo_iter, 0)[0])
                if combo_model.get(combo_iter, 0)[0] == \
                        self._hidden_conn_manager.selected_profile['title']:
                    self._combo_setting_box.combo_box.set_active(posi)
                combo_iter = combo_model.iter_next(combo_iter)
                posi += 1
        else:
            # if nothing configured
            self._combo_setting_box.combo_box.set_active(0)

    def _select_hidden_network_profile(self, combo_setting_box):
        giter = combo_setting_box.combo_box.get_active_iter()
        new_box = combo_setting_box.combo_box.get_model().get(giter, 2)[0]
        current_box = self._hidden_network_params_box.get_children()
        if current_box:
            self._hidden_network_params_box.remove(current_box[0])

        self._hidden_network_params_box.add(new_box)
        new_box.show()
        self._hidden_conn_manager.selected_profile = \
            combo_setting_box.combo_box.get_model().get(giter, 3)[0]

        # load the values previously stored
        if self._hidden_conn_manager.selected_profile is not None:
            stored_parameters = self._hidden_conn_manager.stored_parameters[
                self._hidden_conn_manager.selected_profile['title']]
            for entry in self._entries_properties.keys():
                property_name = self._entries_properties[entry]
                if property_name in stored_parameters.keys():
                    entry.set_text(stored_parameters[property_name])
        else:
            for entry in self._entries_properties.keys():
                entry.set_text('')

    def __connect_hidden_net_cb(self, button):

        profile = self._hidden_conn_manager.selected_profile
        if profile is None:
            if self._hidden_network_name_entry.get_text() != '':
                self._hidden_conn_manager.create_and_connect_by_ssid(
                    self._hidden_network_name_entry.get_text())
        else:

            # get the values from all the entries
            current_box = self._hidden_network_params_box.get_children()[0]
            requested_parameters = []
            for child in current_box.get_children():
                # child is the SettingBox
                entry = child.get_children()[1]
                property_name = self._entries_properties[entry]
                logging.error('property %s value %s', property_name,
                              entry.get_text())
                profile[property_name] = entry.get_text()
                # add in a list to save the requested parameters
                requested_parameters.append(property_name)

            logging.error('profile %s',
                          self._hidden_conn_manager.selected_profile)
            self._hidden_conn_manager.store_requested_parameters(
                requested_parameters)
            self._hidden_conn_manager.create_and_connect_by_profile()

    def _add_proxy_section(self, workspace):
        separator_hidden_network = Gtk.HSeparator()
        workspace.pack_start(separator_hidden_network, False, False, 0)
        separator_hidden_network.show()

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

        option_sets = [('None', 'none', Gtk.VBox(), None),
                       ('Manual', 'manual', manual_proxy_box, None),
                       ('Automatic', 'auto', automatic_proxy_box, None)]

        # get the list of connectivity profiles of type "proxy"
        proxy_profiles = []
        logging.error('profiles %s', self._connectivity_profiles)
        for profile_key in self._connectivity_profiles:
            profile = self._connectivity_profiles[profile_key]
            if profile['type'] == 'proxy':
                proxy_profiles.append(profile)

        # load the proxy profiles in the option_sets
        proxy_profiles_index = {}
        for proxy_profile in proxy_profiles:
            box = Gtk.VBox()
            if proxy_profile['mode'] == 'manual':
                box = manual_proxy_box
            if proxy_profile['mode'] == 'auto':
                box = automatic_proxy_box
            option_sets.append((proxy_profile['title'], proxy_profile['mode'],
                                box, proxy_profile))
            index = len(option_sets) - 1
            proxy_profiles_index[proxy_profile['title']] = index

        box_mode = ProxyModeCombo(
            _('Method:'), self._proxy_settings['org.gnome.system.proxy'],
            'mode', option_sets, size_group)
        box_mode.connect('profile-selected', self._apply_proxy_profile)

        box_proxy.pack_start(box_mode, False, False, 0)
        box_mode.show()

        self.url_box = StringSettingBox(
            _('Configuration URL:'),
            self._proxy_settings['org.gnome.system.proxy'], 'autoconfig-url',
            size_group)

        automatic_proxy_box.pack_start(self.url_box, True, True, 0)
        self.url_box.show()

        wpad_help_text = _('Web Proxy Autodiscovery is used when a'
                           ' Configuration URL is not provided. This is not'
                           ' recommended for untrusted public networks.')
        automatic_proxy_help = Gtk.Label(wpad_help_text)
        automatic_proxy_help.set_alignment(0, 0)
        automatic_proxy_help.set_line_wrap(True)
        automatic_proxy_help.show()
        automatic_proxy_box.pack_start(automatic_proxy_help, True, True, 0)

        self.box_http = HostPortSettingBox(
            _('HTTP Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.http'], size_group)

        manual_proxy_box.pack_start(self.box_http, False, False, 0)
        self.box_http.show()

        auth_contents_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)

        self.auth_box = OptionalSettingsBox(
            _('Use authentication'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'use-authentication', auth_contents_box)

        manual_proxy_box.pack_start(self.auth_box, False, False, 0)
        self.auth_box.show()

        proxy_http_setting = Gio.Settings.new('org.gnome.system.proxy.http')
        proxy_http_setting.delay()

        self.box_username = StringSettingBox(
            _('Username:'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'authentication-user', size_group)

        auth_contents_box.pack_start(self.box_username, False, False, 0)
        self.box_username.show()

        self.box_password = StringSettingBox(
            _('Password:'),
            self._proxy_settings['org.gnome.system.proxy.http'],
            'authentication-password', size_group, password_field=True)

        auth_contents_box.pack_start(self.box_password, False, False, 0)
        self.box_password.show()

        self.box_https = HostPortSettingBox(
            _('HTTPS Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.https'], size_group)

        manual_proxy_box.pack_start(self.box_https, False, False, 0)
        self.box_https.show()

        self.box_ftp = HostPortSettingBox(
            _('FTP Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.ftp'],
            size_group)

        manual_proxy_box.pack_start(self.box_ftp, False, False, 0)
        self.box_ftp.show()

        self.box_socks = HostPortSettingBox(
            _('SOCKS Proxy:'),
            self._proxy_settings['org.gnome.system.proxy.socks'], size_group)

        manual_proxy_box.pack_start(self.box_socks, False, False, 0)
        self.box_socks.show()

        # cntlm fields, hidden by default
        self.box_cntlm_user = StringBox(_('Username:'), size_group)
        manual_proxy_box.pack_start(self.box_cntlm_user, False, False, 0)

        self.box_cntlm_password = StringBox(_('Password:'), size_group, True)
        manual_proxy_box.pack_start(self.box_cntlm_password, False, False, 0)

        self.box_cntlm_host = StringBox(_('Host:'), size_group)
        manual_proxy_box.pack_start(self.box_cntlm_host, False, False, 0)

        self.box_cntlm_port = StringBox(_('Port:'), size_group)
        manual_proxy_box.pack_start(self.box_cntlm_port, False, False, 0)

        self.box_cntlm_domain = StringBox(_('Domain:'), size_group)
        manual_proxy_box.pack_start(self.box_cntlm_domain, False, False, 0)

        # if a profile was selected update the combo value
        self._proxy_profile_name = self._model.get_proxy_profile_name()
        self._proxy_profile_type = self._model.get_proxy_profile_type()
        logging.error('Proxy Profile selected %s', self._proxy_profile_name)
        if self._proxy_profile_name is not None and \
                self._proxy_profile_name != '':
            if self._proxy_profile_name in proxy_profiles_index:
                index = proxy_profiles_index[self._proxy_profile_name]
                logging.error('Profile selected index %s', index)
                box_mode.set_active(index)

    def _apply_proxy_profile(self, widget, profile):
        if profile is None:
            self._proxy_profile_name = ''
            self._proxy_profile_type = ''
            # show all the entrys and set default values
            self.auth_box.set_active(False)
            self.auth_box.set_checkbox_visible(True)
            self.auth_box.show()
            self.box_username.clear()
            self.box_username.show()
            self.box_password.clear()
            self.box_password.show()

            for box in (self.box_cntlm_user, self.box_cntlm_password,
                        self.box_cntlm_host, self.box_cntlm_port,
                        self.box_cntlm_domain):
                box.hide()

            for box in (self.box_http, self.box_https, self.box_ftp,
                        self.box_socks):
                box.show()
                box.set_host('')
                box.set_port(DEFAULT_PROXY_PORT)
            return

        self._proxy_profile_name = profile['title']
        self._proxy_profile_type = ''
        if 'proxy_type' in profile:
            self._proxy_profile_type = profile['proxy_type']

        if self._proxy_profile_type == 'cntlm':
            (user, password, domain, host,
             port) = self._model.get_cntlm_parameters()
            self.box_cntlm_user.set_text(user)
            self.box_cntlm_password.set_text(password)
            self.box_cntlm_domain.set_text(domain)
            self.box_cntlm_host.set_text(host)
            self.box_cntlm_port.set_text(port)

        # load the configuration in the profile
        self.auth_box.set_active(self._model.parameter_as_boolean(
            profile, 'use_authentication'))
        hostname = ''
        if 'http_proxy.host' in profile:
            if profile['http_proxy.host'] != 'REQUEST':
                hostname = profile['http_proxy.host']
        self.box_http.set_host(hostname)

        port = DEFAULT_PROXY_PORT
        if 'http_proxy.port' in profile:
            try:
                port = int(profile['http_proxy.port'])
            except:
                pass
        self.box_http.set_port(port)

        # if is configured use the same ip/port for all the services
        if self._model.parameter_as_boolean(profile, 'use_same_proxy'):
            for box in (self.box_https, self.box_ftp, self.box_socks):
                box.set_host(hostname)
                box.set_port(port)
                box.hide()
        else:
            service_box = {'https': self.box_https,
                           'ftp': self.box_ftp,
                           'socks': self.box_socks}

            for service in service_box.keys():
                parameter = '%s_proxy.host' % service
                hostname = ''
                if parameter in profile:
                    hostname = profile[parameter]

                parameter = '%s_proxy.port' % service
                port = DEFAULT_PROXY_PORT
                if parameter in profile:
                    try:
                        port = int(profile[parameter])
                    except:
                        pass
                box = service_box[service]
                box.set_host(hostname)
                box.set_port(port)
                box.hide()

        if 'use_authentication' in profile:
            self.auth_box.set_checkbox_visible(False)

        # only show the fields where the value is REQUEST
        parameter_widget = {'authentication_user': self.box_username,
                            'authentication_password': self.box_password,
                            'http_proxy.host': self.box_http,
                            'cntlm.user': self.box_cntlm_user,
                            'cntlm.password': self.box_cntlm_password,
                            'cntlm.host': self.box_cntlm_host,
                            'cntlm.port': self.box_cntlm_port,
                            'cntlm.domain': self.box_cntlm_domain}

        for parameter in parameter_widget.keys():
            visible = True
            if 'cntlm' in parameter:
                visible = False
            if parameter in profile:
                visible = (profile[parameter].upper() == 'REQUEST')
            if visible:
                parameter_widget[parameter].show_all()
            else:
                parameter_widget[parameter].hide()

        #ignore_hosts = schoolserver,server,localhost,127.0.0.0/8

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

        self._model.set_proxy_profile_type(self._proxy_profile_type)
        # set cntlm values
        if self._proxy_profile_type == 'cntlm':
            user = self.box_cntlm_user.get_text()
            password = self.box_cntlm_password.get_text()
            domain = self.box_cntlm_domain.get_text()
            host = self.box_cntlm_host.get_text()
            port = self.box_cntlm_port.get_text()
            self._model.apply_cntlm_configs(user, password, domain, host, port)

        self._model.set_proxy_profile_name(self._proxy_profile_name)

        if self._model.get_radio():
            if self._hidden_conn_manager.enabled:
                self.__connect_hidden_net_cb(None)

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
