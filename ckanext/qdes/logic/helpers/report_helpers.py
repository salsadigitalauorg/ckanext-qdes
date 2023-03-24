import logging

from ckan.lib.helpers import url_for
from ckan.model import Session
from ckan.model.group import Group
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
from ckanext.qdes.helpers import qdes_get_dataset_review_period
from ckanext.invalid_uris.model import InvalidUri
from ckanext.vocabulary_services.secure.helpers import get_secure_vocabulary_record
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import asc, cast, DateTime

log = logging.getLogger(__name__)


def qdes_extract_point_of_contact(pos_id, field):
    """DEPRECATED"""
    if pos_id is not None:
        vocab = get_secure_vocabulary_record('point-of-contact', pos_id)
        return vocab.get(field, '')

    return ''


def get_point_of_contact(context, pos_id=None):
    """
    Different from the `_qdes_extract_point_of_contact` function
    above - it returns the full point of contact dict so that
    you only need to lookup the secure CV once, and then use the
    dict properties instead of looking up the secure CV per property
    you want to use
    """
    if pos_id:
        return get_secure_vocabulary_record('point-of-contact', pos_id, context)


def qdes_get_organization_list():
    """
    Return a list of
    """
    return Session.query(Group).filter(Group.is_organization == True).all()


def qdes_get_organization_dict_by_id(id, organizations):
    """
    Return a dict from the organizations dict by id,
    useful to pull data from cache data in local variable.
    """
    for organization in organizations:
        org_dict = organization.as_dict()
        if org_dict.get('id') == id:
            return org_dict

    return {}


def qdes_get_list_of_dataset_not_updated(org_id=None):
    """
    Return a list of dataset that not updated in last 12 months.
    """
    # Setup last modify date threshold.
    last_modify_date_threshold = datetime.utcnow() - relativedelta(months=12)

    # Build query.
    query = Session.query(Package) \
        .filter(Package.state == 'active') \
        .filter(Package.metadata_modified <= last_modify_date_threshold) \
        .order_by(asc(Package.metadata_modified))

    # Filter by organization if org_id exist.
    if org_id:
        query = query.filter(Package.owner_org == org_id)

    return query.all()


def qdes_get_recommended_dataset_fields(scheme, field_group):
    """
    Get a list of recommended fields from provided schema.
    """
    recommended_fields = []
    for field in scheme[field_group]:
        if field.get('recommended', False):
            recommended_fields.append(field)

    return recommended_fields


def qdes_check_recommended_field_value(entity_dict, recommended_fields):
    """
    Return a list of missing value from provided recommended fields.
    """
    missing_values = []
    for field in recommended_fields:
        f_name = field.get('field_name')
        value = str(entity_dict.get(f_name, ''))
        if not value.strip():
            missing_values.append(f_name)

    return missing_values


def qdes_empty_recommended_field_row(package, point_of_contact, missing_values, resource={}):
    """
    Return row for empty recommended field.
    """
    resource_uri = url_for('dataset_resource.read',
                           resource_id=resource.get('id'),
                           id=package.get('id'),
                           package_type=package.get('type'),
                           _external=True
                           ) if resource else ''
    return {
        'Dataset name': package.get('title', package.get('name', '')),
        'Link to dataset (URI)': url_for('dataset.read', id=package.get('id'), _external=True),
        'Resource name': resource.get('name', ''),
        'Link to resource': resource_uri,
        'Dataset creator': package.get('contact_creator', ''),
        'Point of contact - name': point_of_contact.get('Name', ''),
        'Point of contact - email': point_of_contact.get('Email', ''),
        'List of recommended fields without values': ', '.join(missing_values),
        'Organisation name': package.get('organization').get('title', ''),
    }


def qdes_get_list_of_invalid_uris():
    """
    Helper function to return a list of entities that have invalid uri.
    """
    # Get list of invalid uris.
    invalid_uris = Session.query(InvalidUri).all()

    # Build package list.
    entities = {}
    for uri in invalid_uris:
        if uri.entity_id in entities:
            entities[uri.entity_id]['fields'].append(uri.field)
        else:
            entities[uri.entity_id] = {
                'type': uri.entity_type,
                'fields': [uri.field],
            }

    return entities


def invalid_uri_csv_row(invalid_uri, point_of_contact, package, resource={}):
    """
    Helper function to return a dict for a CSV row
    Can be used for either package or resource rows
    """
    # Setup any values we use multiple times below
    package_id = package.get('id', None)

    resource_uri = url_for('dataset_resource.read',
                           resource_id=resource.get('id'),
                           id=package.get('id'),
                           package_type=package.get('type'),
                           _external=True
                           ) if resource else ''

    return {
        'Dataset name': package.get('title', package.get('name', '')),
        'Link to dataset (URI)': url_for('dataset.read', id=package_id, _external=True),
        'Resource name': resource.get('name', ''),
        'Link to resource': resource_uri,
        'Dataset creator': package.get('contact_creator', ''),
        'Point of contact - name': point_of_contact.get('Name', ''),
        'Point of contact - email': point_of_contact.get('Email', ''),
        'List of fields with broken links': ', '.join(invalid_uri.get('fields', [])),
        'Organisation name': package.get('organization').get('title', ''),
    }


def qdes_get_list_of_datasets_not_reviewed(org_id=None):
    """
    Return a list of dataset that not reviewed within the dataset review period.
    """
    # Load ckanext.qdes_schema.dataset_review_period config.
    dataset_review_period = qdes_get_dataset_review_period()

    start_time = datetime.utcnow() - relativedelta(months=dataset_review_period)
    query = Session.query(Package).join(PackageExtra) \
        .filter(PackageExtra.key == 'metadata_review_date') \
        .filter(PackageExtra.value != '') \
        .filter(Package.state == 'active') \
        .filter(cast(PackageExtra.value, DateTime) <= start_time.strftime('%Y-%m-%dT%H:%M:%S')) \
        .order_by(asc(PackageExtra.value))

    if org_id:
        query = query.filter(Package.owner_org == org_id)

    return query.all()
