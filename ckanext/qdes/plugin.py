import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckanext.qdes import blueprint, helpers
from ckanext.qdes.cli import get_commands
from ckanext.qdes.logic.action import get

log = logging.getLogger(__name__)


class QdesPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IActions)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'qdes')

    # IBlueprint
    def get_blueprint(self):
        return blueprint.qdes

    # ITemplateHelpers
    def get_helpers(self):
        return {
            'qdes_review_datasets': helpers.qdes_review_datasets,
            'qdes_review_due_date': helpers.qdes_review_due_date,
            'qdes_get_dataset_review_period': helpers.qdes_get_dataset_review_period,
            'qdes_organization_list': helpers.qdes_organization_list
        }

    # IClick
    def get_commands(self):
        return get_commands()

    # IActions
    def get_actions(self):
        return {
            'get_review_datasets': get.review_datasets
        }
