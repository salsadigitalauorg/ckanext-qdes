import ckan.plugins.toolkit as toolkit
import ckanext.qdes.jobs as jobs
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


def get_commands():
    return [generate_audit_reports, review_datasets]
