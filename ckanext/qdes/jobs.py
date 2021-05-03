import ckan.plugins.toolkit as toolkit
import click
import logging
import os
import shutil

from ckan.common import config as cfg
from ckanext.qdes import helpers, constants
from datetime import datetime
from dateutil.relativedelta import relativedelta

get_action = toolkit.get_action
render = toolkit.render
log = logging.getLogger(__name__)


def review_datasets(data_dict={}):
    site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
    context = {u'user': site_user[u'name']}

    # Action 'get_review_datasets' defaults to using  config value 'ckanext.qdes_schema.dataset_review_period' or 12 months if not set
    review_datasets = get_action('get_review_datasets')(context, data_dict)

    contact_points = {}
    for review_dataset in review_datasets:
        contact_point = review_dataset.get('contact_point', None)
        datasets = contact_points.get(contact_point, [])
        title = review_dataset.get('title')
        name = review_dataset.get('name')
        url = toolkit.url_for('{}.read'.format(review_dataset.get('type', None)), id=name, _external=True)
        dataset = {'title': title, 'url': url}
        # Only add dataset if it does not already exist in datasets list
        datasets.append(dataset) if dataset not in datasets else datasets
        contact_points[contact_point] = datasets

    for contact_point in contact_points:
        datasets = contact_points[contact_point]
        # Only email contact point if there are datasets
        if len(datasets) > 0:
            contact_point_data = get_action('get_secure_vocabulary_record')(context, {'vocabulary_name': 'point-of-contact', 'query': contact_point})
            if contact_point_data:
                recipient_name = contact_point_data.get('Name', '')
                recipient_email = contact_point_data.get('Email', '')
                subject = render('emails/subject/review_datasets.txt')
                body = render('emails/body/review_datasets.txt', {'datasets': datasets})
                body_html = render('emails/body/review_datasets.html', {'datasets': datasets})
                toolkit.enqueue_job(toolkit.mail_recipient, [recipient_name, recipient_email, subject, body, body_html])


def generate_reports():
    # Get last run.
    last_run_timestamp = cfg.get('ckanext.qdes_schema.dataset_audit_period_last_run', None)
    if last_run_timestamp:
        last_run_date = datetime.fromtimestamp(float(last_run_timestamp))

        log.debug('last_run_date: ' + str(last_run_date))

        # Validate last run against dataset_audit_period.
        audit_period = int(cfg.get('ckanext.qdes_schema.dataset_audit_period', 1))
        audit_period_date = datetime.utcnow() - relativedelta(months=audit_period)

        if last_run_date >= audit_period_date:
            click.secho(u"Reports not generated, last run date within audit_period_date " + str(audit_period_date), fg=u"red")
            return

    site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
    context = {u'user': site_user[u'name']}

    # Generate csv files.
    available_actions = {
        'qdes_datasets_not_updated': 'not-updated',
        'qdes_datasets_with_empty_recommended_fields': 'recommended',
        'qdes_datasets_with_invalid_urls': 'invalid-urls',
        'qdes_datasets_not_reviewed': 'not-reviewed',
    }
    csv_files = []
    for report in available_actions:
        csv_file = helpers.qdes_generate_csv(available_actions.get(report), get_action(report)(context, {'org_id': None}))

        if csv_file:
            csv_files.append(csv_file)

    if not csv_files:
        click.secho(u"No report generated, data is empty.", fg=u"green")
        return

    # Create the destination directory.
    try:
        reports_dir = constants.REPORT_PATH
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        current_backup_dir = reports_dir + '/' + datetime.today().strftime('%Y-%m-%d')
        if os.path.exists(current_backup_dir):
            shutil.rmtree(current_backup_dir)

        os.makedirs(current_backup_dir)
    except Exception as e:
        log.error(str(e))
        return

    # Move csv files to destination.
    for csv_file in csv_files:
        shutil.move(constants.TMP_PATH + '/' + csv_file, current_backup_dir + '/' + csv_file)

    # Remove older backup.
    config_value = int(cfg.get('ckanext.qdes.max_old_backup', 50))
    reports_dir = os.listdir(constants.REPORT_PATH)
    reports_dir.sort(reverse=True)

    if len(reports_dir) > config_value:
        del reports_dir[:config_value]
        for dir in reports_dir:
            shutil.rmtree(constants.REPORT_PATH + '/' + dir)

    # Update last run.
    last_run_date = datetime.utcnow()
    get_action('config_option_update')(context, {
        'ckanext.qdes_schema.dataset_audit_period_last_run': datetime.timestamp(last_run_date)
    })

    click.secho(u"Reports generated", fg=u"green")


def mark_as_reviewed(datasets):
    for package_id in datasets:
        try:
            site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
            context = {u'user': site_user[u'name'], 'defer_commit': False}
            get_action('package_patch')(context, {'id': package_id, 'metadata_review_date': helpers.utcnow_as_string()})
        except Exception as e:
            log.error(str(e))
