import logging
import ckan.plugins as plugins

from ckanext.qdes.access import blueprint, middleware
from ckanext.qdes.access.logic.auth import update as auth_update

log = logging.getLogger(__name__)


class QdesAccessPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IMiddleware, inherit=True)

    # IBlueprint
    def get_blueprint(self):
        return blueprint.qdes_access

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            'user_update': auth_update.user_update,
        }

    # IMiddleware
    def make_middleware(self, app, config):
        return middleware.QdesAuthMiddleware(app, config)
