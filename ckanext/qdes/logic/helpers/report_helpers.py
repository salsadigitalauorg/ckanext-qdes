import logging

from ckan.lib.helpers import url_for
from ckan.model import Session
from ckan.model.group import Group
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
from ckan.model.resource import Resource
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
    you want to use.

    Returns an empty dict when pos_id is not provided, or when the
    vocabulary record cannot be resolved (e.g. stale/orphaned reference).
    """
    if pos_id:
        record = get_secure_vocabulary_record('point-of-contact', pos_id, context)
        if record is not None:
            return record

    return {}


def qdes_get_organization_list():
    """
    Return a list of
    """
    # SQLAlchemy: '== True' on a mapped column is required to build IS TRUE/= true
    # SQL, not a Python truthiness check. `is True` / bare truthiness do not work here.
    return Session.query(Group).filter(Group.is_organization == True).all()  # noqa: E712


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


def _qdes_package_dict_with_organization(package):
    package_dict = package.as_dict()

    organization = None
    if package.owner_org:
        organization = Session.query(Group).filter(Group.id == package.owner_org).first()

    package_dict['organization'] = organization.as_dict() if organization else {}

    return package_dict


def qdes_get_invalid_uri_entities(org_id=None):
    """
    Return invalid URI entities with package/resource data in bulk.

    This avoids calling package_show/resource_show repeatedly.
    """

    entities = []

    # Dataset-level invalid URIs.
    dataset_rows = Session.query(
        InvalidUri,
        Package
    ).join(
        Package,
        Package.id == InvalidUri.entity_id
    ).filter(
        InvalidUri.entity_type == 'dataset'
    ).filter(
        Package.state == 'active'
    ).filter(
        Package.type != 'dataservice'
    ).order_by(
        Package.title,
        InvalidUri.id
    )

    if org_id:
        dataset_rows = dataset_rows.filter(Package.owner_org == org_id)

    # Group the flat rows by entity_id.
    dataset_groups = {}
    for invalid_uri, package in dataset_rows.all():
        entity_id = invalid_uri.entity_id
        if entity_id not in dataset_groups:
            dataset_groups[entity_id] = {
                'invalid_uri': {
                    'type': 'dataset',
                    'fields': [],
                    'uris': [],
                },
                'package': _qdes_package_dict_with_organization(package),
                'resource': {},
            }
        dataset_groups[entity_id]['invalid_uri']['fields'].append(invalid_uri.field)
        dataset_groups[entity_id]['invalid_uri']['uris'].append(invalid_uri.uri)

    for entity_id in dataset_groups:
        entities.append(dataset_groups[entity_id])

    # Resource-level invalid URIs.
    resource_rows = Session.query(
        InvalidUri,
        Package,
        Resource
    ).join(
        Resource,
        Resource.id == InvalidUri.entity_id
    ).join(
        Package,
        Package.id == Resource.package_id
    ).filter(
        InvalidUri.entity_type == 'resource'
    ).filter(
        Resource.state == 'active'
    ).filter(
        Package.state == 'active'
    ).filter(
        Package.type != 'dataservice'
    ).order_by(
        Package.title,
        InvalidUri.id
    )

    if org_id:
        resource_rows = resource_rows.filter(Package.owner_org == org_id)

    # Group the flat rows by entity_id.
    resource_groups = {}
    for invalid_uri, package, resource in resource_rows.all():
        entity_id = invalid_uri.entity_id
        if entity_id not in resource_groups:
            resource_groups[entity_id] = {
                'invalid_uri': {
                    'type': 'resource',
                    'fields': [],
                    'uris': [],
                },
                'package': _qdes_package_dict_with_organization(package),
                'resource': resource.as_dict(),
            }
        resource_groups[entity_id]['invalid_uri']['fields'].append(invalid_uri.field)
        resource_groups[entity_id]['invalid_uri']['uris'].append(invalid_uri.uri)

    for entity_id in resource_groups:
        entities.append(resource_groups[entity_id])

    return entities


def invalid_uri_csv_row(invalid_uri, point_of_contact, package, resource=None):
    """
    Helper function to return a dict for a CSV row
    Can be used for either package or resource rows
    """
    if resource is None:
        resource = {}

    package_id = package.get('id', None)
    extras = package.get('extras', {}) or {}

    resource_uri = url_for('dataset_resource.read',
                           resource_id=resource.get('id'),
                           id=package.get('id'),
                           package_type=package.get('type'),
                           _external=True
                           ) if resource else ''

    uris = invalid_uri.get('uris', []) or []
    fields = invalid_uri.get('fields', []) or []

    invalid_url_pairs = []
    for i in range(len(fields)):
        invalid_url_pairs.append({
            'field': fields[i],
            'url': uris[i] if i < len(uris) else '',
        })

    return {
        'Dataset name': package.get('title', package.get('name', '')),
        'Link to dataset (URI)': url_for('dataset.read', id=package_id, _external=True),
        'Resource name': resource.get('name', ''),
        'Link to resource': resource_uri,
        'Dataset creator': extras.get('contact_creator', ''),
        'Point of contact - name': point_of_contact.get('Name', ''),
        'Point of contact - email': point_of_contact.get('Email', ''),
        'Invalid URLs': invalid_url_pairs,
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
