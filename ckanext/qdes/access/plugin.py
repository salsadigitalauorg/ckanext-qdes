import logging
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from ckanext.qdes.access import blueprint, middleware
from ckanext.qdes.access.logic.auth import (
    update as auth_update,
    create as auth_create,
    delete as auth_delete,
    get as auth_get
)

log = logging.getLogger(__name__)


class QdesAccessPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)

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
            'api_token_list': auth_get.api_token_list,
            'user_reset': auth_get.user_reset,
            'request_reset': auth_get.request_reset
        }

    # IMiddleware
    def make_middleware(self, app, config):
        return middleware.QdesAuthMiddleware(app, config)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
