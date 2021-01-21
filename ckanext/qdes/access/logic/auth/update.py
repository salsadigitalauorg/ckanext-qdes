import ckan.plugins.toolkit as toolkit


@toolkit.chained_auth_function
def user_update(next_auth, context, data_dict):
    # sysadmins only
    return {'success': False}


@toolkit.chained_auth_function
def group_edit_permissions(next_auth, context, data_dict):
    # sysadmins only
    return {'success': False}

