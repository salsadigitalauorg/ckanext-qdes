import logging
import time

from sqlalchemy import func, asc
from datetime import datetime
from dateutil.relativedelta import relativedelta
from ckan.plugins.toolkit import config
from ckan.common import g
from ckan.model import Session
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
from ckan.model.group import Group, Member

from pprint import pformat

log = logging.getLogger(__name__)


def qdes_organization_list(user_id=None):
    u"""
    Return a list of organization, if user_id not empty, it will return the org belong to the user.
    """
    organizations = []

    if user_id:
        if g.userobj.sysadmin:
            # In some cases, sysadmin can be deleted from organization, so get_groups will return []
            # but in this case, we need to query all of the organization available in the system.
            organizations = Session.query(Group).filter(Group.is_organization == True).all()
        else:
            organizations = g.userobj.get_groups('organization')

    return organizations


def qdes_get_dataset_review_period():
    return config.get('ckanext.qdes_schema.dataset_review_period', 12)


def qdes_review_datasets(org_id=None):
    u"""
    Return a list of dataset that need to be reviewed.
    """
    dataset_review_period = qdes_get_dataset_review_period()

    query = Session.query(Package).join(PackageExtra).order_by(asc(PackageExtra.value))

    # @todo, need to fix the filter.
    # Filter by metadata review date.
    start_time = datetime.utcnow() - relativedelta(months=dataset_review_period)
    query = query.filter(PackageExtra.key == 'metadata_review_date')
    #     .filter(datetime.strptime(PackageExtra.value, '%Y-%m-%dT%H:%M:%S').timestamp() <= start_time.timestamp())

    # Filter by organisations.
    admin_org = g.userobj.get_groups('organization', 'admin')
    editor_org = g.userobj.get_groups('organization', 'editor')
    admin_editor_user = not g.userobj.sysadmin and (admin_org or editor_org)
    if g.userobj.sysadmin and org_id:
        # Sysadmin can see all of packages, except they filter the organization.
        query = query.filter(Package.owner_org == org_id)
    elif admin_editor_user:
        organizations = set([])
        organizations.update(admin_org)
        organizations.update(editor_org)
        org_ids = []
        for organization in organizations:
            org_ids.append(organization.id)
        query = query.filter(Package.owner_org.in_(org_ids))

    packages = query.all()

    return packages


def qdes_review_due_date(review_date):
    u"""
    Return due from given date.
    """
    dataset_review_period = qdes_get_dataset_review_period()
    # due_date = datetime.strptime(review_date, '%Y-%m-%dT%H:%M:%S') + relativedelta(month=dataset_review_period)
    due_date = datetime.utcnow() + relativedelta(months=dataset_review_period)
    log.error('dataset_review_period %s' % due_date)
    return due_date.strftime('%Y-%m-%dT%H:%M:%S')
