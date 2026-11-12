"""Pure MaiWeave v1 interpretation, also bundled into the MaiWork adaptation.

This is an advisory life condition, never an authorization or a send ticket.
No model, storage, network, activity history or inferred sleep schedule lives here.
"""
from datetime import datetime, timezone
import math

WEAVE_PLUGIN = 'ilworkcn.maiweave'
WEAVE_API = 'get_life_status'
BUSY_KINDS = frozenset(('work', 'study', 'travel'))
KINDS = BUSY_KINDS | {'sleep', 'meal', 'leisure', 'rest', 'social', 'diary'}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Missing life timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Life timestamps require a timezone')
    return result.timestamp()


def evaluate_status(status, category, *, max_age_seconds=180, now=None):
    """Read effective sleep from MaiWeave's own life rules.

queried_at dates the decision; updated_at dates stored energy, mood and location.
Each caller obtains a fresh response; this function does not cache permissions.
"""
    result = {'version': 1, 'decision': 'deny', 'reason': 'state_unknown'}
    def deny(reason):
        return {**result, 'reason': reason}
    if (category not in ('social', 'work')
            or type(max_age_seconds) is not int or not 10 <= max_age_seconds <= 3600):
        return deny('invalid_life_query')
    if (not isinstance(status, dict) or type(status.get('version')) is not int
            or status['version'] != 1):
        return deny('life_contract_mismatch')
    if any(type(status.get(key)) is not bool for key in ('ready', 'enabled', 'schedule_enabled')):
        return result
    if not status['ready']:
        return deny('not_ready')
    if not status['enabled']:
        return deny('life_disabled')
    try:
        at = datetime.now(timezone.utc).timestamp() if now is None else now
        if not math.isfinite(at):
            return result
        queried = timestamp(status['queried_at'])
        age = at - queried
        if not -5 <= age <= max_age_seconds:
            return deny('life_state_stale')
        if timestamp(status['updated_at']) > queried + 5:
            return result
        if any(type(status.get(key)) is not bool for key in ('sleeping', 'effective_sleeping')):
            return result
        # Absence and explicit null differ: required fields cannot silently disappear.
        awake = status['awake_until']
        if awake is not None and timestamp(awake) <= at:
            return deny('life_boundary_changed')
        activity = status['current']
        if activity is not None:
            if (not isinstance(activity, dict) or activity.get('kind') not in KINDS
                    or activity.get('status') not in ('scheduled', 'active')
                    or not isinstance(activity.get('id'), str) or not activity['id']):
                return result
            if not timestamp(activity['start']) <= at < timestamp(activity['end']):
                return deny('life_boundary_changed')
        sleeping_plan = activity is not None and activity['kind'] == 'sleep'
        if status['sleeping'] != sleeping_plan:
            return result
        # An idle response can cross the start of its next plan in transit.
        next_plan = status['next_plan']
        if next_plan is not None:
            if not isinstance(next_plan, dict):
                return result
            if timestamp(next_plan['start']) <= at:
                return deny('life_boundary_changed')
        sleep_until = status['sleep_until']
        if status['effective_sleeping']:
            if (not status['schedule_enabled'] or awake is not None
                    or (activity is not None and not sleeping_plan)):
                return result
            if timestamp(sleep_until) <= at:
                return deny('life_boundary_changed')
        elif sleep_until is not None or (status['schedule_enabled'] and sleeping_plan and awake is None):
            return result
    except (KeyError, TypeError, ValueError, OverflowError):
        return result
    if status['effective_sleeping']:
        return deny('sleeping')
    if activity is not None and activity['kind'] in BUSY_KINDS:
        return deny('busy')
    return {**result, 'decision': 'allow', 'reason': 'available'}
