import logging
import json
import ckan.logic as logic
import ckan.views.user as ckan_view_user
import ckan.model as model
import ckan.plugins.toolkit as toolkit

from flask import Blueprint
from flask.views import MethodView
from ckan.lib.navl.dictization_functions import unflatten

log = logging.getLogger(__name__)
qdes_access = Blueprint('qdes_access', __name__)
request = toolkit.request
render = toolkit.render
check_access = toolkit.check_access
_ = toolkit._
get_action = toolkit.get_action
g = toolkit.g
h = toolkit.h
clean_dict = logic.clean_dict
tuplize_dict = logic.tuplize_dict
parse_params = logic.parse_params


def unauthorised():
    fullname = request.params.get('fullname', '')
    email = request.params.get('email', '')
    extra_vars = {
        u'code': [403],
        u'name': u'Not Authorised',
        u'content': u' User {0} with email {1} is not a member of any authenticated AD group'.format(fullname, email)
    }
    return render(u'error_document_template.html', extra_vars)


def ad_groups(id):
    extra_vars = {}
    context = {u'model': model, u'session': model.Session, u'user': g.user}

    try:
        data_dict = {u'id': id}
        check_access(u'get_organisation_ad_groups', context, data_dict)
        group_dict = get_action(u'organization_show')(context, data_dict)
        ad_groups = next((extra.get('value')
                          for extra in group_dict.get('extras') or [{}]
                          if extra.get('key') == 'ad_groups' and extra.get('state') == 'active'),
                         [])
    except toolkit.ObjectNotFound:
        toolkit.abort(404, _(u'Organization not found'))
    except toolkit.NotAuthorized:
        toolkit.abort(403,
                      _('Unauthorized to view AD groups'))

    extra_vars = {
        u"group_dict": group_dict,
        u"group_type": 'organization',
        u"ad_groups": toolkit.get_converter('json_or_string')(ad_groups) or []
    }
    return render(u'organization/ad_groups.html', extra_vars)


class ADsGroupView(MethodView):
    u'''New ADs group view'''

    def _prepare(self, id=None):
        context = {
            u'model': model,
            u'session': model.Session,
            u'user': g.user
        }
        try:
            check_access(u'create_organisation_ad_group', context, {u'id': id})
        except toolkit.NotAuthorized:
            toolkit.abort(403,
                          _('Unauthorized to create AD group'))

        return context

    def post(self, group_type='organization', is_organization=True, id=None):
        context = self._prepare(id)
        data_dict = clean_dict(unflatten(tuplize_dict(parse_params(request.form))))
        data_dict['id'] = id
        ad_group = data_dict.get(u'ad_group')

        try:
            if ad_group:
                group_dict = get_action(u'organization_show')(context, data_dict)

                for extra in group_dict.get('extras') or [{}]:
                    # Remove the id from the extra because schema has empty_if_not_sysadmin validator
                    extra.pop('id', None)
                    # Existing ad_groups
                    if extra.get('key') == 'ad_groups' and extra.get('state') == 'active':
                        ad_groups = toolkit.get_converter('json_or_string')(extra.get('value') or [])
                        if not isinstance(ad_groups, list):
                            ad_groups = []
                        ad_groups.append({"group": ad_group, "role": data_dict['role']})
                        extra['value'] = json.dumps(ad_groups)
                        get_action(u'organization_update')(context, group_dict)
                        break
                    else:
                        # First ad_group
                        ad_groups = []
                        ad_groups.append({"group": ad_group, "role": data_dict['role']})
                        extra['key'] = 'ad_groups'
                        extra['group_id'] = group_dict.get('id')
                        extra['value'] = json.dumps(ad_groups)
                        group_dict['extras'].append(extra)
                        get_action(u'organization_update')(context, group_dict)
                        break

        except toolkit.NotAuthorized:
            toolkit.abort(403, _(u'Unauthorized to update organisation'))
        except toolkit.ObjectNotFound:
            toolkit.abort(404, _(u'Organisation not found'))
        except toolkit.ValidationError as e:
            toolkit.h.flash_error(e.error_summary)
            return toolkit.redirect_to(u'qdes_access.ad_groups', id=id)

        return h.redirect_to(u'qdes_access.ad_groups', id=id)

    def get(self, group_type='organization', is_organization=True, id=None):
        extra_vars = {}
        context = self._prepare(id)
        data_dict = {u'id': id}
        data_dict['include_datasets'] = False
        group_dict = get_action(u'organization_show')(context, data_dict)
        roles = get_action(u'member_roles_list')(context, {
            u'group_type': group_type
        })

        extra_vars.update({
            u"group_dict": group_dict,
            u"roles": roles,
            u"group_type": group_type,
        })
        return toolkit.render(u'organization/ad_group_new.html', extra_vars)


def ad_group_delete(id, group_type='organization', is_organization=True):
    extra_vars = {}
    if u'cancel' in request.params:
        return render(u'organization/ad_groups.html', extra_vars)

    context = {u'model': model, u'session': model.Session, u'user': g.user}

    try:
        check_access(u'delete_organisation_ad_group', context, {u'id': id})
    except toolkit.NotAuthorized:
        toolkit.abort(403, _(u'Unauthorized to delete AD group'))

    try:
        ad_groups = []
        data_dict = {u'id': id}
        group_dict = get_action(u'organization_show')(context, data_dict)
        if request.method == u'POST':
            delete_ad_group = request.params.get(u'delete_ad_group')

            if delete_ad_group:
                for extra in group_dict.get('extras') or [{}]:
                    # Remove the id from the extra because schema has empty_if_not_sysadmin validator
                    extra.pop('id', None)
                    # Existing ad_groups
                    if extra.get('key') == 'ad_groups' and extra.get('state') == 'active':
                        ad_groups = toolkit.get_converter('json_or_string')(extra.get('value') or [])
                        for ad_group in ad_groups if isinstance(ad_groups, list) else []:
                            if ad_group.get('group', None) == delete_ad_group:
                                ad_groups.remove(ad_group)
                                extra['value'] = json.dumps(ad_groups)
                                get_action(u'organization_update')(context, group_dict)
                                break
    except toolkit.ObjectNotFound:
        toolkit.abort(404, _(u'Organisation not found'))
    except toolkit.NotAuthorized:
        toolkit.abort(403,
                      _('Unauthorized to update organisation'))

    extra_vars = {
        u"group_dict": group_dict,
        u"group_type": 'organization',
        u"ad_groups": ad_groups
    }
    return render(u'organization/ad_groups.html', extra_vars)


qdes_access.add_url_rule(u'/service/login', view_func=ckan_view_user.login, methods=[u'GET', u'POST'])
qdes_access.add_url_rule(u'/user/unauthorised', view_func=unauthorised)
qdes_access.add_url_rule(u'/organization/ad_groups/<id>', view_func=ad_groups)
qdes_access.add_url_rule(u'/organization/ad_group_new/<id>', view_func=ADsGroupView.as_view(str(u'ad_group_new')), methods=[u'GET', u'POST'])
qdes_access.add_url_rule(u'/organization/ad_group_delete/<id>', view_func=ad_group_delete, methods=[u'GET', u'POST'])
