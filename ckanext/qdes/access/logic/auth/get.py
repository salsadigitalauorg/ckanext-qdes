from ckan.plugins.toolkit import auth_sysadmins_check
import ckan.authz as authz


@auth_sysadmins_check
def user_reset(context, data_dict):
    # No access
    return {'success': False}


@auth_sysadmins_check
def request_reset(context, data_dict):
    # No access
    return {'success': False}


def organisation_ad_groups(context, data_dict):
    return authz.is_authorized('organization_update', context, data_dict)
