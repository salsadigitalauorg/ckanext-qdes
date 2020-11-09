import ckan.plugins.toolkit as toolkit
import logging

from ckan.model import Session
from ckan.model.package import Package
from ckan.model.group import Group
from ckan.lib.helpers import url_for, render_datetime
from ckanext.qdes.helpers import qdes_render_date_with_offset
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import asc, cast, Date
from pprint import pformat

log = logging.getLogger(__name__)


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
    organizations = Session.query(Group).filter(Group.is_organization == True).all()

    # Build rows.
    rows = []
    for package in packages:
        pkg_dict = package.as_dict()
        extras = pkg_dict.get('extras')
        org_dict = _qdes_get_organization_dict_by_id(pkg_dict.get('owner_org'), organizations)

        rows.append({
            'Dataset name': pkg_dict.get('name', ''),
            'Link to dataset (URI)': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'Dataset creator': extras.get('contact_creator', ''),
            'Point of contact (URI)': extras.get('contact_point', ''),
            'Dataset creation date': qdes_render_date_with_offset(pkg_dict.get('metadata_created')),
            'Dataset update date': qdes_render_date_with_offset(pkg_dict.get('metadata_modified')),
            'Organisation name': org_dict.get('name', ''),
        })

    return rows


def qdes_empty_recommended(context, config):
    pass


def qdes_invalid_uris(context, config):
    pass


def qdes_datasets_not_reviewed(context, config):
    pass


def qdes_report_all(context, config):
    pass
