from datetime import datetime, time

from argon2 import PasswordHasher, exceptions


password_hasher = PasswordHasher()


def is_time_between(begin_time, end_time, check_time):
    """
    https://stackoverflow.com/a/10048290/6928824
    """
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    # crosses midnight
    else:
        return check_time >= begin_time or check_time <= end_time


def do_not_disturb_now(server_config):
    do_not_disturb = server_config.do_not_disturb
    now = datetime.now().time()
    begin = time(*do_not_disturb['begin'])
    end = time(*do_not_disturb['end'])
    return is_time_between(begin, end, now)


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(hash, password):
    return password_hasher.verify(hash, password)


VerificationError = exceptions.VerificationError
