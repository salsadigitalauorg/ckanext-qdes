# encoding: utf-8
"""Unit tests for organisation role selection.

These tests are deliberately free of database, Redis and Solr dependencies so
they can run without the CKAN test harness:

    python -m pytest ckanext/qdes/tests/test_access_helpers_unit.py \
        -p no:ckan -p no:ckan_fixtures -o addopts=""
"""

import pytest

from ckanext.qdes.access import helpers

VALID_ROLES = ['admin', 'editor', 'member']


class TestSelectHighestRole(object):
    """Group A - pure unit tests, no database required."""

    def test_member_and_editor_returns_editor(self):
        assert (
            helpers.select_highest_role(['member', 'editor'], valid_roles=VALID_ROLES)
            == 'editor'
        )

    def test_member_and_admin_returns_admin(self):
        assert (
            helpers.select_highest_role(['member', 'admin'], valid_roles=VALID_ROLES)
            == 'admin'
        )

    def test_editor_and_admin_returns_admin(self):
        assert (
            helpers.select_highest_role(['editor', 'admin'], valid_roles=VALID_ROLES)
            == 'admin'
        )

    def test_all_three_returns_admin(self):
        roles = ['member', 'editor', 'admin']
        assert helpers.select_highest_role(roles, valid_roles=VALID_ROLES) == 'admin'

    def test_single_role_returned_unchanged(self):
        assert (
            helpers.select_highest_role(['member'], valid_roles=VALID_ROLES) == 'member'
        )
        assert (
            helpers.select_highest_role(['editor'], valid_roles=VALID_ROLES) == 'editor'
        )
        assert (
            helpers.select_highest_role(['admin'], valid_roles=VALID_ROLES) == 'admin'
        )

    def test_order_independent(self):
        # The defect this ticket fixes: selection must not depend on input order.
        assert (
            helpers.select_highest_role(['admin', 'member'], valid_roles=VALID_ROLES)
            == 'admin'
        )
        assert (
            helpers.select_highest_role(['member', 'admin'], valid_roles=VALID_ROLES)
            == 'admin'
        )
        assert (
            helpers.select_highest_role(['editor', 'member'], valid_roles=VALID_ROLES)
            == 'editor'
        )
        assert (
            helpers.select_highest_role(['member', 'editor'], valid_roles=VALID_ROLES)
            == 'editor'
        )

    def test_duplicates_collapse(self):
        assert (
            helpers.select_highest_role(['editor', 'editor'], valid_roles=VALID_ROLES)
            == 'editor'
        )

    def test_empty_returns_none(self):
        assert helpers.select_highest_role([], valid_roles=VALID_ROLES) is None

    def test_unknown_role_ignored_valid_still_wins(self):
        # An unrecognised role must not deny the user a valid lower role.
        roles = ['superuser', 'member']
        assert helpers.select_highest_role(roles, valid_roles=VALID_ROLES) == 'member'

    def test_all_invalid_returns_none(self):
        assert (
            helpers.select_highest_role(['superuser', ''], valid_roles=VALID_ROLES)
            is None
        )

    def test_none_and_empty_entries_tolerated(self):
        roles = [None, 'member']
        assert helpers.select_highest_role(roles, valid_roles=VALID_ROLES) == 'member'

    def test_none_input_returns_none(self):
        assert helpers.select_highest_role(None, valid_roles=VALID_ROLES) is None

    @pytest.mark.parametrize(
        'roles',
        [
            ['member'],
            ['member', 'editor'],
            ['admin', 'editor', 'member'],
            ['superuser', 'editor'],
            ['superuser'],
            [],
        ],
    )
    def test_never_returns_role_not_in_input(self, roles):
        # Least privilege: a role is never escalated beyond what was asserted.
        result = helpers.select_highest_role(roles, valid_roles=VALID_ROLES)
        assert result is None or result in roles

    def test_valid_roles_resolved_from_ckan_when_not_supplied(self):
        assert helpers.select_highest_role(['member', 'admin']) == 'admin'

    def test_ckan_valid_role_without_known_priority_is_still_assigned(self):
        # Must not be discarded - that would deny access the AD group grants.
        assert (
            helpers.select_highest_role(['curator'], valid_roles=VALID_ROLES + ['curator'])
            == 'curator'
        )

    def test_unranked_role_loses_to_every_known_role(self):
        # Ranked last, so it never displaces a known role.
        valid_roles = VALID_ROLES + ['curator']
        assert helpers.select_highest_role(['curator', 'member'], valid_roles=valid_roles) == 'member'
        assert helpers.select_highest_role(['curator', 'admin'], valid_roles=valid_roles) == 'admin'
        assert helpers.select_highest_role(['admin', 'curator'], valid_roles=valid_roles) == 'admin'

    def test_unranked_role_not_escalated(self):
        # Least privilege still holds for roles with no known priority.
        result = helpers.select_highest_role(['curator'], valid_roles=VALID_ROLES + ['curator'])
        assert result == 'curator'
        assert result != 'admin'


class TestGetRolePriority(object):
    """Priority ordering is derived from CKAN, not hardcoded."""

    def test_derived_from_ckan_role_permissions(self):
        priority = helpers.get_role_priority()
        assert priority['admin'] > priority['editor'] > priority['member']

    def test_covers_every_ckan_role(self):
        import ckan.authz as authz

        assert set(helpers.get_role_priority()) == set(authz.ROLE_PERMISSIONS)

    def test_agrees_with_fallback_constant_ordering(self):
        # A contradiction would silently change which role wins on fallback.
        derived = helpers.get_role_priority()
        fallback = helpers.ROLE_PRIORITY
        shared = sorted(set(derived) & set(fallback))
        assert shared
        by_derived = sorted(shared, key=lambda r: derived[r])
        by_fallback = sorted(shared, key=lambda r: fallback[r])
        assert by_derived == by_fallback
