# Copyright (C) 2014, Sugar Labs
# Copyright (C) 2014, Walter Bender
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GConf
from gi.repository import GObject

import os
import json
import time
import math
import logging

from gettext import gettext as _

from sugar3.graphics.icon import EventIcon
from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor

from jarabe.intro.genderpicker import GENDERS

_group_stats = None
_SECONDS_PER_YEAR = 365 * 24 * 60 * 60.


def calculate_birth_timestamp(age):
    age_in_seconds = age * _SECONDS_PER_YEAR
    birth_timestamp = int(time.time() - age_in_seconds)
    return birth_timestamp


def calculate_age(birth_timestamp):
    age_in_seconds = time.time() - birth_timestamp
    # Round to nearest int
    age = int(math.floor(age_in_seconds / _SECONDS_PER_YEAR) + 0.5)
    return age


def age_to_index(age):
    group_stats = get_group_stats()

    if age is None:
        return int(len(group_stats.AGES) / 2.0)

    age2 = age * 2
    for i in range(len(group_stats.AGES) - 1):
        if age2 < (group_stats.AGES[i] + group_stats.AGES[i + 1]):
            return i

    return len(group_stats.AGES) - 1


def age_to_group_label(age):
    group_stats = get_group_stats()

    return group_stats.AGE_LABELS[age_to_index(age)]


def group_label_to_age(label):
    group_stats = get_group_stats()

    if labels not in group_stats.AGE_LABELS:
        return None

    return group_stats.AGES[group_stats.AGE_LABELS.index(label)]


def load_age():
    group_stats = get_group_stats()

    client = GConf.Client.get_default()
    birth_timestamp = client.get_int('/desktop/sugar/user/birth_timestamp')

    if birth_timestamp == 0:
        return None

    birth_age = calculate_age(birth_timestamp)

    age = (group_stats.AGES[-2] + group_stats.AGES[-1]) / 2.
    if birth_age >= age:
        return group_stats.AGES[-1]

    for i in range(len(group_stats.AGES) - 1):
        age = (group_stats.AGES[i] + group_stats.AGES[i + 1]) / 2.
        if birth_age < age:
            return group_stats.AGES[i]

    return None


def save_age(age):
    if age is None:
        return
    birth_timestamp = calculate_birth_timestamp(age)
    client = GConf.Client.get_default()
    client.set_int('/desktop/sugar/user/birth_timestamp', birth_timestamp)

    # Record the label so we know it was set
    client.set_string('/desktop/sugar/user/group', age_to_group_label(age))


class GroupStats():
    GROUP_LABEL = []
    AGES = []
    AGE_LABELS = []
    AGE_ICONS = []

    def __init__(self):
        f = open(os.environ["SUGAR_GROUP_LABELS"], 'r')
        json_data = f.read()
        f.close()
        group_stats = json.loads(json_data)
        self.GROUP_LABEL = group_stats['group-label']
        for item in group_stats['group-items']:
            self.AGE_ICONS.append([item['female-icon'], item['male-icon']])
            self.AGE_LABELS.append(_(item['label']))
            self.AGES.append(item['age'])


def get_group_stats():
    global _group_stats

    if not _group_stats:
        _group_stats = GroupStats()

    return _group_stats


class Picker(Gtk.Grid):

    def __init__(self, icon, label):
        Gtk.Grid.__init__(self)

        self._button = EventIcon(pixel_size=style.LARGE_ICON_SIZE,
                                 icon_name=icon)
        self.attach(self._button, 0, 0, 1, 1)
        self._button.show()

        self._label = Gtk.Label(label)
        self.attach(self._label, 0, 1, 1, 1)
        self._label.show()

    def connect(self, callback, arg):
        self._button.connect('button-press-event', callback, arg)

    def set_color(self, color):
        self._button.xo_color = color

    def set_icon(self, icon):
        self._button.set_icon_name(icon)


class AgePicker(Gtk.Grid):

    age_changed_signal = GObject.Signal('age-changed', arg_types=([int]))

    def __init__(self, gender, page=None):
        Gtk.Grid.__init__(self)

        self.set_row_spacing(style.DEFAULT_SPACING)
        self.set_column_spacing(style.DEFAULT_SPACING)

        self._group_stats = get_group_stats()

        self._page = page
        self._gender = gender
        self._age = self.get_age()
        self._pickers = []
        self._nocolor = XoColor('#010101,#ffffff')
        self._color = XoColor()

        if self._gender not in GENDERS:
            self._gender = 'female'

        gender_index = GENDERS.index(self._gender)
        age_index = age_to_index(self._age)

        width = Gdk.Screen.width()

        num_ages = len(self._group_stats.AGES)
        for i in range(num_ages):
            self._pickers.append(
                Picker(self._group_stats.AGE_ICONS[i][gender_index],
                       _(self._group_stats.AGE_LABELS[i])))
            self._pickers[i].connect(self._button_press_cb, i)

        self._fixed = Gtk.Fixed()
        fixed_size = width - 4 * style.GRID_CELL_SIZE
        self._fixed.set_size_request(fixed_size, -1)
        self.attach(self._fixed, 0, 0, 1, 1)
        self._fixed.show()

        self._age_adj = Gtk.Adjustment(value=age_index, lower=0,
                                       upper=num_ages - 1, step_incr=1,
                                       page_incr=1, page_size=0)
        self._age_adj.connect('value-changed', self.__age_adj_changed_cb)

        self._age_slider = Gtk.HScale()
        self._age_slider.set_draw_value(False)
        self._age_slider.set_adjustment(self._age_adj)
        self.attach(self._age_slider, 0, 1, 1, 1)

        for i in range(num_ages):
            self._fixed.put(self._pickers[i], 0, 0)

        self._configure(width)

        Gdk.Screen.get_default().connect('size-changed', self._configure_cb)

    def _configure_cb(self, event=None):
        width = Gdk.Screen.width()
        self._configure(width)

    def _configure(self, width):
        fixed_size = width - 4 * style.GRID_CELL_SIZE
        self._fixed.set_size_request(fixed_size, -1)

        num_ages = len(self._group_stats.AGES)

        dx = int((fixed_size - style.LARGE_ICON_SIZE) / (num_ages - 1))
        for i in range(num_ages):
            self._fixed.move(self._pickers[i], dx * i, 0)

        if num_ages + 2 < width / style.LARGE_ICON_SIZE:
            for i in range(num_ages):
                self._pickers[i].show()
            self._age_slider.hide()
        else:
            self._age_slider.show()
            value = self._age_adj.get_value()
            self._set_age_picker(int(value + 0.5))

    def get_label(self):
        return self._group_stats.GROUP_LABEL

    def _set_age_picker(self, age_index):
        for i in range(len(self._group_stats.AGES)):
            if i == age_index:
                self._pickers[i].show()
            else:
                self._pickers[i].hide()
        self._do_selected(age_index)

    def __age_adj_changed_cb(self, widget):
        value = self._age_adj.get_value()
        self._set_age_picker(int(value + 0.5))

    def _do_selected(self, age_index):
        if self._age is not None:
            i = age_to_index(self._age)
            self._pickers[i].set_color(self._nocolor)
        self._set_age(self._group_stats.AGES[age_index])
        self._pickers[age_index].set_color(self._color)

    def _button_press_cb(self, widget, event, age_index):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            self._do_selected(age_index)

    def get_age(self):
        if self._page is None:
            return load_age()
        elif hasattr(self, '_age'):
            if self._age is None:
                return None
            i = age_to_index(self._age)
            return self._group_stats.AGES[i]
        return None

    def _set_age(self, age):
        if self._page is None:
            if age != self._age:
                self.age_changed_signal.emit(age)
        else:
            self._page.set_valid(True)
        self._age = age

    def update_color(self, color):
        self._color = color
        if self._age is not None:
            i = age_to_index(self._age)
            self._pickers[i].set_color(self._color)

    def update_gender(self, gender):
        self._gender = gender

        if self._gender in GENDERS:
            gender_index = GENDERS.index(self._gender)
        else:
            gender_index = 0

        for i in range(len(self._group_stats.AGES)):
            self._pickers[i].set_icon(
                self._group_stats.AGE_ICONS[i][gender_index])
