import ckan.plugins.toolkit as toolkit
import ckan.authz as authz
import ckan.logic.auth as logic_auth


def has_user_access_to_update_members_for_organsation(context, data_dict):
    group = logic_auth.get_group_object(context, data_dict)
    user = context.get('user')

    # If the group is a organization it means we are trying to add a user as a member to the organisation
    # We want to lock this down to only allowing sysadmin user access:
    return group.is_organization and not authz.is_sysadmin(user)
