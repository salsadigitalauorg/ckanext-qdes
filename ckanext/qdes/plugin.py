import ckan.lib.email_notifications as email_notifications
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckan.common import _
from ckanext.qdes import blueprint, helpers
from ckanext.qdes.cli import get_commands
from ckanext.qdes.logic.action import get, create
from pprint import pformat

log = logging.getLogger(__name__)


class QdesPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IClick)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'qdes')

        toolkit.add_ckan_admin_tab(toolkit.config, 
                                    'qdes.api_tokens',
                                    'API Tokens',
                                    config_var='ckan.admin_tabs', 
                                    icon=None)


    # IConfigurer
    def update_config_schema(self, schema):
        ignore_missing = toolkit.get_validator('ignore_missing')
        is_positive_integer = toolkit.get_validator('is_positive_integer')

        schema.update({
            'ckanext.qdes_schema.dataset_review_period': [ignore_missing, is_positive_integer],
            'ckanext.qdes_schema.dataset_audit_period': [ignore_missing, is_positive_integer],
            'ckanext.qdes_schema.dataset_audit_period_last_run': [ignore_missing],
            'ckanext.qdes_schema.contact': [ignore_missing],
        })

        return schema

    # IBlueprint
    def get_blueprint(self):
        return blueprint.qdes

    # ITemplateHelpers
    def get_helpers(self):
        return {
            'qdes_review_datasets': helpers.qdes_review_datasets,
            'qdes_review_due_date': helpers.qdes_review_due_date,
            'qdes_get_dataset_review_period': helpers.qdes_get_dataset_review_period,
            'qdes_organization_list': helpers.qdes_organization_list,
            'qdes_render_date_with_offset': helpers.qdes_render_date_with_offset,
            'qdes_activity_stream_detail': helpers.qdes_activity_stream_detail,
        }

    # IClick
    def get_commands(self):
        return get_commands()

    # IActions
    def get_actions(self):
        return {
            'get_review_datasets': get.review_datasets,
            'qdes_datasets_not_updated': get.qdes_datasets_not_updated,
            'qdes_datasets_with_empty_recommended_fields': get.qdes_datasets_with_empty_recommended_fields,
            'qdes_datasets_with_invalid_urls': get.qdes_datasets_with_invalid_urls,
            'qdes_datasets_not_reviewed': get.qdes_datasets_not_reviewed,
            'qdes_report_all': get.qdes_report_all,
            'create_review_datasets_job': create.review_datasets_job,
            'user_create': create.user_create
        }

    # IClick
    def get_commands(self):
        return get_commands()


# Replace _notifications_for_activities function to replace the email subject.
def update_email_subject(func):
    def update(activities, user_dict):
        notifications = func(activities, user_dict)
        if notifications:
            notifications[0]['subject'] = _('Ecoscience.QLD Data Catalogue - Activity on Followed Content')

        return notifications

    return update

email_notifications._notifications_for_activities = update_email_subject(email_notifications._notifications_for_activities)
