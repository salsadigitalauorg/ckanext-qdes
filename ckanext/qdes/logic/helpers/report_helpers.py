import logging

from ckan.lib.helpers import url_for
from ckanext.vocabulary_services.secure.helpers import get_secure_vocabulary_record

log = logging.getLogger(__name__)


def _qdes_extract_point_of_contact(pos_id, field):
    if pos_id is not None:
        vocab = get_secure_vocabulary_record('point-of-contact', pos_id)
        return vocab.get(field, '')

    return ''


def get_point_of_contact(pos_id=None):
    """
    Different from the `_qdes_extract_point_of_contact` function
    above - it returns the full point of contact dict so that
    you only need to lookup the secure CV once, and then use the
    dict properties instead of looking up the secure CV per property
    you want to use
    """
    if pos_id:
        return get_secure_vocabulary_record('point-of-contact', pos_id)


def invalid_uri_csv_row(invalid_uri, package, resource={}):
    """
    Helper function to return a dict for a CSV row
    Can be used for either package or resource rows
    """
    # Setup any values we use multiple times below
    package_id = package.get('id', None)

    # Only lookup point of contact once, instead of twice within the dict below
    contact_point = package.get('contact_point', None)

    # Package *SHOULD* have a `contact_point` set, but just in case
    point_of_contact = get_point_of_contact(contact_point) if contact_point else {}

    resource_uri = url_for('resource.read',
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
