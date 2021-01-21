import ckan.plugins as plugins
from ckanext.qdes.access import blueprint
from ckanext.qdes.access.logic.auth import (
    update as auth_update,
    create as auth_create,
    delete as auth_delete
)


class QdesAccessPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IAuthFunctions)

    # IBlueprint
    def get_blueprint(self):
        return blueprint.qdes_access

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            'user_update': auth_update.user_update,
            'group_edit_permissions': auth_update.group_edit_permissions,
            'member_create': auth_create.member_create,
            'member_delete': auth_delete.member_delete
        }
