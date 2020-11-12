import os
import csv
import time
import zipfile
import logging

from ckan.common import g
from ckan.lib.helpers import render_datetime
from ckan.model import Session
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
from ckan.model.group import Group, Member
from ckan.plugins.toolkit import config
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import Response
from sqlalchemy import cast, asc, DateTime

from pprint import pformat

log = logging.getLogger(__name__)
tmp_dir = '/app/src/ckanext-qdes/ckanext/qdes/tmp/'

def utcnow_as_string():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')


def qdes_render_date_with_offset(date_value_utc):
    offset = render_datetime(date_value_utc, date_format='%z')
    return render_datetime(date_value_utc, date_format='%Y-%m-%dT%H:%M:%S') + offset[:3] + ':' + offset[-2:]


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
    return config.get('ckanext.qdes_schema.dataset_review_period', 1)


def qdes_review_datasets(org_id=None):
    u"""
    Return a list of datasets that need to be reviewed.
    """
    query = Session.query(Package).join(PackageExtra)

    # Filter by metadata review date.
    query = query.filter(PackageExtra.key == 'metadata_review_date') \
        .filter(PackageExtra.value != '') \
        .filter(Package.state == 'active') \
        .order_by(asc(PackageExtra.value))

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
    due_date = datetime.strptime(review_date, '%Y-%m-%dT%H:%M:%S') + relativedelta(months=dataset_review_period)
    return due_date.strftime('%Y-%m-%dT%H:%M:%S')

def qdes_generate_csv(title, rows):
    """
    Create a csv file to ./tmp directory and return the filename.
    """
    filename = ''
    if rows:
        filename = title + '-' + str(datetime.utcnow().timestamp()) + '.csv'

        fieldnames = []
        for key in rows[0]:
            fieldnames.append(key)

        with open(tmp_dir + filename, mode='w') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writeheader()
            for row in rows:
                csv_writer.writerow(row)

    return filename


def qdes_zip_csv_files(files):
    """
    Create a zip file to ./tmp directory and return the zip filename.
    """
    filename = 'backup-' + str(datetime.utcnow().timestamp()) + '.zip'
    zipf = zipfile.ZipFile(tmp_dir + filename, 'w', zipfile.ZIP_DEFLATED)

    for file in files:
        zipf.write(tmp_dir + file, file)

        # Delete the csv files.
        os.remove(tmp_dir + file)

    zipf.close()

    return filename


def qdes_send_file_to_browser(file, type):
    with open(os.path.join(tmp_dir, file), 'rb') as f:
        data = f.readlines()
    os.remove(os.path.join(tmp_dir, file))

    return Response(data, headers={
        'Content-Type': 'application/zip' if type == 'zip' else 'text/csv',
        'Content-Disposition': 'attachment; filename=%s;' % file
    })
