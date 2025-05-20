# encoding: utf-8
import logging
import string
import secrets
import ckan.authz as authz
import ckan.model as model
import ckan.logic.auth as logic_auth

from ckan.plugins.toolkit import (
    config,
    aslist,
    get_action,
    get_converter,
    get_validator
)

log = logging.getLogger(__name__)


def has_user_access_to_update_members_for_organisation(context, data_dict):
    group = logic_auth.get_group_object(context, data_dict)
    user = context.get('user')

    # If the group is a organization it means we are trying to add a user as a member to the organisation
    # We want to lock this down to only allowing sysadmin user access:
    return group.is_organization and not authz.is_sysadmin(user)


def get_context_with_site_user():
    return {
        u'user': get_action('get_site_user')({'ignore_auth': True}, {})['name']
    }


def user_password_valid(user_dict):
    # If password has not been set it does not need to be validated
    if 'password' not in user_dict:
        return True

    errors = {}
    errors[('password',)] = []
    get_validator('user_password_validator')('password', {'password': user_dict.get('password')}, errors, None)
    return len(errors[('password',)]) == 0


def generate_password():
    while True:
        alphabet = string.ascii_lowercase + string.ascii_uppercase + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for i in range(12))
        # Occasionally it won't meet the constraints, so check
        errors = {}
        errors[('password',)] = []
        get_validator('user_password_validator')('password', {'password': password}, errors, None)
        if len(errors[('password',)]) == 0:
            # If there are no errors it must be a valid password
            break
    return password


def get_organisation_mapping():
    group_extras = model.Session \
        .query(model.GroupExtra) \
        .filter(model.GroupExtra.key == 'ad_groups') \
        .filter(model.GroupExtra.state == 'active').all()

    organisation_mapping = {}
    for group_extra in group_extras:
        ad_groups = get_converter('json_or_string')(group_extra.value or [])
        for ad_group in ad_groups if isinstance(ad_groups, list) else []:
            organisation_mapping[ad_group.get('group')] = {"org_id": group_extra.group_id, "role": ad_group.get('role')}

    return organisation_mapping


def get_read_only_saml_groups():
    return aslist(config.get('ckanext.qdes_access.saml_read_only_group'))


def saml_group_mapping_exist(saml_groups):
    organisation_mapping = get_organisation_mapping()
    read_only_saml_groups = get_read_only_saml_groups()
    if isinstance(saml_groups, list):
        # If saml_groups exist and there is either organisation_mapping or read_only_saml_groups config set up, check to see if any saml_groups exist
        # First check if organisation_mapping_exists, if this is false then check if read_only_saml_groups_exists
        organisation_mapping_exists = any(saml_group for saml_group in saml_groups if saml_group in organisation_mapping) if isinstance(
            organisation_mapping, dict) else False
        log.debug('organisation_mapping_exists: {0}'.format(organisation_mapping_exists))
        read_only_saml_groups_exists = any(saml_group for saml_group in saml_groups if saml_group in read_only_saml_groups) if isinstance(
            read_only_saml_groups, list) else False
        log.debug('read_only_saml_groups_exists: {0}'.format(read_only_saml_groups_exists))
        return organisation_mapping_exists or read_only_saml_groups_exists
    else:
        # There are no SAML groups to find mappings, return false to stop login workflow
        log.debug('No SAML groups')
        return False


def update_user_organisations(user, saml_groups):
    context = get_context_with_site_user()

    remove_user_from_all_organisations(context, user)

    # Load organisation_mapping config from CKAN.INI which will be in JSON format
    # The order of the organisation_mapping config values should be sorted with highest role priority mapping first
    organisation_mapping = get_organisation_mapping()
    log.debug('Using organisation_mapping: {0}'.format(organisation_mapping))

    if isinstance(organisation_mapping, dict) and isinstance(saml_groups, list):
        organisations_added = []
        for org_map in organisation_mapping:
            log.debug('Checking organisation_mapping: {0}'.format(org_map))
            if org_map in saml_groups:
                organisation = organisation_mapping[org_map]
                log.debug('SAML group found in organisation_mapping: {0}'.format(organisation))
                org_name = organisation.get('org_name', None)
                org_role = organisation.get('role', None)
                if org_name not in organisations_added and add_organisation_member(context, user, org_name, org_role):
                    # If adding organisation member was successful we add it to the list as only 1 (the highest) role is assigned per organisation
                    log.debug('Member role "{0}" was successfully added to organisation "{1}"'.format(org_role, org_name))
                    organisations_added.append(org_name)


def remove_user_from_all_organisations(context, user):
    # Remove user's access from its current organisations, saml2 groups are the source of truth
    # Get organisations that the user has a permission for
    organisation_list_for_user = get_action('organization_list_for_user')(context, {"id": user})
    log.debug('Removing {0} from all its current organisation roles'.format(user))
    for organisation in organisation_list_for_user or []:
        remove_organisation_member(context, user, organisation.get('name'), organisation.get('capacity'))


def remove_organisation_member(context, user, org_name, role):
    member_dict = {
        'username': user,
        'id': org_name,
        'role': role,
    }
    log.debug('Removing {0} member role from organisation {1}'.format(user, member_dict))
    get_action('organization_member_delete')(context, member_dict)


def add_organisation_member(context, user, org_name, role):
    # Only add a saml role if org_name has a value and the role exist in ckan roles list
    if org_name is not None and role in [role.get('value') for role in authz.roles_list()]:
        member_dict = {
            'username': user,
            'id': org_name,
            'role': role,
        }
        log.debug('Adding {0} member role to organisation: {1}'.format(user, member_dict))
        get_action('organization_member_create')(context, member_dict)
        return True
    else:
        log.debug('Role does not exist in roles list: {0}'.format(role))
        return False


def update_user_sysadmin_status(userobj, saml_sysadmin_group, groups):
    if not userobj:
        return

    if userobj.sysadmin and saml_sysadmin_group not in groups:
        log.debug(f'User {userobj.name} is not part of the {saml_sysadmin_group} group, removing sysadmin access')
        userobj.sysadmin = False
        model.Session.add(userobj)
        model.Session.commit()
    elif not userobj.sysadmin and saml_sysadmin_group in groups:
        log.debug(f'User {userobj.name} is part of the {saml_sysadmin_group} group, adding sysadmin access')
        # Sysadmin does not need to be a member of any organisation as they have access to all organisations
        remove_user_from_all_organisations(get_context_with_site_user(), userobj.name)
        userobj.sysadmin = True
        model.Session.add(userobj)
        model.Session.commit()


def delete_user(userobj):
    if not userobj:
        return

    context = get_context_with_site_user()
    log.debug('Deleting user {0}'.format(userobj.name))
    get_action('user_delete')(context, {"id": userobj.id})
    userobj.purge()
    userobj.commit()
