import logging
import six
import msgspec
import sqlalchemy as sa

from markupsafe import Markup
from datetime import datetime
from dataclasses import dataclass
from flask_session.redis import RedisSessionInterface

log = logging.getLogger(__name__)


@dataclass
class MarkupWrapper:
    content: str
    type: str = "__markup__"


@dataclass
class DatetimeWrapper:
    content: str
    type: str = "__datetime__"


class MsgspecSerializer:

    def __init__(self):
        self.encoder = msgspec.msgpack.Encoder()
        self.decoder = msgspec.msgpack.Decoder()

    def encode(self, obj):
        def convert(o):
            if isinstance(o, Markup):
                return MarkupWrapper(str(o)).__dict__
            elif isinstance(o, datetime):
                return DatetimeWrapper(o.isoformat()).__dict__
            elif isinstance(o, dict):
                return {k: convert(v) for k, v in o.items()}
            elif isinstance(o, (list, tuple)):
                return [convert(i) for i in o]
            return o

        converted_obj = convert(obj)
        return self.encoder.encode(converted_obj)

    def decode(self, data):
        def convert_back(obj):
            if isinstance(obj, dict):
                if obj.get("type") == "__markup__":
                    return Markup(obj["content"])
                elif obj.get("type") == "__datetime__":
                    return datetime.fromisoformat(obj["content"])
                return {k: convert_back(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_back(i) for i in obj]
            return obj

        decoded = self.decoder.decode(data)
        return convert_back(decoded)


class QdesRedisSession(RedisSessionInterface):

    def __init__(self, app):
        super().__init__(
            app,
            app.config["SESSION_REDIS"],
            app.config["SESSION_KEY_PREFIX"],
            app.config["SESSION_USE_SIGNER"],
            app.config["SESSION_PERMANENT"],
            serialization_format="msgpack",
        )
        self.serializer = MsgspecSerializer()


class QdesTrackingMiddleware:
    """Middleware for tracking user activity"""

    def __init__(self, app, config):
        self.app = app
        self.engine = sa.create_engine(config.get('sqlalchemy.url'))

    def __call__(self, environ, start_response):
        if self._is_tracking_request(environ):
            return self._handle_tracking(environ, start_response)
        return self.app(environ, start_response)

    def _is_tracking_request(self, environ):
        return (environ['PATH_INFO'] == '/_tracking' and
                environ.get('REQUEST_METHOD') == 'POST')

    def _handle_tracking(self, environ, start_response):
        try:
            data = self._parse_tracking_data(environ)
            user_key = self._generate_user_key(environ)
            self._store_tracking_data(user_key, data)

            start_response('200 OK', [('Content-Type', 'text/html')])
            return []
        except Exception as e:
            log.error(f"Tracking failed: {str(e)}")
            start_response('500 Internal Server Error',
                           [('Content-Type', 'text/html')])
            return [b'Tracking failed']

    def _parse_tracking_data(self, environ):
        content_length = int(environ['CONTENT_LENGTH'])
        payload = six.ensure_str(environ['wsgi.input'].read(content_length))
        parts = payload.split('&')
        return dict(part.split('=') for part in parts)
