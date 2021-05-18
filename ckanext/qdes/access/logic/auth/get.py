import ckan.plugins.toolkit as toolkit


# @toolkit.chained_auth_function
# def api_token_list(next_auth, context, data_dict):
#     # sysadmins only
#     return {'success': False}


@toolkit.auth_sysadmins_check
def user_reset(context, data_dict):
    # No access
    return {'success': False}


@toolkit.auth_sysadmins_check
def request_reset(context, data_dict):
    # No access
    return {'success': False}
