# Copyright (C) 2015 Martin Abente Lahaye <tch@sugarlabs.org>
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

from jarabe.model import brightness

STEPS = 8
BOUND_KEYS = ['XF86MonBrightnessUp', 'XF86MonBrightnessDown']


def handle_key_press(key):
    model = brightness.get_instance()
    if not model.get_path():
        return

    value = model.get_brightness()
    max_value = model.get_max_brightness()
    delta = max_value / STEPS

    if key == 'XF86MonBrightnessUp':
        new_value = value + delta
        if new_value > max_value:
            new_value = max_value
    else:
        new_value = value - delta
        if new_value < 0:
            new_value = 0

    model.set_brightness(new_value)