# encoding: utf-8
"""Integration tests for organisation role mapping.

These require the CKAN test harness and a test database. See conftest.py.
Pure role-selection tests live in test_access_helpers_unit.py.
"""
import json
import pytest

import ckan.model as model
import ckan.tests.factories as factories

from ckan.plugins.toolkit import get_action

from ckanext.qdes.access import helpers

# This distribution enforces a stricter password policy than CKAN core's test
# factories generate, so tests supply a compliant password explicitly.
TEST_PASSWORD = 'TestPassw0rd!23'


def set_ad_groups(org_id, ad_groups):
    """Store an 'ad_groups' extra against an organisation."""
    group_extra = model.GroupExtra(
        group_id=org_id, key='ad_groups', value=json.dumps(ad_groups), state='active')
    model.Session.add(group_extra)
    model.Session.commit()


def get_capacities(user_name):
    """Return {org_name: capacity} for every organisation the user belongs to."""
    context = helpers.get_context_with_site_user()
    organisations = get_action('organization_list_for_user')(context, {'id': user_name})
    return {org.get('name'): org.get('capacity') for org in organisations}


@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
class TestGetOrganisationMapping(object):
    """Group B - mapping shape."""

    def test_group_mapped_to_multiple_orgs_kept(self):
        org_a = factories.Organization()
        org_b = factories.Organization()
        set_ad_groups(org_a['id'], [{'group': 'AD-SHARED', 'role': 'editor'}])
        set_ad_groups(org_b['id'], [{'group': 'AD-SHARED', 'role': 'member'}])

        mapping = helpers.get_organisation_mapping()

        org_ids = {entry['org_id'] for entry in mapping['AD-SHARED']}
        assert org_ids == {org_a['id'], org_b['id']}

    def test_multiple_groups_same_org_all_collected(self):
        org = factories.Organization()
        set_ad_groups(org['id'], [
            {'group': 'AD-MEMBER', 'role': 'member'},
            {'group': 'AD-EDITOR', 'role': 'editor'},
        ])

        mapping = helpers.get_organisation_mapping()

        assert mapping['AD-MEMBER'] == [{'org_id': org['id'], 'role': 'member'}]
        assert mapping['AD-EDITOR'] == [{'org_id': org['id'], 'role': 'editor'}]

    def test_malformed_extra_value_does_not_raise(self):
        org = factories.Organization()
        group_extra = model.GroupExtra(
            group_id=org['id'], key='ad_groups', value='not-json', state='active')
        model.Session.add(group_extra)
        model.Session.commit()

        assert helpers.get_organisation_mapping() == {}

    def test_entry_without_group_name_skipped(self):
        org = factories.Organization()
        set_ad_groups(org['id'], [{'role': 'admin'}, {'group': '', 'role': 'admin'}])

        assert helpers.get_organisation_mapping() == {}

    def test_inactive_group_extra_excluded(self):
        org = factories.Organization()
        group_extra = model.GroupExtra(
            group_id=org['id'], key='ad_groups',
            value=json.dumps([{'group': 'AD-GONE', 'role': 'admin'}]), state='deleted')
        model.Session.add(group_extra)
        model.Session.commit()

        assert 'AD-GONE' not in helpers.get_organisation_mapping()


@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
class TestUpdateUserOrganisations(object):
    """Group C - integration, memberships actually persist."""

    def test_multiple_groups_same_org_gets_highest(self):
        user = factories.User(password=TEST_PASSWORD)
        org = factories.Organization()
        set_ad_groups(org['id'], [
            {'group': 'AD-MEMBER', 'role': 'member'},
            {'group': 'AD-ADMIN', 'role': 'admin'},
        ])

        helpers.update_user_organisations(user['name'], ['AD-MEMBER', 'AD-ADMIN'])

        capacities = get_capacities(user['name'])
        assert capacities == {org['name']: 'admin'}

    def test_multi_org_independent_highest_roles(self):
        user = factories.User(password=TEST_PASSWORD)
        org_a = factories.Organization()
        org_b = factories.Organization()
        set_ad_groups(org_a['id'], [
            {'group': 'AD-A-EDITOR', 'role': 'editor'},
            {'group': 'AD-A-MEMBER', 'role': 'member'},
        ])
        set_ad_groups(org_b['id'], [{'group': 'AD-B-MEMBER', 'role': 'member'}])

        helpers.update_user_organisations(
            user['name'], ['AD-A-EDITOR', 'AD-A-MEMBER', 'AD-B-MEMBER'])

        capacities = get_capacities(user['name'])
        assert capacities == {org_a['name']: 'editor', org_b['name']: 'member'}

    def test_shared_group_grants_both_orgs(self):
        user = factories.User(password=TEST_PASSWORD)
        org_a = factories.Organization()
        org_b = factories.Organization()
        set_ad_groups(org_a['id'], [{'group': 'AD-SHARED', 'role': 'admin'}])
        set_ad_groups(org_b['id'], [{'group': 'AD-SHARED', 'role': 'member'}])

        helpers.update_user_organisations(user['name'], ['AD-SHARED'])

        capacities = get_capacities(user['name'])
        assert capacities == {org_a['name']: 'admin', org_b['name']: 'member'}

    def test_previous_memberships_revoked(self):
        user = factories.User(password=TEST_PASSWORD)
        org_current = factories.Organization()
        org_stale = factories.Organization()
        set_ad_groups(org_current['id'], [{'group': 'AD-CURRENT', 'role': 'member'}])
        context = helpers.get_context_with_site_user()
        get_action('organization_member_create')(context, {
            'id': org_stale['id'], 'username': user['name'], 'role': 'admin'})

        helpers.update_user_organisations(user['name'], ['AD-CURRENT'])

        capacities = get_capacities(user['name'])
        assert capacities == {org_current['name']: 'member'}

    def test_no_matching_groups_results_in_no_memberships(self):
        user = factories.User(password=TEST_PASSWORD)
        org = factories.Organization()
        set_ad_groups(org['id'], [{'group': 'AD-MEMBER', 'role': 'member'}])

        helpers.update_user_organisations(user['name'], ['AD-UNMAPPED'])

        assert get_capacities(user['name']) == {}

    def test_invalid_highest_role_falls_back_to_valid_role(self):
        user = factories.User(password=TEST_PASSWORD)
        org = factories.Organization()
        set_ad_groups(org['id'], [
            {'group': 'AD-BROKEN', 'role': 'superuser'},
            {'group': 'AD-MEMBER', 'role': 'member'},
        ])

        helpers.update_user_organisations(user['name'], ['AD-BROKEN', 'AD-MEMBER'])

        capacities = get_capacities(user['name'])
        assert capacities == {org['name']: 'member'}


@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
class TestUnchangedBehaviour(object):
    """Group D - regression guards for behaviour that must not change."""

    def test_saml_group_mapping_exist_with_new_shape(self):
        org = factories.Organization()
        set_ad_groups(org['id'], [{'group': 'AD-MEMBER', 'role': 'member'}])

        assert helpers.saml_group_mapping_exist(['AD-MEMBER']) is True
        assert helpers.saml_group_mapping_exist(['AD-UNMAPPED']) is False

    def test_sysadmin_group_grants_sysadmin(self):
        user = factories.User(password=TEST_PASSWORD)
        userobj = model.User.get(user['name'])

        helpers.update_user_sysadmin_status(userobj, 'AD-SYSADMIN', ['AD-SYSADMIN'])

        assert model.User.get(user['name']).sysadmin is True

    def test_sysadmin_removed_when_group_absent(self):
        user = factories.Sysadmin(password=TEST_PASSWORD)
        userobj = model.User.get(user['name'])

        helpers.update_user_sysadmin_status(userobj, 'AD-SYSADMIN', ['AD-OTHER'])

        assert model.User.get(user['name']).sysadmin is False
