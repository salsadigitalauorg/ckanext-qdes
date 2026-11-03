import re

import pytest

LOGIN_FORM = {'login': 'nobody', 'password': 'wrong-password'}


@pytest.mark.usefixtures('clean_db')
class TestServiceLoginCsrf:

    def test_post_without_csrf_token_is_rejected(self, app):
        res = app.post('/service/login', data=LOGIN_FORM)

        assert res.status_code == 400

    def test_post_with_csrf_token_reaches_login(self, app):
        # One client, so the session that holds the token survives to the POST.
        client = app.test_client()
        form = client.get('/service/login').get_data(as_text=True)
        token = re.search(r'name="_csrf_token" value="([^"]+)"', form).group(1)

        res = client.post('/service/login', data=dict(LOGIN_FORM, _csrf_token=token))

        assert res.status_code == 200
        assert 'Login failed' in res.get_data(as_text=True)
