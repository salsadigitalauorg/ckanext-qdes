import logging

import ckan.lib.mailer as mailer
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckan.views.user import RequestResetView
from flask import Blueprint

log = logging.getLogger(__name__)
qdes_access = Blueprint('qdes_access', __name__)
h = toolkit.h
get_action = toolkit.get_action
NotFound = toolkit.ObjectNotFound
g = toolkit.g
request = toolkit.request
_ = toolkit._


def request_reset():
    '''
    This method is copied from the ckan user view class method RequestResetView.post
    It is a exact copy so will need to be checked and updated if necessary on any CKAN upgrades
    There are a few modifications to check if the user requesting a password reset is a sysadmin
    Only sysadmins are sent a reset link email
    '''
    RequestResetView._prepare(None)
    id = request.form.get(u'user')
    if id in (None, u''):
        h.flash_error(_(u'Email is required'))
        return h.redirect_to(u'/user/reset')
    log.info(u'Password reset requested for user "{}"'.format(id))

    context = {u'model': model, u'user': g.user, u'ignore_auth': True}
    user_objs = []

    # Usernames cannot contain '@' symbols
    if u'@' in id:
        # Search by email address
        # (You can forget a user id, but you don't tend to forget your
        # email)
        user_list = get_action(u'user_list')(context, {
            u'email': id
        })
        if user_list:
            # send reset emails for *all* user accounts with this email
            # (otherwise we'd have to silently fail - we can't tell the
            # user, as that would reveal the existence of accounts with
            # this email address)
            for user_dict in user_list:
                # This is ugly, but we need the user object for the mailer,
                # and user_list does not return them
                # Qdes modifications begin
                user = get_action(u'user_show')(
                    context, {u'id': user_dict[u'id']})
                if user.get('sysadmin', False):
                    user_objs.append(context[u'user_obj'])
                else:
                    log.info(
                        u'User requested reset link for a non sysadmin user: {}'.format(id))
                # Qdes modifications end

    else:
        # Search by user name
        # (this is helpful as an option for a user who has multiple
        # accounts with the same email address and they want to be
        # specific)
        try:
            # Qdes modifications begin
            user = get_action(u'user_show')(context, {u'id': id})
            if user.get('sysadmin', False):
                user_objs.append(context[u'user_obj'])
            else:
                log.info(
                    u'User requested reset link for a non sysadmin user: {}'.format(id))
            # Qdes modifications end
        except NotFound:
            pass

    if not user_objs:
        log.info(u'User requested reset link for unknown user: {}'
                 .format(id))

    for user_obj in user_objs:
        log.info(u'Emailing reset link to user: {}'
                 .format(user_obj.name))
        try:
            # FIXME: How about passing user.id instead? Mailer already
            # uses model and it allow to simplify code above
            mailer.send_reset_link(user_obj)
        except mailer.MailerException as e:
            # SMTP is not configured correctly or the server is
            # temporarily unavailable
            h.flash_error(_(u'Error sending the email. Try again later '
                            'or contact an administrator for help'))
            log.exception(e)
            return h.redirect_to(u'home.index')

    # always tell the user it succeeded, because otherwise we reveal
    # which accounts exist or not
    h.flash_success(
        _(u'A reset link has been emailed to you '
            '(unless the account specified does not exist)'))
    return h.redirect_to(u'home.index')


qdes_access.add_url_rule(
    u'/user/reset', view_func=request_reset, methods=[u'POST'])
