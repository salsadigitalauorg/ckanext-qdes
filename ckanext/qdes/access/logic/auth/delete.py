import ckan.plugins.toolkit as toolkit
from ckanext.qdes.access import helpers


@toolkit.chained_auth_function
def member_delete(next_auth, context, data_dict):
    if helpers.has_user_access_to_update_members_for_organsation(context, data_dict):
        # sysadmins only
        return {'success': False}
    else:
        # Fallback to the default CKAN behaviour
        return next_auth(context, data_dict)
