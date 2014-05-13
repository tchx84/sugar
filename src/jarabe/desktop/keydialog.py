# Copyright (C) 2006-2007 Red Hat, Inc.
# Copyright (C) 2009 One Laptop per Child
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

import hashlib
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk

import dbus

import os
import shutil

from sugar3 import env
from sugar3.graphics.icon import Icon
from sugar3.graphics import style
from jarabe.model import network
from jarabe.journal.objectchooser import ObjectChooser

IW_AUTH_ALG_OPEN_SYSTEM = 'open'
IW_AUTH_ALG_SHARED_KEY = 'shared'

WEP_PASSPHRASE = 1
WEP_HEX = 2
WEP_ASCII = 3

SETTING_TYPE_STRING = 1
SETTING_TYPE_LIST = 2
SETTING_TYPE_CHOOSER = 3


def string_is_hex(key):
    is_hex = True
    for c in key:
        if not 'a' <= c.lower() <= 'f' and not '0' <= c <= '9':
            is_hex = False
    return is_hex


def string_is_ascii(string):
    try:
        string.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False


def string_to_hex(passphrase):
    key = ''
    for c in passphrase:
        key += '%02x' % ord(c)
    return key


def hash_passphrase(passphrase):
    # passphrase must have a length of 64
    if len(passphrase) > 64:
        passphrase = passphrase[:64]
    elif len(passphrase) < 64:
        while len(passphrase) < 64:
            passphrase += passphrase[:64 - len(passphrase)]
    passphrase = hashlib.md5(passphrase).digest()
    return string_to_hex(passphrase)[:26]


class CanceledKeyRequestError(dbus.DBusException):
    def __init__(self):
        dbus.DBusException.__init__(self)
        self._dbus_error_name = network.NM_SETTINGS_IFACE + '.CanceledError'


class NetworkParameters(Gtk.HBox):
    def __init__(self, auth_param):
        Gtk.HBox.__init__(self, homogeneous=True)
        self._key = auth_param._key_name
        self._label = Gtk.Label(_(auth_param._key_label))
        self._key_type = auth_param._key_type
        self._auth_param = auth_param

        self.pack_start(self._label, True, True, 0)
        self._label.show()

        if self._is_entry():
            self._entry = Gtk.Entry()
            if 'password' in self._key:
                self._entry.set_visibility(False)
            self.pack_start(self._entry, True, True, 0)
            self._entry.show()
        elif self._is_liststore():
            self._option_store = Gtk.ListStore(str, str)
            for option in auth_param._options:
                self._option_store.append(option)

            self._entry = auth_param._options[0][1]
            self._option_combo = Gtk.ComboBox(model=self._option_store)
            cell = Gtk.CellRendererText()
            self._option_combo.pack_start(cell, True)
            self._option_combo.add_attribute(cell, 'text', 0)
            self._option_combo.set_active(0)
            self._option_combo.connect('changed',
                                       self._option_combo_changed_cb)
            self.pack_start(self._option_combo, True, True, 0)
            self.show()
            self._option_combo.show()
        elif self._is_chooser():
            self._chooser_button = Gtk.Button(_('Choose..'))
            self._chooser_button.connect('clicked', self._object_chooser_cb)
            self.pack_start(self._chooser_button, True, True, 0)
            self._chooser_button.show()
            self._entry = ''

    def _is_entry(self):
        return (not self._is_chooser()) and \
               (len(self._auth_param._options) == 0)

    def _is_liststore(self):
        return (not self._is_chooser()) and \
               (len(self._auth_param._options) > 0)

    def _is_chooser(self):
        return self._key_type == SETTING_TYPE_CHOOSER

    def _object_chooser_cb(self, chooser_button):
        self._want_document = True
        self._show_picker_cb()

    def _show_picker_cb(self):
        if not self._want_document:
            return
        chooser = ObjectChooser()

        try:
            result = chooser.run()
            if result == Gtk.ResponseType.ACCEPT:
                jobject = chooser.get_selected_object()
                if jobject and jobject.file_path:
                    file_basename = os.path.basename(
                        jobject._metadata._properties['title'])
                    self._chooser_button.set_label(file_basename)

                    profile_path = env.get_profile_path()
                    self._entry = os.path.join(profile_path, file_basename)

                    # Remove (older) file, if it exists.
                    if os.path.exists(self._entry):
                        os.remove(self._entry)

                    # Copy the file.
                    shutil.copy2(jobject.file_path, self._entry)

        finally:
            chooser.destroy()
            del chooser

    def _option_combo_changed_cb(self, widget):
        it = self._option_combo.get_active_iter()
        (value, ) = self._option_store.get(it, 1)
        self._entry = value

    def _get_key(self):
        return self._key

    def _get_value(self):
        if self._is_entry():
            return self._entry.get_text()
        elif self._is_liststore():
            return self._entry
        elif self._is_chooser():
            if len(self._entry) > 0:
                return dbus.ByteArray('file://' + self._entry + '\0')
            else:
                return self._entry


class KeyValuesDialog(Gtk.Dialog):
    def __init__(self, auth_lists, final_callback, settings):
        # This must not be "modal", else the "chooser" widgets won't
        # accept anything !!
        Gtk.Dialog.__init__(self)
        self.set_title(_('Wireless Parameters required'))

        self._spacing_between_children_widgets = 5
        self._auth_lists = auth_lists
        self._final_callback = final_callback
        self._settings = settings

        label = Gtk.Label(_("Please enter parameters\n"))
        self.vbox.set_spacing(self._spacing_between_children_widgets)
        self.vbox.pack_start(label, True, True, 0)

        self._auth_type_store = Gtk.ListStore(str, str)
        for auth_list in self._auth_lists:
            self._auth_type_store.append([auth_list._auth_label,
                                          auth_list._auth_type])

        self._auth_type_combo = Gtk.ComboBox(model=self._auth_type_store)
        cell = Gtk.CellRendererText()
        self._auth_type_combo.pack_start(cell, True)
        self._auth_type_combo.add_attribute(cell, 'text', 0)
        self._auth_type_combo.set_active(0)
        self._auth_type_combo.connect('changed',
                                      self._auth_type_combo_changed_cb)
        self._auth_type_box = Gtk.HBox(homogeneous=True)
        self._auth_label = Gtk.Label(_('Authentication'))
        self._auth_type_box.pack_start(self._auth_label, True, True, 0)
        self._auth_type_box.pack_start(self._auth_type_combo,
                                       True, True, 0)
        self.vbox.pack_start(self._auth_type_box, True, True, 0)
        self._auth_label.show()
        self._auth_type_combo.show()

        button = Gtk.Button()
        button.set_image(Icon(icon_name='dialog-cancel'))
        button.set_label(_('Cancel'))
        self.add_action_widget(button, Gtk.ResponseType.CANCEL)
        button = Gtk.Button()
        button.set_image(Icon(icon_name='dialog-ok'))
        button.set_label(_('Ok'))
        self.add_action_widget(button, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        self.connect('response', self._fetch_values)

        auth_type = self._auth_lists[0]._auth_type
        self._selected_auth_list = self._select_auth_list(auth_type)
        self._add_key_value('eap', auth_type)
        self._add_container_box()

    def _auth_type_combo_changed_cb(self, widget):
        it = self._auth_type_combo.get_active_iter()
        (auth_type, ) = self._auth_type_store.get(it, 1)
        self._selected_auth_list = self._select_auth_list(auth_type)
        self._add_key_value('eap', auth_type)
        self._reset()

    def _select_auth_list(self, auth_type):
        for auth_list in self._auth_lists:
            if auth_list._params_list[0]._options[0][1] == auth_type:
                return auth_list

    def _populate_auth_params(self, auth_list):
        for auth_param in auth_list._params_list[1:]:
            obj = NetworkParameters(auth_param)
            self._key_values_box.pack_start(obj, True, True, 0)
            obj.show()

    def _reset(self):
        self.vbox.remove(self._key_values_box)
        self._add_container_box()

    def _add_container_box(self):
        self._key_values_box = Gtk.VBox(
            spacing=self._spacing_between_children_widgets)
        self.vbox.pack_start(self._key_values_box, True, True, 0)
        self._key_values_box.show()
        self._populate_auth_params(self._selected_auth_list)

    def _remove_all_params(self):
        self._key_values_box.remove_all()

    def _fetch_values(self, key_dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            for child in self._key_values_box.get_children():
                key = child._get_key()
                value = child._get_value()
                self._add_key_value(key, value)
            self._final_callback(self._settings,
                                 self._selected_auth_list)
        key_dialog.destroy()

    def _add_key_value(self, key, value):
        for auth_param in self._selected_auth_list._params_list:
            if auth_param._key_name == key:
                if (auth_param._key_type == SETTING_TYPE_STRING) or \
                   (auth_param._key_type == SETTING_TYPE_CHOOSER):
                    auth_param._value = value
                elif auth_param._key_type == SETTING_TYPE_LIST:
                    values = []
                    values.append(value)
                    auth_param._value = values


class KeyDialog(Gtk.Dialog):
    def __init__(self, ssid, flags, wpa_flags, rsn_flags, dev_caps, response):
        Gtk.Dialog.__init__(self, flags=Gtk.DialogFlags.MODAL)
        self.set_title('Wireless Key Required')

        self._response = response
        self._entry = None
        self._ssid = ssid
        self._flags = flags
        self._wpa_flags = wpa_flags
        self._rsn_flags = rsn_flags
        self._dev_caps = dev_caps

        display_name = network.ssid_to_display_name(ssid)
        label = Gtk.Label(label=_("A wireless encryption key is required for\n"
                                  " the wireless network '%s'.")
                          % (display_name, ))
        self.vbox.pack_start(label, True, True, 0)

        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

    def add_key_entry(self):
        self._entry = Gtk.Entry()
        self._entry.connect('changed', self._update_response_sensitivity)
        self._entry.connect('activate', self._entry_activate_cb)
        self.vbox.pack_start(self._entry, True, True, 0)
        self.vbox.set_spacing(6)
        self.vbox.show_all()

        self._update_response_sensitivity()
        self._entry.grab_focus()

    def _entry_activate_cb(self, entry):
        self.response(Gtk.ResponseType.OK)

    def create_security(self):
        raise NotImplementedError

    def get_response_object(self):
        return self._response


class WEPKeyDialog(KeyDialog):
    def __init__(self, ssid, flags, wpa_flags, rsn_flags, dev_caps, response):
        KeyDialog.__init__(self, ssid, flags, wpa_flags, rsn_flags,
                           dev_caps, response)

        # WEP key type
        self.key_store = Gtk.ListStore(str, int)
        self.key_store.append(['Passphrase (128-bit)', WEP_PASSPHRASE])
        self.key_store.append(['Hex (40/128-bit)', WEP_HEX])
        self.key_store.append(['ASCII (40/128-bit)', WEP_ASCII])

        self.key_combo = Gtk.ComboBox(model=self.key_store)
        cell = Gtk.CellRendererText()
        self.key_combo.pack_start(cell, True)
        self.key_combo.add_attribute(cell, 'text', 0)
        self.key_combo.set_active(0)
        self.key_combo.connect('changed', self._key_combo_changed_cb)

        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_('Key Type:')), True, True, 0)
        hbox.pack_start(self.key_combo, True, True, 0)
        hbox.show_all()
        self.vbox.pack_start(hbox, True, True, 0)

        # Key entry field
        self.add_key_entry()

        # WEP authentication mode
        self.auth_store = Gtk.ListStore(str, str)
        self.auth_store.append(['Open System', IW_AUTH_ALG_OPEN_SYSTEM])
        self.auth_store.append(['Shared Key', IW_AUTH_ALG_SHARED_KEY])

        self.auth_combo = Gtk.ComboBox(model=self.auth_store)
        cell = Gtk.CellRendererText()
        self.auth_combo.pack_start(cell, True)
        self.auth_combo.add_attribute(cell, 'text', 0)
        self.auth_combo.set_active(0)

        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_('Authentication Type:')), True, True, 0)
        hbox.pack_start(self.auth_combo, True, True, 0)
        hbox.show_all()

        self.vbox.pack_start(hbox, True, True, 0)

    def _key_combo_changed_cb(self, widget):
        self._update_response_sensitivity()

    def _get_security(self):
        key = self._entry.get_text()

        it = self.key_combo.get_active_iter()
        (key_type, ) = self.key_store.get(it, 1)

        if key_type == WEP_PASSPHRASE:
            key = hash_passphrase(key)
        elif key_type == WEP_ASCII:
            key = string_to_hex(key)

        it = self.auth_combo.get_active_iter()
        (auth_alg, ) = self.auth_store.get(it, 1)

        return (key, auth_alg)

    def print_security(self):
        (key, auth_alg) = self._get_security()
        print 'Key: %s' % key
        print 'Auth: %d' % auth_alg

    def create_security(self):
        (key, auth_alg) = self._get_security()
        wsec = {'wep-key0': key, 'auth-alg': auth_alg}
        return {'802-11-wireless-security': wsec}

    def _update_response_sensitivity(self, ignored=None):
        key = self._entry.get_text()
        it = self.key_combo.get_active_iter()
        (key_type, ) = self.key_store.get(it, 1)

        valid = False
        if key_type == WEP_PASSPHRASE:
            # As the md5 passphrase can be of any length and has no indicator,
            # we cannot check for the validity of the input.
            if len(key) > 0:
                valid = True
        elif key_type == WEP_ASCII:
            if len(key) == 5 or len(key) == 13:
                valid = string_is_ascii(key)
        elif key_type == WEP_HEX:
            if len(key) == 10 or len(key) == 26:
                valid = string_is_hex(key)

        self.set_response_sensitive(Gtk.ResponseType.OK, valid)


class WPAPersonalKeyDialog(KeyDialog):
    def __init__(self, ssid, flags, wpa_flags, rsn_flags, dev_caps, response):
        KeyDialog.__init__(self, ssid, flags, wpa_flags, rsn_flags,
                           dev_caps, response)
        self.add_key_entry()

        self.store = Gtk.ListStore(str)
        self.store.append([_('WPA & WPA2 Personal')])

        self.combo = Gtk.ComboBox(model=self.store)
        cell = Gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 0)
        self.combo.set_active(0)

        self.hbox = Gtk.HBox()
        self.hbox.pack_start(Gtk.Label(_('Wireless Security:')), True, True, 0)
        self.hbox.pack_start(self.combo, True, True, 0)
        self.hbox.show_all()

        self.vbox.pack_start(self.hbox, True, True, 0)

    def _get_security(self):
        return self._entry.get_text()

    def print_security(self):
        key = self._get_security()
        print 'Key: %s' % key

    def create_security(self):
        wsec = {'psk': self._get_security()}
        return {'802-11-wireless-security': wsec}

    def _update_response_sensitivity(self, ignored=None):
        key = self._entry.get_text()
        is_hex = string_is_hex(key)

        valid = False
        if len(key) == 64 and is_hex:
            # hex key
            valid = True
        elif len(key) >= 8 and len(key) <= 63:
            # passphrase
            valid = True
        self.set_response_sensitive(Gtk.ResponseType.OK, valid)
        return False


def create(ssid, flags, wpa_flags, rsn_flags, dev_caps, response):
    if wpa_flags == network.NM_802_11_AP_SEC_NONE and \
            rsn_flags == network.NM_802_11_AP_SEC_NONE:
        key_dialog = WEPKeyDialog(ssid, flags, wpa_flags, rsn_flags,
                                  dev_caps, response)
    elif (wpa_flags & network.NM_802_11_AP_SEC_KEY_MGMT_PSK) or \
            (rsn_flags & network.NM_802_11_AP_SEC_KEY_MGMT_PSK):
        key_dialog = WPAPersonalKeyDialog(ssid, flags, wpa_flags, rsn_flags,
                                          dev_caps, response)
    elif (wpa_flags & network.NM_802_11_AP_SEC_KEY_MGMT_802_1X) or \
            (rsn_flags & network.NM_802_11_AP_SEC_KEY_MGMT_802_1X):
        # nothing. All details are asked for WPA/WPA2-Enterprise
        # networks, before the conneection-activation is done.
        return
    key_dialog.connect('response', _key_dialog_response_cb)
    key_dialog.show_all()
    width, height = key_dialog.get_size()
    key_dialog.move(Gdk.Screen.width() / 2 - width / 2,
                    style.GRID_CELL_SIZE * 2)


def get_key_values(key_list, final_callback, settings):
    key_dialog = KeyValuesDialog(key_list, final_callback,
                                 settings)
    key_dialog.show_all()


def _key_dialog_response_cb(key_dialog, response_id):
    response = key_dialog.get_response_object()
    secrets = None
    if response_id == Gtk.ResponseType.OK:
        secrets = key_dialog.create_security()

    if response_id in [Gtk.ResponseType.CANCEL, Gtk.ResponseType.NONE,
                       Gtk.ResponseType.DELETE_EVENT]:
        # key dialog dialog was canceled; send the error back to NM
        response.set_error(CanceledKeyRequestError())
    elif response_id == Gtk.ResponseType.OK:
        if not secrets:
            raise RuntimeError('Invalid security arguments.')
        response.set_secrets(secrets)
    else:
        raise RuntimeError('Unhandled key dialog response %d' % response_id)

    key_dialog.destroy()
