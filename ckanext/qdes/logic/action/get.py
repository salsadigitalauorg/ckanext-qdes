import logging
import ckan.authz as authz
import ckan.plugins.toolkit as toolkit
import ckanext.qdes.logic.helpers.report_helpers as qdes_logic_helpers
import ckanext.scheming.helpers as scheming_helpers

from ckan.lib.helpers import url_for
from ckan.model import Session
from ckanext.qdes import helpers
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pprint import pformat
from sqlalchemy import func

check_access = toolkit.check_access
get_action = toolkit.get_action
qdes_render_date_with_offset = helpers.qdes_render_date_with_offset
log = logging.getLogger(__name__)


def review_datasets(context, data_dict):
    if not authz.is_sysadmin(context.get('user')) and not authz.has_user_permission_for_some_org(context.get('user'), 'create_dataset'):
        return {'success': False, 'msg': toolkit._('Not authorized')}

    model = context['model']
    try:
        cls = model.PackageExtra
        dataset_review_period = data_dict.get('dataset_review_period', helpers.qdes_get_dataset_review_period())
        review_date = datetime.utcnow() - relativedelta(months=dataset_review_period)

        query = model.PackageExtra().Session.query(cls) \
            .filter(cls.key == 'metadata_review_date') \
            .filter(func.date(cls.value) >= func.date(review_date)) \
            .filter(cls.state == 'active')

        return [get_action('package_show')(context, {'id': package_extra.package_id, }) for package_extra in query.all()]
    except Exception as e:
        log.error(str(e))

    return []


def qdes_datasets_not_updated(context, config={}):
    u"""
    List of all datasets that have been created
    but have not been updated in 12 months.
    """
    # Check access for sysadmin user's only
    check_access('config_option_update', context, None)

    # Get org_id config.
    org_id = config.get('org_id', None)

    # Get dataset not updated.
    packages = qdes_logic_helpers.qdes_get_list_of_dataset_not_updated(org_id)

    # Get list of organizations.
    organizations = qdes_logic_helpers.qdes_get_organization_list()

    # Build rows.
    rows = []
    point_of_contacts = {}
    for package in packages:
        pkg_dict = package.as_dict()
        extras = pkg_dict.get('extras')
        org_dict = qdes_logic_helpers.qdes_get_organization_dict_by_id(pkg_dict.get('owner_org'), organizations)

        # Load and cache point of contacts.
        contact_point_pos = extras.get('contact_point', None)
        if not contact_point_pos in point_of_contacts:
            point_of_contacts[contact_point_pos] = qdes_logic_helpers \
                .get_point_of_contact(context, contact_point_pos) if contact_point_pos else {}

        rows.append({
            'Dataset name': pkg_dict.get('title', pkg_dict.get('name', '')),
            'Link to dataset (URI)': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'Dataset creator': extras.get('contact_creator', ''),
            'Point of contact - name': point_of_contacts.get(contact_point_pos).get('Name', ''),
            'Point of contact - email': point_of_contacts.get(contact_point_pos).get('Email', ''),
            'Dataset creation date': qdes_render_date_with_offset(pkg_dict.get('metadata_created')),
            'Dataset update date': qdes_render_date_with_offset(pkg_dict.get('metadata_modified')),
            'Organisation name': org_dict.get('title', ''),
        })

    return rows


def qdes_datasets_with_empty_recommended_fields(context, config={}):
    u"""
    List of all datasets that have no values against recommended metadata fields.
    """
    # Check access for sysadmin user's only
    check_access('config_option_update', context, None)

    # Get org_id config.
    org_id = config.get('org_id', None)

    # Get list of recommended fields.
    dataset_scheme = scheming_helpers.scheming_get_dataset_schema('dataset')
    dataset_recommended_fields = qdes_logic_helpers \
        .qdes_get_recommended_dataset_fields(dataset_scheme, 'dataset_fields')
    dataset_resource_recommended_fields = qdes_logic_helpers \
        .qdes_get_recommended_dataset_fields(dataset_scheme, 'resource_fields')

    # Build rows.
    rows = []
    i = 1
    has_result = True
    point_of_contacts = {}
    while has_result:
        packages = get_action('current_package_list_with_resources')(context, {'limit': 10, 'offset': i})
        if not packages:
            has_result = False
        else:
            i += 1

        for package in packages:
            # Load and cache point of contacts.
            contact_point_pos = package.get('contact_point', None)
            if not contact_point_pos in point_of_contacts:
                point_of_contacts[contact_point_pos] = qdes_logic_helpers \
                    .get_point_of_contact(context, contact_point_pos) if contact_point_pos else {}

            # Get package organization.
            pkg_org = package.get('organization')

            # Filter based on org_id or package type.
            if (org_id and pkg_org.get('id') != org_id) or package.get('type') == 'dataservice':
                continue

            # Get missing value fields.
            missing_values = qdes_logic_helpers \
                .qdes_check_recommended_field_value(package, dataset_recommended_fields)

            # Get contact point.
            contact_point = point_of_contacts.get(contact_point_pos)

            # Build row.
            row = qdes_logic_helpers \
                .qdes_empty_recommended_field_row(package, contact_point, missing_values)
            rows.append(row)

            # Check dataset resource metadata fields.
            for resource in package.get('resources', []):
                # Get missing value fields.
                missing_values = qdes_logic_helpers \
                    .qdes_check_recommended_field_value(resource, dataset_resource_recommended_fields)

                # Build row.
                row = qdes_logic_helpers \
                    .qdes_empty_recommended_field_row(package, contact_point, missing_values, resource)
                rows.append(row)


    return rows


def qdes_datasets_with_invalid_urls(context, config={}):
    u"""
    List of all datasets with broken links to resources.
    """
    # Check access for sysadmin user's only
    check_access('config_option_update', context, None)

    org_id = config.get('org_id', None)

    # Get list of invalid uris.
    entities = qdes_logic_helpers.qdes_get_list_of_invalid_uris()

    # Build rows.
    rows = []
    packages = {}
    resources = {}
    point_of_contacts = {}
    for entity_id, invalid_uri in entities.items():
        # Load entity and cache them.
        entity_dict = {}
        parent_entity_dict = {}

        if invalid_uri.get('type') == 'dataset':
            entity_dict = packages.get(entity_id, None)
            if not entity_dict:
                try:
                    entity_dict = get_action('package_show')(context, {'id': entity_id})

                    if (org_id and entity_dict.get('owner_org') != org_id) \
                            or entity_dict.get('type') == 'dataservice':
                        continue
                except Exception as e:
                    log.error(str(e), exc_info=True)
                    continue

                # Cache the result.
                packages[entity_id] = entity_dict
        elif invalid_uri.get('type') == 'resource':
            if entity_id in resources:
                entity_dict = resources.get(entity_id)
                parent_entity_dict = packages.get(resources.get('package_id'))
            else:
                try:
                    entity_dict = get_action('resource_show')(context, {'id': entity_id})

                    parent_entity_dict = packages.get(entity_dict.get('package_id'), None)

                    if not parent_entity_dict:
                        parent_entity_dict = get_action('package_show')(context, {'id': entity_dict.get('package_id')})

                        if org_id and parent_entity_dict.get('owner_org') != org_id:
                            continue

                        # Cache the package result.
                        packages[entity_id] = parent_entity_dict

                    # Cache the resource result.
                    resources[entity_id] = entity_dict
                except Exception as e:
                    log.error(str(e), exc_info=True)
                    continue

        # Load and cache point of contacts.
        contact_point_pos = entity_dict.get('contact_point', None)
        if not contact_point_pos in point_of_contacts:
            point_of_contacts[contact_point_pos] = qdes_logic_helpers \
                .get_point_of_contact(context, contact_point_pos) if contact_point_pos else {}

        if invalid_uri.get('type') == 'dataset':
            # Moved to helper function to reduce function size and avoid duplication
            rows.append(qdes_logic_helpers.invalid_uri_csv_row(invalid_uri, point_of_contacts[contact_point_pos] ,entity_dict))
        elif invalid_uri.get('type') == 'resource':
            # Moved to helper function to reduce function size and avoid duplication
            rows.append(qdes_logic_helpers.invalid_uri_csv_row(invalid_uri, point_of_contacts[contact_point_pos], parent_entity_dict, entity_dict))

    return rows


def qdes_datasets_not_reviewed(context, config):
    u"""
    List of all datasets with over 12 months review date.
    """
    # Check access for sysadmin user's only
    check_access('config_option_update', context, None)

    # Get org_id config.
    org_id = config.get('org_id', None)

    # Get list of datasets.
    packages = qdes_logic_helpers.qdes_get_list_of_datasets_not_reviewed(org_id)

    # Get list of organizations.
    organizations = qdes_logic_helpers.qdes_get_organization_list()

    # Build rows.
    rows = []
    point_of_contacts = {}
    for package in packages:
        pkg_dict = package.as_dict()
        extras = pkg_dict.get('extras')
        org_dict = qdes_logic_helpers \
            .qdes_get_organization_dict_by_id(pkg_dict.get('owner_org'), organizations)

        # Load and cache point of contacts.
        contact_point_pos = extras.get('contact_point', None)
        if not contact_point_pos in point_of_contacts:
            point_of_contacts[contact_point_pos] = qdes_logic_helpers \
                .get_point_of_contact(context, contact_point_pos) if contact_point_pos else {}

        rows.append({
            'Dataset name': pkg_dict.get('title', pkg_dict.get('name', '')),
            'Link to dataset (URI)': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'Dataset creator': extras.get('contact_creator', ''),
            'Point of contact - name': point_of_contacts.get(contact_point_pos).get('Name', ''),
            'Point of contact - email': point_of_contacts.get(contact_point_pos).get('Email', ''),
            'Metadata review date': qdes_render_date_with_offset(extras.get('metadata_review_date')),
            'Organisation name': org_dict.get('title', ''),
        })

    return rows


def qdes_report_all(context, config):
    # Check access for sysadmin user's only
    check_access('config_option_update', context, None)

    org_id = config.get('org_id', None)

    available_actions = config.get('available_actions', [])

    csv_files = []
    for report in available_actions:
        csv_file = helpers.qdes_generate_csv(available_actions.get(report), get_action(report)({}, {'org_id': org_id}))

        if csv_file:
            csv_files.append(csv_file)
    if csv_files:
        return helpers.qdes_zip_csv_files(csv_files)

    return []
