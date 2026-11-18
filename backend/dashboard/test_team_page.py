import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounts.models import AccountRole
from blog.models import MediaAsset
from dashboard.models import TeamPageMember, TeamPageSection, TeamPageSettings

API = '/api/dashboard/team-page'


class TeamPageTestCase(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser('team-root', password='test-only-password')
        self.client.force_login(self.super_admin)
        self.section = TeamPageSection.objects.get(level='founder')

    def post(self, path, body=None):
        return self.client.post(f'{API}/{path}', json.dumps(body or {}), content_type='application/json')

    def member(self, **kwargs):
        values = {'section': self.section, 'full_name': 'A Person', 'role': 'Editor', 'status': 'published', **kwargs}
        return TeamPageMember.objects.create(**values)

    def publish(self):
        return self.post('publish/', {'published': True})


class TeamPageAccessTests(TeamPageTestCase):
    def staff_with_role(self, username, code, **role_fields):
        role, _ = AccountRole.objects.update_or_create(code=code, defaults={'label': code, 'can_access_dashboard': True, 'is_active': True, **role_fields})
        user = User.objects.create_user(username, password='test-only-password', is_staff=True)
        user.membership_profile.account_role = role
        user.membership_profile.save(update_fields=['account_role', 'updated_at'])
        return user

    def test_regular_admin_is_refused_everywhere(self):
        member = self.member()
        self.client.force_login(self.staff_with_role('plain-admin', 'admin', dashboard_permissions=['*']))
        self.assertEqual(self.client.get(f'{API}/').status_code, 403)
        self.assertEqual(self.client.get(f'{API}/preview/').status_code, 403)
        for path in ('settings/', 'publish/', 'sections/save/', 'sections/reorder/', 'members/save/', 'members/arrange/',
                     f'sections/{self.section.pk}/save/', f'sections/{self.section.pk}/delete/',
                     f'members/{member.pk}/save/', f'members/{member.pk}/delete/'):
            self.assertEqual(self.post(path, {'published': True}).status_code, 403, path)
        self.assertTrue(TeamPageMember.objects.filter(pk=member.pk).exists())
        self.assertFalse(TeamPageSettings.is_live())

    def test_super_admin_role_is_allowed(self):
        self.client.force_login(self.staff_with_role('role-root', 'super_admin', is_super_admin=True))
        self.assertEqual(self.client.get(f'{API}/').status_code, 200)

    def test_inactive_super_admin_role_is_refused(self):
        self.client.force_login(self.staff_with_role('role-off', 'super_admin', is_super_admin=True, is_active=False))
        self.assertEqual(self.client.get(f'{API}/').status_code, 403)

    def test_anonymous_is_refused(self):
        self.client.logout()
        self.assertEqual(self.client.get(f'{API}/').status_code, 401)
        self.assertEqual(self.client.get(f'{API}/preview/').status_code, 401)

    def test_bootstrap_says_who_is_super_admin(self):
        self.assertTrue(self.client.get('/api/dashboard/bootstrap/').json()['is_super_admin'])
        self.client.force_login(self.staff_with_role('plain-admin-2', 'admin', dashboard_permissions=['*']))
        self.assertFalse(self.client.get('/api/dashboard/bootstrap/').json()['is_super_admin'])


class TeamPagePublishingTests(TeamPageTestCase):
    def test_page_starts_unpublished(self):
        self.member()
        self.assertFalse(TeamPageSettings.load().is_published)
        self.client.logout()
        self.assertEqual(self.client.get('/api/team/').status_code, 404)

    def test_publish_refused_with_nothing_to_show(self):
        self.member(status='draft')
        self.assertEqual(self.publish().status_code, 400)
        self.assertFalse(TeamPageSettings.is_live())

    def test_publish_and_unpublish(self):
        self.member(full_name='Shown')
        response = self.publish()
        self.assertTrue(response.json()['settings']['is_published'])
        self.client.logout()
        self.assertEqual(self.client.get('/api/team/').json()['sections'][0]['members'][0]['full_name'], 'Shown')
        self.client.force_login(self.super_admin)
        self.post('publish/', {'published': False})
        self.client.logout()
        self.assertEqual(self.client.get('/api/team/').status_code, 404)

    def test_public_page_leaves_out_drafts_hidden_and_empty_sections(self):
        hidden = TeamPageSection.objects.create(name='Hidden', is_visible=False)
        empty = TeamPageSection.objects.create(name='Empty')
        self.member(section=hidden, full_name='In hidden section')
        self.member(full_name='Published')
        self.member(full_name='Unfinished', status='draft')
        self.publish()
        self.client.logout()
        data = self.client.get('/api/team/').json()
        self.assertEqual([section['id'] for section in data['sections']], [self.section.pk])
        self.assertNotIn(empty.pk, [section['id'] for section in data['sections']])
        self.assertEqual([member['full_name'] for member in data['sections'][0]['members']], ['Published'])
        self.assertNotIn('is_draft', data['sections'][0]['members'][0])

    def test_vision_is_only_public_for_the_founder_level(self):
        team = TeamPageSection.objects.create(name='Web team', level='team')
        self.member(vision='Founder words')
        self.member(section=team, full_name='Team person', vision='Left over')
        self.publish()
        sections = {section['level']: section for section in self.client.get('/api/team/').json()['sections']}
        self.assertEqual(sections['founder']['members'][0]['vision'], 'Founder words')
        self.assertEqual(sections['team']['members'][0]['vision'], '')

    def test_preview_works_while_unpublished_and_can_include_drafts(self):
        self.member(full_name='Published')
        self.member(full_name='Unfinished', status='draft')
        names = lambda data: [member['full_name'] for member in data['sections'][0]['members']]
        data = self.client.get(f'{API}/preview/').json()
        self.assertFalse(data['is_published'])
        self.assertEqual(names(data), ['Published'])
        self.assertEqual(names(self.client.get(f'{API}/preview/?drafts=1').json()), ['Published', 'Unfinished'])

    @override_settings(SERVE_FRONTEND_FROM_DJANGO=False)
    def test_seo_hides_the_page_until_published(self):
        from resref import seo

        self.member()
        self.assertEqual(seo.resolve(self.client.get('/').wsgi_request, '/team').status, 404)
        self.assertNotIn('/team', [path for path, _ in seo.sitemap_entries()])
        self.publish()
        self.assertEqual(seo.resolve(self.client.get('/').wsgi_request, '/team').status, 200)
        self.assertIn('/team', [path for path, _ in seo.sitemap_entries()])
        self.assertIn('noindex', seo.resolve(self.client.get('/').wsgi_request, '/team/preview').robots)


class TeamPageManagementTests(TeamPageTestCase):
    def test_sections_are_seeded_with_the_page_unpublished(self):
        self.assertEqual(list(TeamPageSection.objects.values_list('level', flat=True)), ['founder', 'leadership', 'directors'])

    def test_draft_needs_only_a_name(self):
        response = self.post('members/save/', {'section_id': self.section.pk, 'full_name': 'Name only', 'status': 'draft'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['member']['status'], 'draft')
        self.assertEqual(self.post('members/save/', {'section_id': self.section.pk, 'full_name': ''}).status_code, 400)

    def test_publishing_a_member_needs_a_role(self):
        member = self.member(role='', status='draft')
        self.assertEqual(self.post(f'members/{member.pk}/save/', {'status': 'published'}).status_code, 400)
        member.refresh_from_db()
        self.assertEqual(member.status, 'draft')
        self.assertEqual(self.post(f'members/{member.pk}/save/', {'status': 'published', 'role': 'Director'}).status_code, 200)

    def test_links_are_checked(self):
        member = self.member()
        save = lambda links: self.post(f'members/{member.pk}/save/', {'links': links})
        self.assertEqual(save([{'label': 'Bad', 'url': 'javascript:alert(1)'}]).status_code, 400)
        self.assertEqual(save([{'label': 'Bad', 'url': 'mailto:not-an-email'}]).status_code, 400)
        self.assertEqual(save([{'label': 'No address', 'url': ''}]).status_code, 400)
        self.assertEqual(save([{'label': 'x', 'url': 'https://example.com'}] * 7).status_code, 400)
        self.assertEqual(save([{'label': '', 'url': ''}, {'label': 'Site', 'url': 'https://example.com'}, {'label': 'Mail', 'url': 'mailto:a@example.com'}]).status_code, 200)
        member.refresh_from_db()
        self.assertEqual([link['label'] for link in member.links], ['Site', 'Mail'])

    def test_photo_must_exist(self):
        member = self.member()
        self.assertEqual(self.post(f'members/{member.pk}/save/', {'photo_id': 999999}).status_code, 400)
        asset = MediaAsset.objects.create(title='Portrait', url='https://example.com/p.jpg')
        response = self.post(f'members/{member.pk}/save/', {'photo_id': asset.pk})
        self.assertEqual(response.json()['member']['photo_url'], 'https://example.com/p.jpg')

    def test_moving_a_member_by_editing_puts_them_last(self):
        other = TeamPageSection.objects.create(name='Other')
        self.member(section=other, sort_order=4)
        member = self.member()
        self.post(f'members/{member.pk}/save/', {'section_id': other.pk})
        member.refresh_from_db()
        self.assertEqual((member.section_id, member.sort_order), (other.pk, 5))

    def test_arrange_orders_and_moves_members(self):
        other = TeamPageSection.objects.create(name='Other')
        first, second = self.member(section=other, full_name='First'), self.member(section=other, full_name='Second')
        arriving = self.member(full_name='Arriving')
        response = self.post('members/arrange/', {'section_id': other.pk, 'ids': [arriving.pk, second.pk, first.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(other.members.values_list('full_name', flat=True)), ['Arriving', 'Second', 'First'])

    def test_arrange_handles_long_lists(self):
        members = [self.member(full_name=f'Person {index}') for index in range(15)]
        ids = [member.pk for member in reversed(members)]
        self.post('members/arrange/', {'section_id': self.section.pk, 'ids': ids})
        self.assertEqual(list(self.section.members.values_list('pk', flat=True)), ids)

    def test_reorder_rename_and_hide_sections(self):
        ids = list(TeamPageSection.objects.values_list('pk', flat=True))
        self.post('sections/reorder/', {'ids': list(reversed(ids))})
        self.assertEqual(list(TeamPageSection.objects.values_list('pk', flat=True)), list(reversed(ids)))
        self.post(f'sections/{ids[0]}/save/', {'name': 'Renamed', 'is_visible': False})
        section = TeamPageSection.objects.get(pk=ids[0])
        self.assertEqual((section.name, section.is_visible, section.level), ('Renamed', False, 'founder'))

    def test_new_sections_join_the_end_and_level_is_checked(self):
        response = self.post('sections/save/', {'name': 'Web team', 'level': 'team'})
        self.assertEqual(TeamPageSection.objects.last().pk, response.json()['section']['id'])
        self.assertEqual(self.post('sections/save/', {'name': 'Bad', 'level': 'nope'}).status_code, 400)
        self.assertEqual(self.post('sections/save/', {'name': ''}).status_code, 400)

    def test_section_with_members_cannot_be_deleted(self):
        member = self.member()
        self.assertEqual(self.post(f'sections/{self.section.pk}/delete/').status_code, 400)
        self.assertEqual(self.post(f'members/{member.pk}/delete/').status_code, 200)
        self.assertEqual(self.post(f'sections/{self.section.pk}/delete/').status_code, 200)
