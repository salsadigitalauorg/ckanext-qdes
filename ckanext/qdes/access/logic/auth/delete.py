from ckan.plugins.toolkit import chained_auth_function
from ckanext.qdes.access import helpers
import ckan.authz as authz


@chained_auth_function
def member_delete(next_auth, context, data_dict):
    if helpers.has_user_access_to_update_members_for_organisation(context, data_dict):
        # sysadmins only
        return {'success': False}
    else:
        # Fallback to the default CKAN behaviour
        return next_auth(context, data_dict)


def organisation_ad_group(context, data_dict):
    return authz.is_authorized('organization_update', context, data_dict)
