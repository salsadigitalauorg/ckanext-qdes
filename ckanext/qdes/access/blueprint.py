import logging

import ckan.plugins.toolkit as toolkit
import ckan.views.user as ckan_view_user
from flask import Blueprint

log = logging.getLogger(__name__)
qdes_access = Blueprint('qdes_access', __name__)


qdes_access.add_url_rule(u'/service/login', view_func=ckan_view_user.login)
