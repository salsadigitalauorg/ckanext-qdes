import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckan.common import _
from ckanext.activity.logic import validators as activity_validators
from ckanext.qdes import blueprint, helpers, validators, middleware
from ckanext.qdes.cli import get_commands
from ckanext.qdes.logic.action import get, create, delete

import ckanext.activity.email_notifications as email_notifications


log = logging.getLogger(__name__)


class QdesPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurable, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'qdes')

    # IConfigurer

    def update_config_schema(self, schema):
        ignore_missing = toolkit.get_validator('ignore_missing')
        is_positive_integer = toolkit.get_validator('is_positive_integer')
        validate_banner_image = toolkit.get_validator('validate_banner_image')

        schema.update({
            'ckanext.qdes_schema.dataset_review_period': [ignore_missing, is_positive_integer],
            'ckanext.qdes_schema.dataset_audit_period': [ignore_missing, is_positive_integer],
            'ckanext.qdes_schema.dataset_audit_period_last_run': [ignore_missing],
            'ckanext.qdes_schema.contact': [ignore_missing],
            'ckanext.qdes.banner_image': [ignore_missing, validate_banner_image],
            'clear_banner_image_upload': [ignore_missing],
            'banner_image_upload': [ignore_missing]
        })

        return schema

    # IConfigurable
    def configure(self, config):
        activity_validators.object_id_validators['new API token'] = "user_id_exists"
        activity_validators.object_id_validators['revoked API token'] = "user_id_exists"

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
            'qdes_add_activity_for_private_pkg': helpers.qdes_add_activity_for_private_pkg,
            'get_publication_status_history': helpers.get_publication_status_history,
            'get_banner_image': helpers.get_banner_image,
            'get_recently_created_datasets': helpers.get_recently_created_datasets,
            'get_most_popular_datasets': helpers.get_most_popular_datasets,
            'get_dataset_totals_by_type': helpers.get_dataset_totals_by_type,
            'qdes_tracking_enabled': helpers.qdes_tracking_enabled,
            'user_datasets': helpers.user_datasets,
            'qdes_follow_button': helpers.qdes_follow_button,
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
            'user_create': create.user_create,
            'api_token_create': create.api_token_create,
            'api_token_revoke': delete.api_token_revoke,
            'api_token_activity_log': get.api_token_activity_log
        }

    # IClick
    def get_commands(self):
        return get_commands()

    # IPackageController
    def after_dataset_create(self, context, pkg_dict):
        return helpers.qdes_add_activity_for_private_pkg(context, pkg_dict, 'new')

    def after_dataset_update(self, context, pkg_dict):
        return helpers.qdes_add_activity_for_private_pkg(context, pkg_dict, 'changed')

    # IValidators
    def get_validators(self):
        return {
            'validate_banner_image': validators.validate_banner_image
        }

    # IMiddleware
    def make_middleware(self, app, config):
        if toolkit.asbool(config.get('ckan.qdes.tracking_enabled', 'false')):
            return middleware.QdesTrackingMiddleware(app, config)


# Replace _notifications_for_activities function to replace the email subject.
def update_email_subject(func):
    def update(activities, user_dict):
        # Get package name.
        for activity in activities:
            data = activity.get('data', None)
            if data:
                if data.get('package', None):
                    package = model.Package.get(activity.get('object_id'))
                    if package:
                        activity['data']['package']['name'] = package.name
                elif data.get('group', None):
                    group = model.Group.get(activity.get('object_id'))
                    if group:
                        activity['data']['group']['name'] = group.name

                        if not group.type == 'group':
                            activity['data']['group']['is_organization'] = True

        notifications = func(activities, user_dict)
        if notifications:
            notifications[0]['subject'] = _('QESD catalogue – activity on followed content')

        return notifications

    return update


email_notifications._notifications_for_activities = update_email_subject(email_notifications._notifications_for_activities)
