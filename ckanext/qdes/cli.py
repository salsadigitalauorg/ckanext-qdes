import ckan.plugins.toolkit as toolkit
import ckanext.qdes.jobs as jobs
import click
import logging


log = logging.getLogger(__name__)
get_action = toolkit.get_action


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

@click.command(u"ckan-job-worker-monitor")
def ckan_worker_job_monitor():
    try:
        toolkit.enqueue_job(jobs.ckan_worker_job_monitor, title='CKAN job worker monitor')
        click.secho(u"CKAN job worker monitor added to worker queue", fg=u"green")
    except Exception as e:
        log.error(e)
        
@click.command(u"validate-datasets")
@click.pass_context
def validate_datasets(ctx):
    click.secho(f"Starting validating datasets", fg=u"green")
    try:
        flask_app = ctx.meta['flask_app']
        with flask_app.test_request_context():
            jobs.validate_datasets()
    except Exception as e:
        log.error(e)
    click.secho(f"Finished validating datasets", fg=u"green")

def get_commands():
    return [generate_audit_reports, review_datasets, send_email_notifications, ckan_worker_job_monitor, validate_datasets]
