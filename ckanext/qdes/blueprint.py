import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
import ckan.lib.navl.dictization_functions as dict_fns
import logging
import os

from ckan.common import config
from ckanext.qdes import helpers
from ckanext.qdes import constants
from ckanext.qdes import jobs
from flask import Blueprint
from pprint import pformat

clean_dict = logic.clean_dict
tuplize_dict = logic.tuplize_dict
parse_params = logic.parse_params
get_action = logic.get_action

h = toolkit.h
render = toolkit.render
request = toolkit.request
abort = toolkit.abort
g = toolkit.g

log = logging.getLogger(__name__)
qdes = Blueprint('qdes', __name__)


def dashboard_review_datasets():
    # Only sysadmin, admin or editor.
    admin_org = g.userobj.get_groups('organization', 'admin')
    editor_org = g.userobj.get_groups('organization', 'editor')
    if not (g.userobj.sysadmin or admin_org or editor_org):
        abort(404, 'Not found')

    org_id = request.args.get('org_id', None)

    if request.method == 'POST':
        data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(request.form))))

        if 'dataset' in data:
            if not type(data['dataset']) is list:
                data['dataset'] = list([data['dataset']])

            toolkit.enqueue_job(jobs.mark_as_reviewed, [data['dataset']])

            h.flash_success('This is a background process and can take several minutes. You can safely navigate away from this screen and check the status of the review process later.')
        else:
            h.flash_error('There are no datasets marked for review')

        return h.redirect_to('/dashboard/review-datasets{}'.format('?org_id=' + org_id if org_id else ''))

    extra_vars = {
        'packages': helpers.qdes_review_datasets(org_id),
        'user_dict': get_action('user_show')({}, {'id': g.userobj.id}),
    }
    return render('user/dashboard_review_datasets.html', extra_vars=extra_vars)


def dashboard_reports():
    # Only sysadmin can access.
    if not g.userobj.sysadmin:
        abort(404, 'Not found')

    if request.method == 'POST':
        # Get the submitted data.
        data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(request.form))))

        # Get the rows.
        available_actions = {
            'qdes_datasets_not_updated': 'not-updated',
            'qdes_datasets_with_empty_recommended_fields': 'recommended',
            'qdes_datasets_with_invalid_urls': 'invalid-urls',
            'qdes_datasets_not_reviewed': 'not-reviewed',
        }
        if data.get('audit_type') in available_actions:
            rows = get_action(data.get('audit_type'))({}, {'org_id': data['org_id']})
            file = helpers.qdes_generate_csv(available_actions.get(data.get('audit_type')), rows)
            type = 'csv'

        else:
            file = get_action('qdes_report_all')({}, {'available_actions': available_actions, 'org_id': data['org_id']})
            type = 'zip'

        if file:
            # Send to browser.
            return helpers.qdes_send_file_to_browser(constants.TMP_PATH + '/' + file, type)
        else:
            h.flash_error('No report can be generated, data is empty.')
            return h.redirect_to('/dashboard/reports')

    extra_vars = {
        'user_dict': get_action('user_show')({}, {'id': g.userobj.id}),
    }
    return render('user/dashboard_reports.html', extra_vars=extra_vars)


def reports(type):
    types = {
        'not-updated': 'not-updated',
        'not-reviewed': 'not-reviewed',
        'invalid-uris': 'invalid-urls',
        'incomplete-recommended': 'recommended',
    }

    if not type in types:
        abort(404, 'Not found')

    # Get the latest report directory.
    reports_dir = os.listdir(constants.REPORT_PATH)
    if not reports_dir:
        abort(404, 'Not found')

    reports_dir.sort(reverse=True)
    latest_dir = constants.REPORT_PATH + '/' + reports_dir[0] + '/'

    # Get the csv file.
    csv_files = os.listdir(latest_dir)
    csv_file = ''
    for file in csv_files:
        if types.get(type) in file:
            csv_file = file
            break

    # Send to browser but don't remove it.
    return helpers.qdes_send_file_to_browser(latest_dir + csv_file, 'csv', False)


def api_tokens():
    # Only sysadmin can access.
    if not g.userobj or not g.userobj.sysadmin:
        abort(404, 'Not found')

    tokens = helpers.get_api_tokens()
    return render(u'admin/api_tokens.html', extra_vars={"tokens": tokens})


def api_token_revoke(jti):
    # Only sysadmin can access.
    if not g.userobj or not g.userobj.sysadmin:
        abort(404, 'Not found')

    get_action(u'api_token_revoke')({}, {u'jti': jti})

    h.flash_success('Revoked API token')
    return h.redirect_to(u'qdes.api_tokens')


def contact():
    # Only logged in user can access.
    if not g.userobj:
        abort(404, 'Not found')

    return render(u'contact_page.html', extra_vars={"content": config.get('ckanext.qdes_schema.contact', '')})


qdes.add_url_rule(u'/dashboard/review-datasets', view_func=dashboard_review_datasets, methods=[u'GET', u'POST'])
qdes.add_url_rule(u'/dashboard/reports', view_func=dashboard_reports, methods=[u'GET', u'POST'])
qdes.add_url_rule(u'/reports/<type>', view_func=reports, methods=[u'GET'])
qdes.add_url_rule(u'/ckan-admin/api-tokens', view_func=api_tokens, methods=[u'GET'])
qdes.add_url_rule(u'/ckan-admin/api-tokens/<jti>/revoke', view_func=api_token_revoke, methods=[u'POST'])
qdes.add_url_rule(u'/contact', view_func=contact, methods=[u'GET'])
