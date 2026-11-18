import importlib
import json

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import AccountRole
from dashboard.models import TeamMember
from dashboard.permissions import (
    ALL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    clear_role_cache,
    get_dashboard_role,
    has_dashboard_access,
    has_dashboard_permission,
    permissions_for_user,
    translate_legacy_permissions,
)


PASSWORD = 'Roles-test-pass-2026!'


def make_user(username, role_code=None, superuser=False, staff=True):
    if superuser:
        return User.objects.create_superuser(username, f'{username}@example.com', PASSWORD)
    user = User.objects.create_user(username, f'{username}@example.com', PASSWORD, is_staff=staff)
    if role_code:
        user.membership_profile.account_role = AccountRole.objects.get(code=role_code)
        user.membership_profile.save(update_fields=['account_role', 'updated_at'])
    return user


class RolesTestCase(TestCase):
    def post(self, url, payload=None):
        return self.client.post(url, data=json.dumps(payload or {}), content_type='application/json')

    def role(self, code):
        return AccountRole.objects.get(code=code)


class SeededRoleTests(RolesTestCase):
    def test_default_roles_are_seeded(self):
        for code in ['admin', 'developer', 'manager', 'editor', 'contributor', 'viewer']:
            role = self.role(code)
            self.assertTrue(role.can_access_dashboard, code)
        self.assertEqual(sorted(self.role('editor').dashboard_permissions), sorted(DEFAULT_ROLE_PERMISSIONS['editor']))

    def test_editor_sees_content_only(self):
        editor = make_user('editor-a', 'editor')
        self.assertTrue(has_dashboard_access(editor))
        self.assertTrue(has_dashboard_permission(editor, 'content.create'))
        for denied in ['users.view', 'settings.view', 'forms.view', 'roles.view', 'reports.view', 'premium.view']:
            self.assertFalse(has_dashboard_permission(editor, denied), denied)
        self.client.force_login(editor)
        self.assertEqual(self.client.get('/api/dashboard/posts/').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/users/').status_code, 403)
        self.assertEqual(self.client.get('/api/dashboard/settings/').status_code, 403)
        self.assertEqual(self.client.get('/api/dashboard/roles-permissions/').status_code, 403)
        modules = {item['id']: item['enabled'] for item in self.client.get('/api/dashboard/bootstrap/').json()['modules']}
        self.assertTrue(modules['content'])
        self.assertFalse(modules['users'])
        self.assertFalse(modules['settings'])

    def test_contributor_cannot_delete_or_manage_taxonomy(self):
        contributor = make_user('contrib-a', 'contributor')
        self.client.force_login(contributor)
        self.assertEqual(self.post('/api/dashboard/categories/save/', {'name': 'New'}).status_code, 403)
        self.assertEqual(self.post('/api/dashboard/posts/bulk/', {'action': 'publish', 'ids': []}).status_code, 403)

    def test_developer_and_manager_scopes(self):
        developer = make_user('dev-a', 'developer')
        manager = make_user('mgr-a', 'manager')
        self.assertTrue(has_dashboard_permission(developer, 'settings.edit'))
        self.assertFalse(has_dashboard_permission(developer, 'users.view'))
        self.assertFalse(has_dashboard_permission(developer, 'content.edit'))
        self.assertTrue(has_dashboard_permission(manager, 'reports.manage'))
        self.assertTrue(has_dashboard_permission(manager, 'users.view'))
        self.assertFalse(has_dashboard_permission(manager, 'users.edit'))
        self.assertFalse(has_dashboard_permission(manager, 'settings.view'))

    def test_superuser_always_has_everything(self):
        superuser = make_user('root-a', superuser=True)
        admin_role = self.role('admin')
        admin_role.is_active = False
        admin_role.save()
        self.assertEqual(permissions_for_user(superuser), ALL_PERMISSIONS)
        self.assertTrue(has_dashboard_permission(superuser, 'roles.delete'))

    def test_legacy_permission_names_still_resolve(self):
        editor = make_user('editor-legacy-name', 'editor')
        self.assertTrue(has_dashboard_permission(editor, 'content.read'))
        self.assertTrue(has_dashboard_permission(editor, 'content.write'))
        self.assertFalse(has_dashboard_permission(editor, 'users.read'))

    def test_team_role_fallback_uses_stored_permissions(self):
        user = User.objects.create_user('team-viewer', 'team-viewer@example.com', PASSWORD, is_staff=True)
        TeamMember.objects.create(user=user, role='viewer')
        viewer = self.role('viewer')
        viewer.dashboard_permissions = ['dashboard.view', 'reports.view']
        viewer.save()
        self.assertEqual(get_dashboard_role(user), 'viewer')
        self.assertEqual(permissions_for_user(user), ['dashboard.view', 'reports.view'])

    def test_inactive_role_removes_dashboard_access(self):
        user = make_user('dev-off', 'developer')
        developer = self.role('developer')
        developer.is_active = False
        developer.save()
        clear_role_cache(user)
        user = User.objects.get(pk=user.pk)
        self.assertFalse(has_dashboard_access(user))


class PerActionEnforcementTests(RolesTestCase):
    def setUp(self):
        self.role_obj = AccountRole.objects.create(
            code='media_desk', label='Media desk', can_access_dashboard=True,
            dashboard_permissions=['dashboard.view', 'media.view', 'taxonomy.view', 'taxonomy.edit'],
        )
        self.user = make_user('media-desk')
        self.user.membership_profile.account_role = self.role_obj
        self.user.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.client.force_login(self.user)

    def test_create_and_edit_are_separate(self):
        from blog.models import Category
        category = Category.objects.create(name='Existing', slug='existing')
        self.assertEqual(self.post('/api/dashboard/categories/save/', {'name': 'Fresh'}).status_code, 403)
        response = self.post(f'/api/dashboard/categories/{category.pk}/save/', {'name': 'Renamed'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.post(f'/api/dashboard/categories/{category.pk}/delete/').status_code, 403)

    def test_view_without_other_modules(self):
        self.assertEqual(self.client.get('/api/dashboard/media/').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/posts/').status_code, 403)
        self.assertEqual(self.client.get('/api/dashboard/faq/items/').status_code, 403)

    def test_changes_apply_without_code_changes(self):
        self.assertEqual(self.client.get('/api/dashboard/faq/items/').status_code, 403)
        self.role_obj.dashboard_permissions = self.role_obj.dashboard_permissions + ['faq.view']
        self.role_obj.save()
        self.assertEqual(self.client.get('/api/dashboard/faq/items/').status_code, 200)


class RolesApiTests(RolesTestCase):
    def setUp(self):
        self.superuser = make_user('root-b', superuser=True)

    def test_list_roles(self):
        self.client.force_login(self.superuser)
        data = self.client.get('/api/dashboard/roles-permissions/').json()
        codes = [role['code'] for role in data['roles']]
        for code in ['admin', 'developer', 'manager', 'editor', 'contributor']:
            self.assertIn(code, codes)
        self.assertNotIn('free', codes)
        self.assertEqual([action['id'] for action in data['actions']], ['view', 'create', 'edit', 'delete', 'manage'])
        admin = next(role for role in data['roles'] if role['code'] == 'admin')
        self.assertTrue(admin['locked'])
        self.assertTrue(data['can']['edit'])

    def test_create_edit_delete_custom_role(self):
        self.client.force_login(self.superuser)
        response = self.post('/api/dashboard/roles/save/', {'label': 'Reviewer', 'permissions': ['content.view', 'faq.view']})
        self.assertEqual(response.status_code, 200, response.content)
        role = response.json()['role']
        self.assertEqual(role['code'], 'reviewer')
        self.assertEqual(role['permissions'], ['content.view', 'dashboard.view', 'faq.view'])
        response = self.post(f"/api/dashboard/roles/{role['id']}/save/", {'label': 'Reviewer', 'permissions': ['content.view', 'content.edit']})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('content.edit', AccountRole.objects.get(pk=role['id']).dashboard_permissions)
        self.assertEqual(self.post(f"/api/dashboard/roles/{role['id']}/delete/").status_code, 200)
        self.assertFalse(AccountRole.objects.filter(pk=role['id']).exists())

    def test_rejects_unknown_permissions_and_duplicate_codes(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.post('/api/dashboard/roles/save/', {'label': 'X', 'permissions': ['root.everything']}).status_code, 400)
        self.assertEqual(self.post('/api/dashboard/roles/save/', {'label': 'Editor', 'permissions': []}).status_code, 400)

    def test_admin_role_is_locked(self):
        self.client.force_login(self.superuser)
        admin = self.role('admin')
        response = self.post(f'/api/dashboard/roles/{admin.pk}/save/', {'label': admin.label, 'permissions': ['dashboard.view']})
        self.assertEqual(response.status_code, 403)
        response = self.post(f'/api/dashboard/roles/{admin.pk}/save/', {'label': admin.label, 'is_active': False})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post(f'/api/dashboard/roles/{admin.pk}/delete/').status_code, 400)

    def test_builtin_roles_cannot_be_deleted(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.post(f"/api/dashboard/roles/{self.role('editor').pk}/delete/").status_code, 400)

    def test_role_with_users_cannot_be_deleted(self):
        self.client.force_login(self.superuser)
        role = AccountRole.objects.create(code='temp_role', label='Temp', can_access_dashboard=True, dashboard_permissions=['dashboard.view'])
        holder = make_user('temp-holder')
        holder.membership_profile.account_role = role
        holder.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.assertEqual(self.post(f'/api/dashboard/roles/{role.pk}/delete/').status_code, 400)

    def test_roles_page_needs_roles_permission(self):
        self.client.force_login(make_user('mgr-b', 'manager'))
        self.assertEqual(self.client.get('/api/dashboard/roles-permissions/').status_code, 403)
        self.assertEqual(self.post('/api/dashboard/roles/save/', {'label': 'Sneaky', 'permissions': []}).status_code, 403)


class LockoutAndEscalationTests(RolesTestCase):
    def setUp(self):
        self.access_admin = AccountRole.objects.create(
            code='access_admin', label='Access admin', can_access_dashboard=True,
            dashboard_permissions=['dashboard.view', 'roles.view', 'roles.create', 'roles.edit', 'roles.delete', 'content.view'],
        )
        self.actor = make_user('access-admin')
        self.actor.membership_profile.account_role = self.access_admin
        self.actor.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.client.force_login(self.actor)

    def test_cannot_change_own_role(self):
        url = f'/api/dashboard/roles/{self.access_admin.pk}/save/'
        response = self.post(url, {'label': 'Access admin', 'permissions': ['dashboard.view']})
        self.assertEqual(response.status_code, 403)
        response = self.post(url, {'label': 'Access admin', 'is_active': False})
        self.assertEqual(response.status_code, 403)
        self.access_admin.refresh_from_db()
        self.assertIn('roles.edit', self.access_admin.dashboard_permissions)
        self.assertTrue(self.access_admin.is_active)

    def test_can_rename_own_role(self):
        response = self.post(f'/api/dashboard/roles/{self.access_admin.pk}/save/', {'label': 'Access lead', 'description': 'Runs roles'})
        self.assertEqual(response.status_code, 200, response.content)

    def test_cannot_grant_permissions_they_do_not_have(self):
        response = self.post('/api/dashboard/roles/save/', {'label': 'Too much', 'permissions': ['users.edit']})
        self.assertEqual(response.status_code, 403)
        editor = self.role('editor')
        response = self.post(f'/api/dashboard/roles/{editor.pk}/save/', {'label': editor.label, 'permissions': editor.dashboard_permissions + ['settings.edit']})
        self.assertEqual(response.status_code, 403)

    def test_can_remove_permissions_from_other_roles(self):
        editor = self.role('editor')
        response = self.post(f'/api/dashboard/roles/{editor.pk}/save/', {'label': editor.label, 'permissions': ['content.view']})
        self.assertEqual(response.status_code, 200, response.content)
        editor.refresh_from_db()
        self.assertEqual(editor.dashboard_permissions, ['content.view', 'dashboard.view'])

    def test_cannot_delete_own_role(self):
        self.assertEqual(self.post(f'/api/dashboard/roles/{self.access_admin.pk}/delete/').status_code, 403)

    def test_cannot_change_own_account_role_on_users_page(self):
        self.access_admin.dashboard_permissions = self.access_admin.dashboard_permissions + ['users.view', 'users.edit']
        self.access_admin.save()
        response = self.post(f'/api/dashboard/users/{self.actor.pk}/save/', {
            'email': self.actor.email, 'username': self.actor.username, 'account_role': 'admin',
        })
        self.assertEqual(response.status_code, 403)


class PreviousAccessMigrationTests(TestCase):
    """The data migration keeps what existing editors and contributors could do."""

    def run_migration(self):
        module = importlib.import_module('dashboard.migrations.0014_seed_dashboard_roles')
        module.seed_roles(django_apps, None)

    def test_existing_editor_keeps_old_access(self):
        editor = User.objects.create_user('old-editor', 'old-editor@example.com', PASSWORD, is_staff=True)
        TeamMember.objects.create(user=editor, role='editor')
        contributor = User.objects.create_user('old-contrib', 'old-contrib@example.com', PASSWORD, is_staff=True)
        TeamMember.objects.create(user=contributor, role='contributor')
        no_access = User.objects.create_user('not-staff-editor', 'nse@example.com', PASSWORD, is_staff=False)
        TeamMember.objects.create(user=no_access, role='editor')

        self.run_migration()

        editor = User.objects.get(pk=editor.pk)
        self.assertEqual(get_dashboard_role(editor), 'editor_previous')
        self.assertTrue(has_dashboard_access(editor))
        for permission in ['users.view', 'forms.edit', 'reports.manage', 'content.edit', 'activity.view']:
            self.assertTrue(has_dashboard_permission(editor, permission), permission)
        self.assertFalse(has_dashboard_permission(editor, 'users.edit'))
        self.assertFalse(has_dashboard_permission(editor, 'content.delete'))

        contributor = User.objects.get(pk=contributor.pk)
        self.assertEqual(get_dashboard_role(contributor), 'contributor_previous')
        self.assertEqual(
            sorted(permissions_for_user(contributor)),
            sorted(set(translate_legacy_permissions(['dashboard.view', 'content.read', 'content.write', 'forms.read', 'opportunities.read', 'services.read', 'team.read']))),
        )

        no_access = User.objects.get(pk=no_access.pk)
        self.assertFalse(has_dashboard_access(no_access))
        self.assertIsNone(no_access.membership_profile.account_role_id)


class RoleAssignmentTests(RolesTestCase):
    def setUp(self):
        self.superuser = make_user('root-c', superuser=True)
        self.target = make_user('assign-me', staff=False)

    def test_superuser_assigns_and_removes_a_role(self):
        self.client.force_login(self.superuser)
        manager = self.role('manager')
        response = self.post(f'/api/dashboard/roles/{manager.pk}/members/', {'user_id': self.target.pk, 'action': 'add'})
        self.assertEqual(response.status_code, 200, response.content)
        target = User.objects.get(pk=self.target.pk)
        self.assertEqual(get_dashboard_role(target), 'manager')
        self.assertTrue(has_dashboard_access(target))
        response = self.post(f'/api/dashboard/roles/{manager.pk}/members/', {'user_id': self.target.pk, 'action': 'remove'})
        self.assertEqual(response.status_code, 200, response.content)
        target = User.objects.get(pk=self.target.pk)
        self.assertFalse(has_dashboard_access(target))

    def test_assigner_cannot_hand_out_more_than_they_have(self):
        assigner_role = AccountRole.objects.create(
            code='people_lead', label='People lead', can_access_dashboard=True,
            dashboard_permissions=['dashboard.view', 'roles.view', 'roles.manage', 'content.view', 'content.create', 'content.edit'],
        )
        assigner = make_user('people-lead')
        assigner.membership_profile.account_role = assigner_role
        assigner.membership_profile.save(update_fields=['account_role', 'updated_at'])
        self.client.force_login(assigner)
        contributor_like = AccountRole.objects.create(
            code='writer', label='Writer', can_access_dashboard=True,
            dashboard_permissions=['dashboard.view', 'content.view', 'content.create'],
        )
        url = f'/api/dashboard/roles/{contributor_like.pk}/members/'
        self.assertEqual(self.post(url, {'user_id': self.target.pk, 'action': 'add'}).status_code, 200)
        manager = self.role('manager')
        self.assertEqual(self.post(f'/api/dashboard/roles/{manager.pk}/members/', {'user_id': self.target.pk, 'action': 'add'}).status_code, 403)
        admin = self.role('admin')
        self.assertEqual(self.post(f'/api/dashboard/roles/{admin.pk}/members/', {'user_id': self.target.pk, 'action': 'add'}).status_code, 403)
        # Cannot move themselves, and cannot touch a superuser.
        self.assertEqual(self.post(url, {'user_id': assigner.pk, 'action': 'add'}).status_code, 403)
        self.assertEqual(self.post(url, {'user_id': self.superuser.pk, 'action': 'add'}).status_code, 403)

    def test_assignment_needs_roles_manage(self):
        self.client.force_login(make_user('dev-c', 'developer'))
        response = self.post(f"/api/dashboard/roles/{self.role('viewer').pk}/members/", {'user_id': self.target.pk, 'action': 'add'})
        self.assertEqual(response.status_code, 403)
