import logging
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from ckanext.qdes.access import blueprint, middleware, helpers
from ckanext.qdes.access.logic.auth import (
    update as auth_update,
    create as auth_create,
    delete as auth_delete,
    get as auth_get
)
from ckanext.saml2auth.interfaces import ISaml2Auth

log = logging.getLogger(__name__)


class QdesAccessPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(ISaml2Auth)

    # IBlueprint
    def get_blueprint(self):
        return blueprint.qdes_access

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            'user_update': auth_update.user_update,
            'group_edit_permissions': auth_update.group_edit_permissions,
            'member_create': auth_create.member_create,
            'member_delete': auth_delete.member_delete,
            'user_reset': auth_get.user_reset,
            'request_reset': auth_get.request_reset
        }

    # IMiddleware
    def make_middleware(self, app, config):
        return middleware.QdesAuthMiddleware(app, config)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')

    # ISaml2Auth
    def before_saml2_user_update(self, user_dict, saml_attributes):
        # Sometimes Saml2Auth updates the user password which will fail validation
        if not helpers.user_password_valid(user_dict):
            log.debug('Password invalid, generating new password')
            user_dict['password'] = helpers.generate_password()

    def before_saml2_user_create(self, user_dict, saml_attributes):
        # Saml2Auth creates a password which will fail our password validator
        log.debug('New user, generating password')
        user_dict['password'] = helpers.generate_password()

    def after_saml2_login(self, resp, saml_attributes):
        saml_user_group = toolkit.config.get(u'ckanext.qdes_access.saml_user_group', None)
        saml_sysadmin_group = toolkit.config.get(u'ckanext.qdes_access.saml_sysadmin_group', None)
        # If saml_user_group is configured, user cannot login with out a successful SAML group mapping to either organisation_mapping or read_only_saml_groups
        if saml_user_group:
            log.debug('Looking for SAML group with value: {}'.format(saml_user_group))
            groups = saml_attributes.get(saml_user_group, [])
            # groups = ['CG-FED-DDCAT-SDK-M', 'CG-FED-DDCAT']
            log.debug('SAML groups found: {}'.format(groups))
            # This is set in the SAML2 extension before this interface is called
            userobj = toolkit.g.userobj
            if helpers.saml_group_mapping_exist(groups):
                helpers.update_user_sysadmin_status(userobj, saml_sysadmin_group, groups)
                if not userobj.sysadmin:
                    helpers.update_user_organasitions(userobj.name, groups)
            else:
                log.warning('User {0} groups {1} does not exists'.format(userobj.fullname, groups))
                # Delete user and override login response with a redirect response to the unauthorised page
                helpers.delete_user(toolkit.g.userobj)
                resp = toolkit.redirect_to('qdes_access.unauthorised', fullname=userobj.fullname, email=userobj.email)

        return resp
