import ckan.plugins.toolkit as toolkit


@toolkit.chained_auth_function
def api_token_list(next_auth, context, data_dict):
    # sysadmins only
    return {'success': False}
