import ckan.plugins.toolkit as toolkit


@toolkit.auth_sysadmins_check
def user_reset(context, data_dict):
    # No access
    return {'success': False}


@toolkit.auth_sysadmins_check
def request_reset(context, data_dict):
    # No access
    return {'success': False}
