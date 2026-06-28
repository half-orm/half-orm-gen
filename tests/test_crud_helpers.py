"""
Unit tests for half_orm_gen.backend.crud_helpers.

All functions are pure (no DB, no framework) — plain pytest, no fixtures needed.
"""
import pytest
from unittest.mock import MagicMock

from half_orm_gen.backend.crud_helpers import (
    _get_roles,
    _get_role_filter,
    _effective_out_fields,
    _effective_in_fields,
    _resolved_out,
    _resolved_in,
    _parse_q,
    _build_access_entry,
    _filter_access_for_roles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(token=None, authorized_roles=None):
    """Build a minimal duck-typed Request mock."""
    req = MagicMock()
    req.state.authorized_roles = authorized_roles
    req.headers.get = lambda key, default='': (
        f'Bearer {token}' if key == 'Authorization' and token else default
    )
    return req


ALL_FIELDS = ['id', 'title', 'content', 'author_id']
EXCLUDED   = ['content']
NON_EXCL   = ['id', 'title', 'author_id']


# ---------------------------------------------------------------------------
# _get_roles
# ---------------------------------------------------------------------------

class TestGetRoles:
    def test_anonymous_when_no_token(self):
        assert _get_roles(_req()) == ['anonymous']

    def test_token_prepended_before_anonymous(self):
        assert _get_roles(_req('admin')) == ['admin', 'anonymous']

    def test_state_authorized_roles_takes_precedence(self):
        req = _req('admin', authorized_roles=['editor', 'anonymous'])
        assert _get_roles(req) == ['editor', 'anonymous']

    def test_dedup_if_token_equals_anonymous(self):
        # token = 'anonymous' → list should not contain 'anonymous' twice
        roles = _get_roles(_req('anonymous'))
        assert roles.count('anonymous') == 1


# ---------------------------------------------------------------------------
# _get_role_filter
# ---------------------------------------------------------------------------

class TestGetRoleFilter:
    def test_no_matching_role_returns_empty(self):
        ca = {'GET': {'admin': {'filter': {'published': True}}}}
        assert _get_role_filter(ca, 'GET', ['anonymous']) == {}

    def test_matching_role_returns_filter(self):
        ca = {'GET': {'reader': {'filter': {'published': True}}}}
        assert _get_role_filter(ca, 'GET', ['reader']) == {'published': True}

    def test_rv_none_means_no_filter(self):
        ca = {'GET': {'admin': None}}
        assert _get_role_filter(ca, 'GET', ['admin']) == {}

    def test_rv_dict_without_filter_key_means_no_filter(self):
        ca = {'GET': {'admin': {'out': ['id']}}}
        assert _get_role_filter(ca, 'GET', ['admin']) == {}

    def test_multiple_roles_merge_filters(self):
        ca = {'GET': {
            'r1': {'filter': {'a': 1}},
            'r2': {'filter': {'b': 2}},
        }}
        result = _get_role_filter(ca, 'GET', ['r1', 'r2'])
        assert result == {'a': 1, 'b': 2}


# ---------------------------------------------------------------------------
# _effective_out_fields
# ---------------------------------------------------------------------------

class TestEffectiveOutFields:

    # --- not authorized ---

    def test_no_role_match_returns_none(self):
        ca = {'GET': {'admin': None}}
        result = _effective_out_fields(ca, 'GET', ['anonymous'], [], ALL_FIELDS)
        assert result is None

    def test_empty_crud_access_returns_none(self):
        result = _effective_out_fields({}, 'GET', ['anonymous'], [], ALL_FIELDS)
        assert result is None

    # --- rv=None (role matched but no fields configured) ---

    def test_rv_none_role_matched_no_fields(self):
        # rv=None: role is present but has no out fields → no access
        ca = {'GET': {'reader': None}}
        result = _effective_out_fields(ca, 'GET', ['reader'], EXCLUDED, ALL_FIELDS)
        assert result is None

    # --- 'out': None treated defensively as empty list ---

    def test_out_none_in_dict_treated_as_empty(self):
        ca = {'GET': {'reader': {'out': None}}}
        result = _effective_out_fields(ca, 'GET', ['reader'], EXCLUDED, ALL_FIELDS)
        assert result is None

    # --- specific fields ---

    def test_specific_out_fields(self):
        ca = {'GET': {'reader': {'out': ['id', 'title']}}}
        result = _effective_out_fields(ca, 'GET', ['reader'], [], ALL_FIELDS)
        assert result == ['id', 'title']

    def test_api_excluded_removed_from_specific_fields(self):
        ca = {'GET': {'reader': {'out': ['id', 'content', 'title']}}}
        result = _effective_out_fields(ca, 'GET', ['reader'], ['content'], ALL_FIELDS)
        assert 'content' not in result
        assert 'id' in result and 'title' in result

    # --- config error: verb granted but no out fields ---

    def test_empty_out_list_returns_none(self):
        ca = {'GET': {'reader': {'out': []}}}
        result = _effective_out_fields(ca, 'GET', ['reader'], [], ALL_FIELDS)
        assert result is None

    # --- multi-role union ---

    def test_multiple_roles_union(self):
        ca = {'GET': {
            'r1': {'out': ['id', 'title']},
            'r2': {'out': ['title', 'author_id']},
        }}
        result = _effective_out_fields(ca, 'GET', ['r1', 'r2'], [], ALL_FIELDS)
        assert set(result) == {'id', 'title', 'author_id'}

    def test_role_with_none_rv_contributes_no_fields(self):
        ca = {'GET': {
            'r1': {'out': ['id']},
            'r2': None,
        }}
        result = _effective_out_fields(ca, 'GET', ['r1', 'r2'], EXCLUDED, ALL_FIELDS)
        assert result == ['id']

    # --- fallback to GET out for non-GET verb without 'out' key ---

    def test_put_falls_back_to_get_out_when_no_out_key(self):
        ca = {
            'GET': {'editor': {'out': ['id', 'title']}},
            'PUT': {'editor': {'in': ['title']}},  # no 'out' key
        }
        result = _effective_out_fields(ca, 'PUT', ['editor'], [], ALL_FIELDS)
        assert result == ['id', 'title']

    # --- deduplication ---

    def test_deduplication_across_roles(self):
        ca = {'GET': {
            'r1': {'out': ['id', 'title']},
            'r2': {'out': ['id', 'author_id']},
        }}
        result = _effective_out_fields(ca, 'GET', ['r1', 'r2'], [], ALL_FIELDS)
        assert result.count('id') == 1


# ---------------------------------------------------------------------------
# _effective_in_fields
# ---------------------------------------------------------------------------

class TestEffectiveInFields:

    # --- rv=None (not a dict → no in fields) ---

    def test_rv_none_returns_empty_list(self):
        ca = {'POST': {'editor': None}}
        result = _effective_in_fields(ca, 'POST', ['editor'], EXCLUDED, ALL_FIELDS)
        assert result == []

    # --- 'in': None treated defensively as empty list ---

    def test_in_val_none_treated_as_empty(self):
        ca = {'POST': {'editor': {'in': None}}}
        result = _effective_in_fields(ca, 'POST', ['editor'], EXCLUDED, ALL_FIELDS)
        assert result == []

    # --- specific fields ---

    def test_specific_in_fields(self):
        ca = {'POST': {'editor': {'in': ['title', 'content']}}}
        result = _effective_in_fields(ca, 'POST', ['editor'], [], ALL_FIELDS)
        assert result == ['title', 'content']

    def test_api_excluded_removed_from_specific_fields(self):
        ca = {'POST': {'editor': {'in': ['title', 'content']}}}
        result = _effective_in_fields(ca, 'POST', ['editor'], ['content'], ALL_FIELDS)
        assert result == ['title']

    # --- config error ---

    def test_no_role_match_returns_empty_list(self):
        ca = {'POST': {'admin': {'in': ['title']}}}
        result = _effective_in_fields(ca, 'POST', ['anonymous'], [], ALL_FIELDS)
        assert result == []

    def test_empty_in_list_returns_empty_list(self):
        ca = {'POST': {'editor': {'in': []}}}
        result = _effective_in_fields(ca, 'POST', ['editor'], [], ALL_FIELDS)
        assert result == []

    # --- multi-role union ---

    def test_multiple_roles_union(self):
        ca = {'POST': {
            'r1': {'in': ['title']},
            'r2': {'in': ['author_id']},
        }}
        result = _effective_in_fields(ca, 'POST', ['r1', 'r2'], [], ALL_FIELDS)
        assert set(result) == {'title', 'author_id'}


# ---------------------------------------------------------------------------
# _resolved_out / _resolved_in
# ---------------------------------------------------------------------------

class TestResolved:
    def test_resolved_out_get_reads_out_key(self):
        ca = {'GET': {'r': {'out': ['id', 'title']}}}
        assert _resolved_out(ca, 'GET', 'r') == ['id', 'title']

    def test_resolved_out_delete_non_dict_returns_empty(self):
        # DELETE has no out fields; non-dict rv → []
        ca = {'DELETE': {'r': 'allowed'}}
        assert _resolved_out(ca, 'DELETE', 'r') == []

    def test_resolved_out_put_reads_out_key(self):
        ca = {'PUT': {'r': {'in': ['title'], 'out': ['id', 'title']}}}
        assert _resolved_out(ca, 'PUT', 'r') == ['id', 'title']

    def test_resolved_out_put_falls_back_to_get(self):
        ca = {
            'GET': {'r': {'out': ['id']}},
            'PUT': {'r': {'in': ['title']}},
        }
        assert _resolved_out(ca, 'PUT', 'r') == ['id']

    def test_resolved_in_reads_in_key(self):
        ca = {'POST': {'r': {'in': ['title', 'content']}}}
        assert _resolved_in(ca, 'POST', 'r') == ['title', 'content']

    def test_resolved_in_non_dict_rv_returns_empty(self):
        ca = {'POST': {'r': 'allowed'}}
        assert _resolved_in(ca, 'POST', 'r') == []


# ---------------------------------------------------------------------------
# _parse_q
# ---------------------------------------------------------------------------

class TestParseQ:
    def test_ilike_filter(self):
        fk, sc, rf = _parse_q('title:hello', [])
        assert fk == {'title': ('ilike', 'hello%')}
        assert sc == ['title']
        assert rf == []

    def test_comparison_operator(self):
        fk, sc, rf = _parse_q('count:>5', [])
        assert fk == {'count': ('>', '5')}

    def test_range_filter(self):
        fk, sc, rf = _parse_q('age:>=18<=65', [])
        assert rf == [('age', '>=', '18', '<=', '65')]
        assert fk == {}

    def test_excluded_field_ignored(self):
        fk, sc, rf = _parse_q('secret:value', ['secret'])
        assert fk == {}

    def test_multiple_pairs(self):
        fk, sc, rf = _parse_q('title:foo,author_id:>3', [])
        assert 'title' in fk
        assert 'author_id' in fk

    def test_pair_without_colon_ignored(self):
        fk, sc, rf = _parse_q('invalid', [])
        assert fk == {} and sc == [] and rf == []


# ---------------------------------------------------------------------------
# _build_access_entry
# ---------------------------------------------------------------------------

class TestBuildAccessEntry:
    def test_get_rv_none_produces_empty_out(self):
        # rv=None → no fields configured → empty out list
        ca = {'GET': {'reader': None}}
        entry = _build_access_entry(ca, EXCLUDED, ALL_FIELDS)
        assert entry['GET']['reader']['out'] == []

    def test_get_specific_fields(self):
        ca = {'GET': {'reader': {'out': ['id', 'title']}}}
        entry = _build_access_entry(ca, [], ALL_FIELDS)
        assert entry['GET']['reader']['out'] == ['id', 'title']

    def test_delete_produces_allowed(self):
        ca = {'DELETE': {'admin': 'allowed'}}
        entry = _build_access_entry(ca, [], ALL_FIELDS)
        assert entry['DELETE']['admin'] == 'allowed'

    def test_post_rv_none_produces_empty_in_and_out(self):
        ca = {'POST': {'editor': None}}
        entry = _build_access_entry(ca, EXCLUDED, ALL_FIELDS)
        assert entry['POST']['editor']['in']  == []
        assert entry['POST']['editor']['out'] == []

    def test_empty_crud_access_returns_empty_entry(self):
        entry = _build_access_entry({}, [], ALL_FIELDS)
        assert entry == {}


# ---------------------------------------------------------------------------
# _filter_access_for_roles
# ---------------------------------------------------------------------------

class TestFilterAccessForRoles:
    def _access_map(self):
        return {
            'blog/post': {
                'GET': {
                    'reader': {'out': ['id', 'title']},
                    'admin':  {'out': ['id', 'title', 'content']},
                },
                'DELETE': {'admin': 'allowed'},
            }
        }

    def test_reader_sees_only_own_out_fields(self):
        result = _filter_access_for_roles(self._access_map(), ['reader', 'anonymous'])
        assert result['blog/post']['GET']['out'] == ['id', 'title']
        assert 'DELETE' not in result['blog/post']

    def test_admin_gets_delete(self):
        result = _filter_access_for_roles(self._access_map(), ['admin', 'anonymous'])
        assert result['blog/post']['DELETE'] is True

    def test_unknown_role_excluded(self):
        result = _filter_access_for_roles(self._access_map(), ['nobody'])
        assert result == {}

    def test_union_of_out_fields_for_multiple_roles(self):
        result = _filter_access_for_roles(self._access_map(), ['reader', 'admin'])
        out = result['blog/post']['GET']['out']
        assert set(out) == {'id', 'title', 'content'}
        assert out.count('id') == 1  # deduplicated
