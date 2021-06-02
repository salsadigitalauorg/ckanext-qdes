import os
import csv
import time
import zipfile
import logging
import ckan.model as model

from ckan.common import g, _
from ckan.lib.helpers import render_datetime
from ckan.model import Session
from ckan.model.package import Package
from ckan.model.package_extra import PackageExtra
import ckan.plugins.toolkit as toolkit
from ckan.model.group import Group, Member
from ckan.model.api_token import ApiToken
from ckan.plugins.toolkit import config, get_action, asbool
from ckanext.qdes import constants
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import Response
from sqlalchemy import cast, asc, DateTime
from ckan.lib.dictization import model_dictize
from pprint import pformat
from urllib.parse import urlparse
from sqlalchemy.sql import text


from ckanext.vocabulary_services.secure.helpers import get_secure_vocabulary_record

log = logging.getLogger(__name__)


def utcnow_as_string():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')


def qdes_render_date_with_offset(date_value_utc, time=True):
    if not date_value_utc:
        return ''

    offset = render_datetime(date_value_utc, date_format='%z')

    if time:
        return render_datetime(date_value_utc, date_format='%Y-%m-%dT%H:%M:%S') + offset[:3] + ':' + offset[-2:]

    return render_datetime(date_value_utc, date_format='%Y-%m-%d')


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
    period = config.get('ckanext.qdes_schema.dataset_review_period', constants.DEFAULT_DATASET_REVIEW_PERIOD)
    # For some reason, dev database is return empty string.
    if not period:
        period = constants.DEFAULT_DATASET_REVIEW_PERIOD

    return int(period)


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
    contact_point_email = g.userobj.email
    contact_point =  get_action('get_secure_vocabulary_search')({'user': g.user}, {'vocabulary_name': 'point-of-contact', 'query': contact_point_email, 'limit': 1})
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

    if contact_point:
        query = query.filter(PackageExtra.key=='contact_point').filter(PackageExtra.value==contact_point[0].get('value'))
    packages = query.all()

    return packages


def qdes_review_due_date(review_date):
    u"""
    Return due from given date.
    """
    dataset_review_period = qdes_get_dataset_review_period()

    # Remove .000000 from the date time.
    if len(review_date.split('.')) > 1:
        review_date = review_date.split('.')[0]

    # Some values doesn't have time in it, let's add 00:00:00 to it.
    if review_date.find('T') == -1:
        review_date = review_date + 'T00:00:00'

    due_date = datetime.strptime(review_date, '%Y-%m-%dT%H:%M:%S') + relativedelta(months=dataset_review_period)
    return due_date.strftime('%Y-%m-%dT%H:%M:%S')


def qdes_generate_csv(title, rows):
    u"""
    Create a csv file to ./tmp directory and return the filename.
    """
    filename = ''
    if rows:
        date = render_datetime(datetime.utcnow(), date_format='%Y-%m-%d')
        filename = 'audit-' + str(date) + '-' + title + '.csv'

        fieldnames = []
        for key in rows[0]:
            fieldnames.append(key)

        with open(constants.TMP_PATH + '/' + filename, mode='w') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writeheader()
            for row in rows:
                csv_writer.writerow(row)

    return filename


def qdes_zip_csv_files(files):
    u"""
    Create a zip file to ./tmp directory and return the zip filename.
    """
    filename = 'backup-' + str(datetime.utcnow().timestamp()) + '.zip'
    zipf = zipfile.ZipFile(constants.TMP_PATH + '/' + filename, 'w', zipfile.ZIP_DEFLATED)

    for file in files:
        zipf.write(constants.TMP_PATH + '/' + file, file)

        # Delete the csv files.
        os.remove(constants.TMP_PATH + '/' + file)

    zipf.close()

    return filename


def qdes_send_file_to_browser(file, type, remove=True):
    u"""
    Send the file to browser, and remove it.
    """
    with open(file, 'rb') as f:
        data = f.readlines()

    if remove:
        os.remove(file)

    return Response(data, headers={
        'Content-Type': 'application/zip' if type == 'zip' else 'text/csv',
        'Content-Disposition': 'attachment; filename=%s;' % os.path.basename(file)
    })


def get_api_tokens():
    query = Session.query(ApiToken)
    tokens = [
        {
            "user_name": token.owner.name,
            "user_email": token.owner.email,
            "token_id": token.id,
            "token_name": token.name,
            "token_last_access": token.last_access
        }
        for token in query.all()
    ]
    return tokens


def qdes_activity_stream_detail(activity_type):
    """
    Performs some replacement and rearrangement of the activity type for display in the activity notification email
    """
    activity_type = activity_type.replace('organization', _('organization'))
    activity_type = activity_type.replace('package', 'dataset')
    activity_type = activity_type.split()
    activity_type.reverse()

    return ' '.join(activity_type)


def qdes_add_activity_for_private_pkg(context, pkg_dict, activity_type):
    if pkg_dict.get('private'):
        model = context['model']
        session = context['session']
        user = context['user']

        pkg = model.Package.get(pkg_dict['id'])

        user_obj = model.User.by_name(user)
        if user_obj:
            user_id = user_obj.id
        else:
            user_id = 'not logged in'

        activity = pkg.activity_stream_item(activity_type, user_id)
        session.add(activity)

        return pkg_dict

    return


def get_publication_status_history(pkg_id):
    activity_stream = model.activity.package_activity_list(pkg_id, None, None)

    history = []
    last_status = ''
    for activity in activity_stream:
        pkg = activity.data.get('package')
        if pkg:
            status = pkg.get('publication_status', '')
            if not last_status == status:
                last_status = status
                history.append({
                    'date': qdes_render_date_with_offset(pkg.get('metadata_modified')),
                    'publication_status': status
                })

    return history


def get_banner_image():
    banner_image = config.get('ckanext.qdes.banner_image', '') or ''
    url = ''
    if banner_image:
        if urlparse(banner_image).netloc:
            # Link url
            url = banner_image
        else:
            # File upload
            url = '/uploads/qdes-admin/' + banner_image

    return {
        'image_url': url
    }


def get_recently_created_datasets(limit=5):
    q = model.Session.query(model.Package)
    q = q.filter(model.Package.state == model.core.State.ACTIVE)
    q = q.filter(model.Package.private == False)
    q = q.order_by(model.Package.metadata_created.desc())
    q = q.limit(limit)

    return [dataset.as_dict() for dataset in q.all()]


def get_most_popular_datasets(limit=5):
    q = model.Session.query(model.Package)
    q = q.join(model.TrackingSummary, model.TrackingSummary.package_id == model.Package.id)
    q = q.filter(model.TrackingSummary.package_id != '~~not~found~~')
    q = q.filter(model.Package.state == model.core.State.ACTIVE)
    q = q.filter(model.Package.private == False)
    q = q.order_by(model.TrackingSummary.tracking_date.desc())
    q = q.order_by(model.TrackingSummary.running_total.desc())
    q = q.limit(limit)

    return [dataset.as_dict() for dataset in q.all()]


def get_dataset_totals_by_type(dataset_type):
    return get_action('package_search')({}, {"rows": 1, "fq": f"dataset_type:{dataset_type}"})['count']


def qdes_tracking_enabled():
    return asbool(config.get('ckan.qdes.tracking_enabled', 'false'))
