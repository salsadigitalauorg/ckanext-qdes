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
            # The only pages unauthorized users have access to are below
            # service login, saml2login, acs (SAML Assertion Consumer Service), user unauthorised and logout pages
            # But still allow unauthorized access to assets and API
            # API authentication will be handled by API auth/actions but some have public access
            unauthorized_pages_allowed = toolkit.aslist(toolkit.config.get('ckanext.qdes_access.unauthorized_pages_allowed', ''))
            if environ['PATH_INFO'] not in unauthorized_pages_allowed \
                    and not environ['PATH_INFO'].startswith('/base') \
                    and not environ['PATH_INFO'].startswith('/api') \
                    and not environ['PATH_INFO'].startswith('/webassets') \
                    and not environ['PATH_INFO'].startswith('/images') \
                    and not environ['PATH_INFO'].startswith('/css') \
                    and not environ['PATH_INFO'].startswith('/js') \
                    and not environ['PATH_INFO'].startswith('/_debug') \
                    and not environ['PATH_INFO'].startswith('/uploads'):

                log.debug(f"Unauthorized page accessed: {environ['PATH_INFO']}")
                # Status code needs to be 3xx (redirection) for Location header to be used
                status = "302 Unauthorized"
                location = toolkit.config.get('ckanext.qdes_access.unauthorized_redirect_location', '/user/saml2login')
                headers = [('Location', location),
                           ('Content-Length', '0')]
                log.debug(f"Redirecting to: {location}")
                start_response(status, headers)
                # Return now as we want to end the request
                return []

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
