import ckan.plugins.toolkit as toolkit
import ckanext.qdes.jobs as jobs
import ckan.lib.jobs as ckan_jobs

from time import sleep


import os
import click
import logging

from ckan.plugins.toolkit import get_action
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
            jobs.generate_reports()
    except Exception as e:
        log.error(e)


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


@click.command(u"send-email-notifications")
@click.pass_context
def send_email_notifications(ctx):
    try:
        flask_app = ctx.meta['flask_app']
        with flask_app.test_request_context():
            site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
            context = {u'user': site_user[u'name']}
            get_action('send_email_notifications')(context, {})

            click.secho(u"Email notification sent", fg=u"green")
    except Exception as e:
        log.error(e)


@click.command("check-ckan-jobworker")
def check_jobworker():
    queue =  ckan_jobs.get_queue()
    if queue:
        return print("Jobworker OK")
    return print("Jobworker down")

def get_commands():
    return [generate_audit_reports, review_datasets, send_email_notifications, check_jobworker]
