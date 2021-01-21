import logging
import ckan.lib.api_token as api_token
import ckan.model as model
import ckan.plugins.toolkit as toolkit
import ckan.views as views
import six

log = logging.getLogger(__name__)


class QdesAuthMiddleware(object):
    def __init__(self, app, app_conf):
        self.app = app

    def __call__(self, environ, start_response):
        # if logged in via browser cookies or API key, all pages accessible
        if 'repoze.who.identity' not in environ and not self._get_user_for_apikey(environ):
            # The only pages unauthenticated users have access to are below
            # home, login, password reset, saml2login and acs (SAML Assertion Consumer Service)
            # But still allow unauthenticated access to assets and API
            # API authentication will be handled by API auth/actions but some have public access
            if environ['PATH_INFO'] not in ['/', '/user/login', '/user/reset', '/user/saml2login', '/acs'] \
                    and not environ['PATH_INFO'].startswith('/base') \
                    and not environ['PATH_INFO'].startswith('/api') \
                    and not environ['PATH_INFO'].startswith('/webassets') \
                    and not environ['PATH_INFO'].startswith('/images') \
                    and not environ['PATH_INFO'].startswith('/css') \
                    and not environ['PATH_INFO'].startswith('/js') \
                    and not environ['PATH_INFO'].startswith('/_debug'):
                status = "401 Unauthorized"
                headers = [('Location', '/user.login'),
                           ('Content-Length', '0')]

                start_response(status, headers)

        return self.app(environ, start_response)

    def _get_user_for_apikey(self, environ):
        # Based off method _get_user_for_apikey from https://github.com/ckan/ckan/blob/afe077e78e929a38112980d24df7c5d057b363ec/ckan/views/__init__.py
        # Updated to remove request and use paramater environ
        apikey_header_name = toolkit.config.get(views.APIKEY_HEADER_NAME_KEY,
                                                views.APIKEY_HEADER_NAME_DEFAULT)
        apikey = environ.get(apikey_header_name, u'')
        if not apikey:
            # For misunderstanding old documentation (now fixed).
            apikey = environ.get(u'HTTP_AUTHORIZATION', u'')
        if not apikey:
            apikey = environ.get(u'Authorization', u'')
            # Forget HTTP Auth credentials (they have spaces).
            if u' ' in apikey:
                apikey = u''
        if not apikey:
            return None

        apikey = six.ensure_text(apikey, errors=u"ignore")
        query = model.Session.query(model.User)
        user = query.filter_by(apikey=apikey).first()

        if not user:
            user = api_token.get_user_from_token(apikey)
        return user
