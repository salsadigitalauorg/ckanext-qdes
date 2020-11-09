import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
import ckan.lib.navl.dictization_functions as dict_fns
import logging

from ckan.lib.base import abort
from ckan.common import g
from flask import Blueprint
from ckanext.qdes import helpers
from pprint import pformat

h = toolkit.h
clean_dict = logic.clean_dict
tuplize_dict = logic.tuplize_dict
parse_params = logic.parse_params
get_action = logic.get_action
render = toolkit.render
request = toolkit.request
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
        errors = []

        # Defer commit on bulk update to prevent Session closing pre-maturely
        # and throwing exceptions when bulk updating
        defer_commit = True

        data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(request.form))))

        if not type(data['dataset']) is list:
            data['dataset'] = list([data['dataset']])
            # No need to defer commit on single package patch
            defer_commit = False

        for package_id in data['dataset']:
            try:
                get_action('package_patch')({'defer_commit': defer_commit}, {'id': package_id, 'metadata_review_date': helpers.utcnow_as_string()})
            except Exception as e:
                log.error(str(e))
                errors.append({'id': package_id, 'message': str(e)})

        if not errors:
            h.flash_success('Dataset(s) marked as reviewed.')
        else:
            h.flash_error('Errors updating dataset review date: {}'.format(errors))

        return h.redirect_to('/dashboard/review-datasets{}'.format('?org_id=' + org_id if org_id else ''))

    extra_vars = {
        'packages': helpers.qdes_review_datasets(org_id),
        'user_dict': get_action('user_show')({}, {'id': g.userobj.id}),
    }
    return render('user/dashboard_review_datasets.html', extra_vars=extra_vars)


def dashboard_reports():
    if request.method == 'POST':
        # Get the submitted data.
        data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(request.form))))

        # Get the rows.
        available_actions = [
            'qdes_datasets_not_updated',
            'qdes_empty_recommended',
            'qdes_invalid_uris',
            'qdes_datasets_not_reviewed',
        ]
        if data.get('audit_type') in available_actions:
            rows = get_action(data.get('audit_type'))({}, {'org_id': data['org_id']})
        else:
            rows = get_action('qdes_report_all')({}, {'org_id': data['org_id']})

        log.error(pformat(rows))

        # @todo, convert to csv.
        # @todo, zip it if multiple file.
        # @todo, force download the zip or csv.

        return h.redirect_to('/dashboard/reports')

    extra_vars = {
        'user_dict': get_action('user_show')({}, {'id': g.userobj.id}),
    }
    return render('user/dashboard_reports.html', extra_vars=extra_vars)


qdes.add_url_rule(u'/dashboard/review-datasets', view_func=dashboard_review_datasets, methods=[u'GET', u'POST'])
qdes.add_url_rule(u'/dashboard/reports', view_func=dashboard_reports, methods=[u'GET', u'POST'])
