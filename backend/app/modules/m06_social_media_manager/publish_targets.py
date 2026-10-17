"""Non-secret provider subject IDs carried in the owner's publish review."""
import re
from .adapters import AdapterAuthError


def publish_target(platform, account_id):
    # Bounds are defensive input bounds, not claims about provider ID limits.
    if type(account_id) is not str or not account_id or len(account_id) > 256:
        raise AdapterAuthError('publishing account identity is unavailable')
    pattern = r'[A-Za-z0-9_.:-]+' if platform == 'tiktok' else r'[0-9]+'
    if platform not in {'instagram', 'linkedin', 'twitter', 'tiktok'} or not re.fullmatch(pattern, account_id):
        raise AdapterAuthError('publishing account identity is invalid')
    return {'platform': platform, 'account_id': account_id}


def valid_target(platform, target):
    try:
        return (type(target) is dict and set(target) == {'platform', 'account_id'}
                and publish_target(platform, target['account_id']) == target)
    except (AdapterAuthError, KeyError, TypeError):
        return False
