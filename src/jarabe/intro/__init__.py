import os

from gi.repository import GConf

from sugar3 import env
from sugar3.profile import get_profile

from jarabe.intro.window import create_profile


def check_profile():
    profile = get_profile()

    path = os.path.join(env.get_profile_path(), 'config')
    if os.path.exists(path):
        profile.convert_profile()

    return profile.is_valid()


def check_group_stats():
    client = GConf.Client.get_default()
    return client.get_string('/desktop/sugar/user/group') is not None
