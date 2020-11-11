import ckan.plugins.toolkit as toolkit
import ckanext.scheming.helpers as scheming_helpers
import logging

from ckan.model import Session
from ckan.model.group import Group
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
from ckan.lib.helpers import url_for, render_datetime
from ckan.plugins.toolkit import get_action
from ckanext.qdes.helpers import qdes_render_date_with_offset, qdes_get_dataset_review_period, qdes_review_datasets
from ckanext.invalid_uris.model import InvalidUri
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import asc, cast, DateTime
from pprint import pformat

log = logging.getLogger(__name__)


def _qdes_get_organization_list():
    return Session.query(Group).filter(Group.is_organization == True).all()

def _qdes_get_organization_dict_by_id(id, organizations):
    for organization in organizations:
        org_dict = organization.as_dict()
        if org_dict.get('id') == id:
            return org_dict

    return []


def qdes_datasets_not_updated(context, config):
    """
    List of all datasets that have been created but have not been updated in 12 months.
    """
    last_modify_date_threshold = datetime.utcnow() - relativedelta(months=12)

    query = Session.query(Package) \
        .filter(Package.state == 'active') \
        .filter(Package.metadata_modified <= last_modify_date_threshold) \
        .order_by(asc(Package.metadata_modified))

    if config.get('org_id', None):
        query = query.filter(Package.owner_org == config.get('org_id'))

    packages = query.all()

    # Get list of organizations.
    organizations = _qdes_get_organization_list()

    # Build rows.
    rows = []
    for package in packages:
        pkg_dict = package.as_dict()
        extras = pkg_dict.get('extras')
        org_dict = _qdes_get_organization_dict_by_id(pkg_dict.get('owner_org'), organizations)

        rows.append({
            'Dataset name': pkg_dict.get('title', pkg_dict.get('name', '')),
            'Link to dataset (URI)': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'Dataset creator': extras.get('contact_creator', ''),
            'Point of contact (URI)': extras.get('contact_point', ''),
            'Dataset creation date': qdes_render_date_with_offset(pkg_dict.get('metadata_created')),
            'Dataset update date': qdes_render_date_with_offset(pkg_dict.get('metadata_modified')),
            'Organisation name': org_dict.get('title', ''),
        })

    return rows


def _get_recommended_dataset_fields(scheme, field_group):
    recommended_fields = []
    for field in scheme[field_group]:
        if field.get('recommended', False):
            recommended_fields.append(field)

    return recommended_fields


def _check_recommended_field_value(entity_dict, recommended_fields):
    missing_values = []
    for field in recommended_fields:
        f_name = field.get('field_name')
        if entity_dict.get(f_name, None) is None:
            missing_values.append(f_name)

    return missing_values


def qdes_datasets_with_empty_recommended_fields(context, config):
    # Get list of recommended fields.
    dataset_scheme = scheming_helpers.scheming_get_dataset_schema('dataset')
    dataset_recommended_fields = _get_recommended_dataset_fields(dataset_scheme, 'dataset_fields')
    dataset_resource_recommended_fields = _get_recommended_dataset_fields(dataset_scheme, 'resource_fields')

    # Build rows.
    rows = []
    i = 1
    has_result = True
    while has_result:
        packages = get_action('current_package_list_with_resources')({}, {'limit': 10, 'offset': i})
        if not packages:
            has_result = False
        else:
            i += 1

        for package in packages:
            if config.get('org_id') and package.get('organization').get('id') != config.get('org_id'):
                continue

            if package.get('type') == 'dataservice':
                continue

            missing_values = _check_recommended_field_value(package, dataset_recommended_fields)
            rows.append({
                'Dataset name': package.get('title', package.get('name', '')),
                'Link to dataset (URI)': url_for('dataset.read', id=package.get('id'), _external=True),
                'Resource name': '',
                'Link to resource': '',
                'Dataset creator': package.get('contact_creator', ''),
                'Point of contact (URI)': package.get('contact_point', ''),
                'List of recommended fields without values': ', '.join(missing_values),
                'Organisation name': package.get('organization').get('title', ''),
            })

            # Check dataset resource metadata fields.
            for resource in package.get('resources', []):
                missing_values = _check_recommended_field_value(resource, dataset_resource_recommended_fields)
                log.error('res' + resource.get('id'))
                log.error(package.get('id'))
                rows.append({
                    'Dataset name': package.get('title', package.get('name', '')),
                    'Link to dataset (URI)': url_for('dataset.read', id=package.get('id'), _external=True),
                    'Resource name': resource.get('name', ''),
                    'Link to resource': url_for('resource.read',
                                                resource_id=resource.get('id'),
                                                id=package.get('id'),
                                                package_type=package.get('type'),
                                                _external=True
                                                ),
                    'Dataset creator': package.get('contact_creator', ''),
                    'Point of contact (URI)': package.get('contact_point', ''),
                    'List of recommended fields without values': ', '.join(missing_values),
                    'Organisation name': package.get('organization').get('title', ''),
                })

    return rows


def _get_uri_validated_fields(scheme, field_group):
    uri_validated_fields = []
    for field in scheme.get(field_group, []):
        validator = field.get('validators', '').split()
        if 'qdes_uri_validator' in validator:
            uri_validated_fields.append(field)

    return uri_validated_fields


def qdes_datasets_with_invalid_urls(context, config):
    # Get list that need to be validated.
    # dataset_scheme = scheming_helpers.scheming_get_dataset_schema('dataset')
    # dataset_uri_validated_fields = _get_uri_validated_fields(dataset_scheme, 'dataset_fields')
    # dataset_resource_uri_validated_fields = _get_uri_validated_fields(dataset_scheme, 'resource_fields')

    # Get list of invalid uris.
    uris = Session.query(InvalidUri).all()
    invalid_uris = [uri.as_dict() for uri in uris]

    # Build package list.
    entities = {}
    for invalid_uri in invalid_uris:
        if invalid_uri.get('entity_id') in entities:
            entities[invalid_uri.get('entity_id')].get('fields').append(invalid_uri.get('field'))
        else:
            entities[invalid_uri.get('entity_id')] = {}
            entities[invalid_uri.get('entity_id')].update({
                'type': invalid_uri.get('entity_type'),
                'fields': [invalid_uri.get('field')],
            })

    # Build rows.
    rows = []
    packages = {}
    resources = {}
    for entity_id in entities:
        # Load entity and cache them.
        entity_dict = {}
        parent_entity_dict = {}
        invalid_uri = entities.get(entity_id)
        if invalid_uri.get('type') == 'dataset':
            if entity_id in packages:
                entity_dict = packages.get(entity_id)
            else:
                entity_dict = get_action('package_show')({}, {'id': entity_id})

                if config.get('org_id') and entity_dict.get('organization').get('id') != config.get('org_id'):
                    continue

                if entity_dict.get('type') == 'dataservice':
                    continue

                # Cache the result.
                packages[entity_id] = {}
                packages[entity_id].update(entity_dict)
        elif invalid_uri.get('type') == 'resource':
            if entity_id in resources:
                entity_dict = resources.get(entity_id)
                parent_entity_dict = packages.get(resources.get('package_id'))
            else:
                entity_dict = get_action('resource_show')({}, {'id': entity_id})
                # Cache the result.
                resources[entity_id] = {}
                resources[entity_id].update(entity_dict)

                if resources.get('package_id') in packages:
                    parent_entity_dict = packages.get(entity_dict.get('package_id'))
                else:
                    parent_entity_dict = get_action('package_show')({}, {'id': entity_dict.get('package_id')})
                    # Cache the result.
                    packages[entity_id] = {}
                    packages[entity_id].update(parent_entity_dict)

        if invalid_uri.get('type') == 'dataset':
            rows.append({
                'Dataset name': entity_dict.get('title', entity_dict.get('name', '')),
                'Link to dataset (URI)': url_for('dataset.read', id=entity_dict.get('id'), _external=True),
                'Resource name': '',
                'Link to resource': '',
                'Dataset creator': entity_dict.get('contact_creator', ''),
                'Point of contact (URI)': entity_dict.get('contact_point', ''),
                'List of fields with broken links': ', '.join(invalid_uri.get('fields', [])),
                'Organisation name': entity_dict.get('organization').get('title', ''),
            })
        elif invalid_uri.get('type') == 'resource':
            rows.append({
                'Dataset name': parent_entity_dict.get('title', parent_entity_dict.get('name', '')),
                'Link to dataset (URI)': url_for('dataset.read', id=parent_entity_dict.get('id'), _external=True),
                'Resource name': entity_dict.get('name', ''),
                'Link to resource': url_for('resource.read',
                                            resource_id=entity_dict.get('id'),
                                            id=parent_entity_dict.get('id'),
                                            package_type=parent_entity_dict.get('type'),
                                            _external=True
                                            ),
                'Dataset creator': parent_entity_dict.get('contact_creator', ''),
                'Point of contact (URI)': parent_entity_dict.get('contact_point', ''),
                'List of fields with broken links': ', '.join(invalid_uri.get('fields', [])),
                'Organisation name': parent_entity_dict.get('organization').get('title', ''),
            })

    return rows


def qdes_datasets_not_reviewed(context, config):
    dataset_review_period = qdes_get_dataset_review_period()
    start_time = datetime.utcnow() - relativedelta(months=dataset_review_period)
    query = Session.query(Package).join(PackageExtra) \
        .filter(PackageExtra.key == 'metadata_review_date') \
        .filter(PackageExtra.value != '') \
        .filter(Package.state == 'active') \
        .filter(cast(PackageExtra.value, DateTime) <= start_time.strftime('%Y-%m-%dT%H:%M:%S')) \
        .order_by(asc(PackageExtra.value))

    if config.get('org_id', None):
        query = query.filter(Package.owner_org == config.get('org_id'))

    packages = query.all()

    # Get list of organizations.
    organizations = _qdes_get_organization_list()

    # Build rows.
    rows = []
    for package in packages:
        pkg_dict = package.as_dict()
        extras = pkg_dict.get('extras')
        org_dict = _qdes_get_organization_dict_by_id(pkg_dict.get('owner_org'), organizations)

        rows.append({
            'Dataset name': pkg_dict.get('title', pkg_dict.get('name', '')),
            'Link to dataset (URI)': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'Dataset creator': extras.get('contact_creator', ''),
            'Point of contact (URI)': extras.get('contact_point', ''),
            'Metadata review date': qdes_render_date_with_offset(extras.get('metadata_review_date')),
            'Organisation name': org_dict.get('title', ''),
        })

    log.error(pformat(rows))

    return rows


def qdes_report_all(context, config):
    pass
