import logging
import ckan.views.user as ckan_view_user

from ckan.plugins.toolkit import request, render
from flask import Blueprint

log = logging.getLogger(__name__)
qdes_access = Blueprint('qdes_access', __name__)


def unauthorised():
    fullname = request.params.get('fullname', '')
    email = request.params.get('email', '')
    extra_vars = {
        u'code': [403],
        u'name': u'Not Authorised',
        u'content': u' User {0} with email {1} is not a member of any authenticated AD group'.format(fullname, email)
    }
    return render(u'error_document_template.html', extra_vars)


qdes_access.add_url_rule(u'/service/login', view_func=ckan_view_user.login, methods=[u'GET', u'POST'])
qdes_access.add_url_rule(u'/user/unauthorised', view_func=unauthorised)
