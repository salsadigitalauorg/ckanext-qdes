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

# Fallback only - get_role_priority() derives this from CKAN so the two cannot
# drift. Highest first.
ROLE_PRIORITY = {
    'admin': 3,
    'editor': 2,
    'member': 1,
}


def get_role_priority():
    """Return a {role: priority} map for CKAN's organisation roles, highest wins.

    Derived from `authz.ROLE_PERMISSIONS`, an OrderedDict declared
    most-privileged first, so roles added by CKAN or a plugin rank
    automatically.
    """
    try:
        roles = list(authz.ROLE_PERMISSIONS)
    except Exception:
        log.warning('Could not read CKAN ROLE_PERMISSIONS, falling back to ROLE_PRIORITY', exc_info=True)
        return dict(ROLE_PRIORITY)

    if not roles:
        log.warning('CKAN ROLE_PERMISSIONS is empty, falling back to ROLE_PRIORITY')
        return dict(ROLE_PRIORITY)

    # First declared is most privileged.
    return {role: len(roles) - index for index, role in enumerate(roles)}


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

    # Every mapping is collected, not overwritten: one AD group may grant roles
    # in several organisations, and one organisation may be reached via several.
    organisation_mapping = {}
    for group_extra in group_extras:
        ad_groups = get_converter('json_or_string')(group_extra.value or [])
        for ad_group in ad_groups if isinstance(ad_groups, list) else []:
            if not isinstance(ad_group, dict):
                continue
            group_name = ad_group.get('group')
            if not group_name:
                continue
            organisation_mapping.setdefault(group_name, []).append(
                {'org_id': group_extra.group_id, 'role': ad_group.get('role')})

    return organisation_mapping


def select_highest_role(roles, org_id=None, valid_roles=None):
    """Return the highest priority role from `roles`, or None.

    The result is always one of the supplied `roles` - never an escalation
    beyond what the user's AD groups assert. Roles CKAN rejects are discarded
    so a mis-configured mapping cannot deny a valid lower role. Roles CKAN
    accepts but cannot rank stay eligible, ranked last.

    `valid_roles` may be supplied to avoid resolving CKAN's role list.
    """
    if valid_roles is None:
        valid_roles = [role.get('value') for role in authz.roles_list()]

    role_priority = get_role_priority()

    # Below every known role, so an unrankable role only wins unopposed.
    unranked_priority = min(role_priority.values()) - 1 if role_priority else 0

    candidates = []
    invalid_roles = []
    unranked_roles = []
    for role in roles or []:
        if role not in valid_roles:
            invalid_roles.append(role)
            continue
        if role not in role_priority:
            unranked_roles.append(role)
        candidates.append(role)

    if invalid_roles:
        log.warning('Ignoring role(s) {0} for organisation {1} - not a valid CKAN role'.format(invalid_roles, org_id))

    if unranked_roles:
        log.warning(
            'Role(s) {0} for organisation {1} are valid CKAN roles with no known priority, '
            'ranking them below all known roles'.format(unranked_roles, org_id)
        )

    if not candidates:
        log.warning(
            'No valid role could be selected for organisation {0} from roles {1}'.format(org_id, list(roles or []))
        )
        return None

    return max(candidates, key=lambda role: role_priority.get(role, unranked_priority))


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

    # Mappings live in each organisation's 'ad_groups' extra, not CKAN.INI.
    organisation_mapping = get_organisation_mapping()
    log.debug('Using organisation_mapping: {0}'.format(organisation_mapping))

    if isinstance(organisation_mapping, dict) and isinstance(saml_groups, list):
        # Iterate the user's SAML groups, not the mapping, so the result does
        # not depend on the order rows came back from the database.
        candidate_roles = {}
        matched_groups = {}
        for saml_group in saml_groups:
            for organisation in organisation_mapping.get(saml_group) or []:
                org_id = organisation.get('org_id', None)
                if org_id is None:
                    continue
                candidate_roles.setdefault(org_id, []).append(organisation.get('role', None))
                matched_groups.setdefault(org_id, []).append(saml_group)

        # Assign a single role per organisation, taking the highest granted.
        for org_id, roles in candidate_roles.items():
            log.info('Organisation "{0}" matched AD group(s) {1} granting role(s) {2} for user "{3}"'.format(org_id, matched_groups.get(org_id), roles, user))
            org_role = select_highest_role(roles, org_id)
            if org_role and add_organisation_member(context, user, org_id, org_role):
                log.info('Selected highest role "{0}" for user "{1}" in organisation "{2}"'.format(org_role, user, org_id))


def remove_user_from_all_organisations(context, user):
    # Remove user's access from its current organisations, saml2 groups are the source of truth
    # Get organisations that the user has a permission for
    organisation_list_for_user = get_action('organization_list_for_user')(context, {"id": user})
    log.debug('Removing {0} from all its current organisation roles'.format(user))
    for organisation in organisation_list_for_user or []:
        remove_organisation_member(context, user, organisation.get('name'), organisation.get('capacity'))


def remove_organisation_member(context, user, org_id, role):
    member_dict = {
        'username': user,
        'id': org_id,
        'role': role,
    }
    log.debug('Removing {0} member role from organisation {1}'.format(user, member_dict))
    get_action('organization_member_delete')(context, member_dict)


def add_organisation_member(context, user, org_id, role):
    # Only add a saml role if org_id has a value and the role exist in ckan roles list
    if org_id is not None and role in [role.get('value') for role in authz.roles_list()]:
        member_dict = {
            'username': user,
            'id': org_id,
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
