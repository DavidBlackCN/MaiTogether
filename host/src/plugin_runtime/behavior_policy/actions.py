"""Reviewed OneBot actions. A method-name prefix is not a permission."""
from hashlib import sha256
import json

READ = frozenset('''get_login_info get_version_info get_status get_msg get_forward_msg
get_group_info get_group_list get_group_member_info get_group_member_list get_stranger_info
get_friend_list get_group_msg_history get_friend_msg_history get_essence_msg_list
get_group_honor_info get_group_system_msg get_group_notice get_group_file_system_info
get_group_root_files get_group_files_by_folder get_group_file_url get_private_file_url
get_image get_record can_send_image can_send_record get_online_clients get_robot_uin_range
get_c2c_msg_history get_client_status get_group_at_all_remain get_group_shut_list
get_group_ignore_add_request get_unidirectional_friend_list get_profile_like get_file'''.split())
SOCIAL = frozenset('''send_msg send_group_msg send_private_msg send_forward_msg
send_group_forward_msg send_private_forward_msg send_poke group_poke friend_poke
set_msg_emoji_like unset_msg_emoji_like send_like set_group_sign send_group_sign
upload_group_file upload_private_file send_group_ai_record send_qzone_msg'''.split())
MANAGEMENT = frozenset('''set_group_ban set_group_whole_ban set_group_kick delete_msg
set_group_card set_group_name set_group_admin set_group_special_title
set_group_add_request set_friend_add_request delete_group_file set_essence_msg delete_essence_msg'''.split())
MESSAGE_TARGET = frozenset(('set_msg_emoji_like', 'unset_msg_emoji_like', 'delete_msg',
                            'set_essence_msg', 'delete_essence_msg'))


def category(name):
    if name in READ:
        return 'read'
    if name in SOCIAL:
        return 'social'
    if name in MANAGEMENT:
        return 'management'
    return 'unknown'


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def text_digest(params):
    message = params.get('message')
    if isinstance(message, str):
        text = message
    elif isinstance(message, list) and all(isinstance(s, dict) and s.get('type') == 'text'
                                          and isinstance(s.get('data'), dict) for s in message):
        text = ''.join(str(s['data'].get('text', '')) for s in message)
    else:
        return ''
    return sha256(text.encode()).hexdigest()
