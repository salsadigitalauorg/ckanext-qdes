import ckan.plugins.toolkit as toolkit
import ckan.model as model
import click
import logging
import os
import shutil
import requests

from ckan.common import config as cfg
from ckanext.qdes import helpers, constants
from datetime import datetime
from dateutil.relativedelta import relativedelta
from ckanext.scheming.plugins import SchemingDatasetsPlugin
from ckan.logic.schema import default_update_package_schema

get_action = toolkit.get_action
render = toolkit.render
config = toolkit.config
enqueue_job = toolkit.enqueue_job
mail_recipient = toolkit.mail_recipient
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
                # Improvements for job worker visibility when troubleshooting via logs
                job_title = f'Review datasets: Sending email to {recipient_name}'
                enqueue_job(mail_recipient, [recipient_name, recipient_email, subject, body, body_html], title=job_title)


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
    try:
        if datasets == None or len(datasets) == 0:
            return
        log.info(f'Starting to mark {len(datasets)} datasets as reviewed')
        site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
        context = {u'user': site_user[u'name'], 'ignore_auth': True, 'defer_commit': True, 'return_id_only': True}
        metadata_review_date = helpers.utcnow_as_string()
        for package_id in datasets:
            try:
                log.info(f'Marking dataset {package_id} as reviewed')
                get_action('package_patch')(context, {'id': package_id, 'metadata_review_date': metadata_review_date})
            except Exception as e:
                log.error(str(e))
        # Because we set defer_commit = True we need to make sure we commit all the updates to the model.repo
        log.info(f'Committing updates to database')
        model.repo.commit()
        log.info(f'Finished marking {len(datasets)} datasets as reviewed')
    except Exception as e:
        log.error(str(e))


def ckan_worker_job_monitor():
    monitor_url = os.environ.get('MONITOR_QDES_JOBWORKER')
    try:
        if monitor_url:
            log.info(f'Sending notification for CKAN worker job monitor')
            requests.get(monitor_url, timeout=10)
            log.info(f'Successfully sent notification for CKAN worker job monitor')
        else:
            log.error(f'The env variable MONITOR_QDES_JOBWORKER is not set for CKAN worker job monitor')
    except requests.RequestException as e:
        log.error(f'Failed to send ckan worker job monitor notification to {monitor_url}')
        log.error(str(e))

def validate_datasets():
    # Get site default user
    user = get_action('get_site_user')({'ignore_auth': True})
    context = {
        'user': user.get('name'),
        'auth_user_obj': user,
        'ignore_auth': True,
    }
    p = SchemingDatasetsPlugin.instance
    # Get all public datasets
    dataset_list = get_action('package_list')(context, {})
    validation_errors = []
    exclude_from_validation = toolkit.aslist(config.get('ckanext.qdes.validation_error_exclude_metadata'))
    # Loop through all datasets and validate each one
    for dataset in dataset_list:
        try:
            data_dict = get_action('package_show')(context, {"id": dataset})
            schema = default_update_package_schema()
            pkg_data, pkg_errors = p.validate(context, data_dict, schema, 'package_update')
            if pkg_errors:
                log.error("Validation errors for dataset: {}".format(dataset))
                # Exclude certain fields from dataset validation errors
                pkg_errors = {key: error for key, error in pkg_errors.items() if key not in exclude_from_validation}
                if pkg_errors.get('resources'):
                    pkg_errors.pop('resources')
                    # Validate resource, the above code will validate resource
                    # but it has no indication which resource is throwing an error,
                    # so we will re-run the validation for each resource.
                    resources = data_dict.get('resources', [])
                    if resources:
                        data_dict.pop('resources')
                        for res in resources:
                            data_dict['resources'] = [res]
                            pkg_data, resource_errors = p.validate(context, data_dict, schema, 'package_update')
                            if resource_errors.get('resources') and len(resource_errors.get('resources')) == 1:
                                # Exclude certain fields from resource validation errors
                                resource_errors = {key: error for key, error in resource_errors.get('resources')[0].items() if key not in exclude_from_validation}
                                if resource_errors and len(resource_errors) > 0 :
                                    pkg_errors['resources'] = [{
                                        'resource_id': res.get('id'),
                                        'resource_name': res.get('name'),
                                        'errors': resource_errors
                                    }]
                if len(pkg_errors) > 0:
                    validation_errors.append({'dataset': data_dict, 'errors': pkg_errors})
        except Exception as e:
            log.error(f"Error validating dataset: {dataset}")
            log.error(f"Error: {e}")
    
    # Aggregate dataset validation errors by contact point
    contact_points = {}
    for validation_error in validation_errors:
        contact_point = validation_error.get('dataset').get('contact_point')
        datasets = contact_points.get(contact_point, [])
        # Only add dataset if it does not already exist in datasets list
        datasets.append(validation_error) if validation_error not in datasets else datasets
        contact_points[contact_point] = datasets
    
    # Send email to contact points if there are validation errors 
    for contact_point in contact_points:
        try:
            datasets = contact_points[contact_point]
            # Only email contact point if there are datasets
            if len(datasets) > 0:
                contact_point_data = get_action('get_secure_vocabulary_record')(context, {'vocabulary_name': 'point-of-contact', 'query': contact_point})
                if contact_point_data:
                    recipient_name = contact_point_data.get('Name', '')
                    recipient_email = contact_point_data.get('Email', '')
                    subject = render('emails/subject/validate_datasets.txt')
                    body = render('emails/body/validate_datasets.txt', {'datasets': datasets})
                    body_html = render('emails/body/validate_datasets.html', {'datasets': datasets})
                    mail_recipient(recipient_name, recipient_email, subject, body, body_html)
                else:
                    # No contact point found for email notification
                    log.error(f'No contact point found for {contact_point}')
        except Exception as e:
            log.error(f"Error sending email to {contact_point}")

    # Send email to admin if there are validation errors
    if validation_errors:
        recipient_name = config.get('ckanext.qdes.validation_error_recipient_name')
        recipient_email = config.get('ckanext.qdes.validation_error_recipient_email')
        try:
            if recipient_email:
                subject = render('emails/subject/validate_datasets.txt')
                body = render('emails/body/validate_datasets.txt', {'datasets': validation_errors})
                body_html = render('emails/body/validate_datasets.html', {'datasets': validation_errors})
                mail_recipient(recipient_name, recipient_email, subject, body, body_html)
            else:
                log.error(f'validation_error_recipient_email is not set')
        except Exception as e:
            log.error(f"Error sending email to {recipient_name}:{recipient_email}")
