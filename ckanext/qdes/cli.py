import ckan.plugins.toolkit as toolkit
import ckanext.qdes.jobs as jobs
import os
import click
import shutil
import logging

from ckan.common import config as cfg
from ckan.plugins.toolkit import get_action
from ckanext.qdes.helpers import qdes_generate_csv, tmp_dir
from datetime import datetime
from pprint import pformat

log = logging.getLogger(__name__)


@click.command(u"generate-audit-reports")
@click.pass_context
def generate_audit_reports(context):
    u"""
    Generate audit reports.
    """
    try:
        flask_app = context.meta['flask_app']
        with flask_app.test_request_context():
            generate_reports()
    except Exception as e:
        log.error(e)


def generate_reports():
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
        csv_file = qdes_generate_csv(available_actions.get(report), get_action(report)(context, {'org_id': None}))

        if csv_file:
            csv_files.append(csv_file)

    if not csv_files:
        click.secho(u"No report generated, data is empty.", fg=u"green")
        return

    # Create the destination directory.
    try:
        root_dir = '/app/filestore/storage'
        reports_dir = root_dir + '/reports'
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
        shutil.move(tmp_dir + csv_file, current_backup_dir + '/' + csv_file)

    # @todo, remove older backups.
    # config_value = cfg.get('name_of_config_setting', default)

    click.secho(u"Reports generated", fg=u"green")


@click.command(u"review-datasets")
@click.pass_context
def review_datasets(ctx):
    u"""
    Find any datasets that need to be reviewed and send email notification to data creator
    """
    click.secho(u"Begin reviewing datasets", fg=u"green")

    try:
        flask_app = ctx.meta['flask_app']
        with flask_app.test_request_context():
            jobs.review_datasets()
    except Exception as e:
        log.error(e)

    click.secho(u"Finished reviewing datasets", fg=u"green")


def get_commands():
    return [generate_audit_reports, review_datasets]
