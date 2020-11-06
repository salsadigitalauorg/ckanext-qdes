import ckan.plugins.toolkit as toolkit
import logging

from ckan.model import Session
from ckan.model.package import Package
from ckan.model.group import Group
from ckan.lib.helpers import url_for, render_datetime
from ckanext.qdes.helpers import qdes_render_date_with_offset
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import asc
from pprint import pformat

log = logging.getLogger(__name__)


def _qdes_get_organization_dict_by_id(id, organizations):
    for organization in organizations:
        org_dict = organization.as_dict()
        if org_dict.get('id') == id:
            return org_dict

    return []

def qdes_datasets_not_updated(context, config):
    last_modify_date_threshold = datetime.utcnow() - relativedelta(months=1)

    query = Session.query(Package) \
        .filter(Package.state == 'active') \
        .filter(Package.metadata_modified < last_modify_date_threshold) \
        .order_by(asc(Package.metadata_modified))

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
            'dataset_name': pkg_dict.get('name'),
            'url': url_for('dataset.read', id=pkg_dict.get('id'), _external=True),
            'point_of_contact': '',
            'dataset_creation_date': qdes_render_date_with_offset(pkg_dict.get('metadata_created')),
            'dataset_update_date': qdes_render_date_with_offset(pkg_dict.get('metadata_modified')),
            'organisation_name': org_dict.get('name'),
        })

    log.error(pformat(rows))

    return rows


def qdes_empty_recommended(context, config):
    pass


def qdes_invalid_uris(context, config):
    pass


def qdes_datasets_not_reviewed(context, config):
    pass


def qdes_report_all(context, config):
    pass
