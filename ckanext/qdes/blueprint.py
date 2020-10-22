import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
import ckan.lib.navl.dictization_functions as dict_fns
import logging

from datetime import datetime
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

    if request.method == 'POST':
        try:
            data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(request.form))))

            if not type(data['dataset']) is list:
                data['dataset'] = list([data['dataset']])

            for package_id in data['dataset']:
                package_dict = get_action('package_show')({}, {'id': package_id})
                package_dict['metadata_review_date'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                get_action('package_update')({}, package_dict)

            h.flash_success('Dataset(s) marked as reviewed.')
        except Exception as e:
            log.error(str(e))
            h.flash_error('Error updating dataset review date.')

        return h.redirect_to('/dashboard/review-datasets')

    org_id = request.args.get('org_id', None)

    extra_vars = {
        'packages': helpers.qdes_review_datasets(org_id),
        'user_dict': get_action('user_show')({}, {'id': g.userobj.id}),
    }
    return render('user/dashboard_review_datasets.html', extra_vars=extra_vars)


qdes.add_url_rule(u'/dashboard/review-datasets', view_func=dashboard_review_datasets, methods=[u'GET', u'POST'])
