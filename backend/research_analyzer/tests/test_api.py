import io
import json
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

import pandas as pd
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import UsageLimit, UsageRecord
from research_analyzer.services.data_service import MAX_COLS, MAX_ROWS, parse_uploaded_file
from research_analyzer.services.stats_service import chi_square, linear_regression
from research_analyzer import session_store
from research_analyzer.models import AnalyzerSession


class TempStorageMixin:
    """Each test writes analyzer datasets to its own temporary directory."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # rate-limit counters must not leak between tests
        self._storage = tempfile.mkdtemp(prefix='analyzer-test-')
        self._storage_override = override_settings(ANALYZER_STORAGE_DIR=self._storage)
        self._storage_override.enable()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._storage_override.disable()
        shutil.rmtree(self._storage, ignore_errors=True)


class ResearchAnalyzerApiTests(TempStorageMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(
            username='analyzer-admin',
            email='admin@example.com',
            password='pass12345',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_upload_requires_sign_in(self):
        response = Client().post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', b'score\n1\n', content_type='text/csv')},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'auth_required')

    def test_upload_prepare_and_report_flow(self):
        csv = b'score,group\n40,A\n42,A\n60,B\n62,B\n'
        upload = self.client.post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', csv, content_type='text/csv')},
        )
        self.assertEqual(upload.status_code, 200)
        session_id = upload.json()['session_id']

        prepare = self.client.post(
            '/api/research-analyzer/prepare/',
            data=json.dumps({'session_id': session_id, 'options': {'trim_whitespace': True}}),
            content_type='application/json',
        )
        self.assertEqual(prepare.status_code, 200)
        self.assertIn('variables', prepare.json())

        variables = [
            {'name': 'score', 'type': 'numeric', 'role': 'outcome'},
            {'name': 'group', 'type': 'categorical', 'role': 'grouping'},
        ]
        variable_update = self.client.post(
            '/api/research-analyzer/variables/',
            data=json.dumps({'session_id': session_id, 'variables': variables}),
            content_type='application/json',
        )
        self.assertEqual(variable_update.status_code, 200)

        generated = self.client.post(
            '/api/research-analyzer/report/generate/',
            data=json.dumps({'session_id': session_id}),
            content_type='application/json',
        )
        self.assertEqual(generated.status_code, 200)
        generated_payload = generated.json()
        self.assertTrue(generated_payload['success'])
        self.assertTrue(generated_payload['analyses'])

        report = self.client.get('/api/research-analyzer/report/', {'session_id': session_id})
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.json()['sections']['descriptive'])

    def test_rejects_unknown_variable(self):
        upload = self.client.post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', b'score\n1\n2\n', content_type='text/csv')},
        )
        session_id = upload.json()['session_id']
        response = self.client.post(
            '/api/research-analyzer/variables/',
            data=json.dumps({'session_id': session_id, 'variables': [{'name': 'missing', 'type': 'numeric'}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown variable', response.json()['error'])

    def test_csv_parser_applies_row_limit_during_read(self):
        with patch(
            'research_analyzer.services.data_service.pd.read_csv',
            return_value=pd.DataFrame({'score': [1]}),
        ) as reader:
            parsed = parse_uploaded_file(io.BytesIO(b'score\n1\n'), 'study.csv')

        self.assertEqual(len(parsed), 1)
        self.assertEqual(reader.call_args.kwargs['nrows'], MAX_ROWS + 1)

    def test_json_parser_rejects_deep_nesting_before_pandas_parses(self):
        payload = b'[' * 65 + b'0' + b']' * 65

        with self.assertRaisesRegex(ValueError, 'nesting exceeds 64'):
            parse_uploaded_file(io.BytesIO(payload), 'study.json')

    def test_json_record_array_remains_supported(self):
        parsed = parse_uploaded_file(
            io.BytesIO(b'[{"score": 1, "group": "A"}, {"score": 2, "group": "B"}]'),
            'study.json',
        )

        self.assertEqual(parsed.columns.tolist(), ['score', 'group'])
        self.assertEqual(parsed['score'].tolist(), [1, 2])

    def test_json_array_rejects_projected_cell_limit_before_dataframe_creation(self):
        with patch('research_analyzer.services.data_service.MAX_CELLS', 2), patch(
            'research_analyzer.services.data_service.pd.DataFrame.from_records'
        ) as from_records:
            with self.assertRaisesRegex(ValueError, 'cell limit'):
                parse_uploaded_file(io.BytesIO(b'[{"a": 1, "b": 2}, {"a": 3, "b": 4}]'), 'study.json')

        from_records.assert_not_called()

    def test_json_array_rejects_trailing_data(self):
        with self.assertRaisesRegex(ValueError, 'trailing data'):
            parse_uploaded_file(io.BytesIO(b'[{"score": 1}] trailing'), 'study.json')

    def test_json_parser_rejects_excess_rows_with_bounded_read(self):
        with patch(
            'research_analyzer.services.data_service.pd.read_json',
            return_value=pd.DataFrame({'score': range(MAX_ROWS + 1)}),
        ) as reader:
            with self.assertRaisesRegex(ValueError, 'row limit'):
                parse_uploaded_file(io.BytesIO(b'{"score": 1}\n{"score": 2}\n'), 'study.json')

        self.assertTrue(reader.call_args.kwargs['lines'])
        self.assertEqual(reader.call_args.kwargs['nrows'], MAX_ROWS + 1)

    def test_json_parser_rejects_excess_columns(self):
        frame = pd.DataFrame([[1] * (MAX_COLS + 1)], columns=[f'c{index}' for index in range(MAX_COLS + 1)])
        with patch('research_analyzer.services.data_service.pd.read_json', return_value=frame):
            with self.assertRaisesRegex(ValueError, 'column limit'):
                parse_uploaded_file(io.BytesIO(b'{"score": 1}\n{"score": 2}\n'), 'study.json')

    def test_owner_session_limit_never_evicts_another_users_session(self):
        frame = pd.DataFrame({'score': [1]})
        other_user = User.objects.create_user('other-analyzer', 'other@example.com', 'pass12345')
        other_session = session_store.create_session(other_user, 'other.csv', frame, [])
        for _ in range(5):
            session_store.create_session(self.user, 'mine.csv', frame, [])
        self.assertTrue(AnalyzerSession.objects.filter(pk=other_session.pk).exists())

    def test_uploads_are_free_and_analysis_runs_are_metered(self):
        user = User.objects.create_user(
            username='limited-analyzer',
            email='limited-analyzer@example.com',
            password='pass12345',
        )
        user.membership_profile.tier = 'premium'
        user.membership_profile.save(update_fields=['tier', 'updated_at'])
        UsageLimit.objects.update_or_create(
            feature_code='research_analyzer',
            tier='premium',
            period='month',
            defaults={'limit': 1, 'is_active': True},
        )
        self.client.force_login(user)
        upload_file = lambda: SimpleUploadedFile('study.csv', b'score\n1\n2\n', content_type='text/csv')

        first = self.client.post('/api/research-analyzer/upload/', {'file': upload_file()})
        second = self.client.post('/api/research-analyzer/upload/', {'file': upload_file()})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(UsageRecord.objects.filter(user=user).exists())

        def analyze():
            return self.client.post(
                '/api/research-analyzer/analyze/',
                data=json.dumps({
                    'session_id': first.json()['session_id'],
                    'test': 'descriptive',
                    'params': {'variables': [{'name': 'score', 'type': 'numeric'}]},
                }),
                content_type='application/json',
            )

        self.assertEqual(analyze().status_code, 200)
        blocked = analyze()
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()['code'], 'usage_limit')
        self.assertEqual(UsageRecord.objects.filter(user=user, feature_code='research_analyzer').count(), 1)

    def test_failed_analysis_attempts_consume_quota_before_work(self):
        user = User.objects.create_user('limited-failing-analysis', 'failure@example.com', 'pass12345')
        user.membership_profile.tier = 'premium'
        user.membership_profile.save(update_fields=['tier', 'updated_at'])
        UsageLimit.objects.update_or_create(
            feature_code='research_analyzer', tier='premium', period='month',
            defaults={'limit': 1, 'is_active': True},  # uploads are free (T-12)
        )
        self.client.force_login(user)
        upload = self.client.post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', b'score\n1\n2\n', content_type='text/csv')},
        )
        session_id = upload.json()['session_id']

        with patch('research_analyzer.views.run_test', return_value={'error': 'invalid test parameters'}):
            first = self.client.post(
                '/api/research-analyzer/analyze/',
                data=json.dumps({'session_id': session_id, 'test': 'pearson', 'params': {}}),
                content_type='application/json',
            )
            second = self.client.post(
                '/api/research-analyzer/analyze/',
                data=json.dumps({'session_id': session_id, 'test': 'pearson', 'params': {}}),
                content_type='application/json',
            )

        self.assertEqual(first.status_code, 422)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()['code'], 'usage_limit')
        self.assertEqual(UsageRecord.objects.filter(user=user, feature_code='research_analyzer').count(), 1)

    def test_master_analysis_checks_usage_before_running_expensive_work(self):
        user = User.objects.create_user(
            username='limited-master-analysis',
            email='limited-master-analysis@example.com',
            password='pass12345',
        )
        user.membership_profile.tier = 'premium'
        user.membership_profile.save(update_fields=['tier', 'updated_at'])
        UsageLimit.objects.update_or_create(
            feature_code='research_analyzer',
            tier='premium',
            period='month',
            defaults={'limit': 0, 'is_active': True},  # quota already used up
        )
        self.client.force_login(user)
        upload = self.client.post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', b'score\n1\n2\n', content_type='text/csv')},
        )
        session_id = upload.json()['session_id']

        with patch('research_analyzer.views.run_analysis_plan') as run_analysis_plan:
            response = self.client.post(
                '/api/research-analyzer/report/generate/',
                data=json.dumps({'session_id': session_id}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['code'], 'usage_limit')
        run_analysis_plan.assert_not_called()

    def test_high_cardinality_analyses_return_actionable_errors(self):
        frame = pd.DataFrame({
            'outcome': range(101),
            'group': [f'group-{index}' for index in range(101)],
            'category': [f'category-{index}' for index in range(101)],
        })

        chi_result = chi_square(frame, 'group', 'category')
        regression_result = linear_regression(frame, 'outcome', ['group'], ['group'])

        self.assertIn('too large', chi_result['error'].lower())
        self.assertIn('too many categories', regression_result['error'].lower())


class AnalyzerSessionStoreTests(TempStorageMixin, TestCase):
    """T-11: sessions live on disk with metadata in the database."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser('store-admin', 'store-admin@example.com', 'pass12345')
        self.client.force_login(self.user)

    def _upload(self, client=None, body=b'score,group\n1,A\n2,B\n3,A\n'):
        response = (client or self.client).post(
            '/api/research-analyzer/upload/',
            {'file': SimpleUploadedFile('study.csv', body, content_type='text/csv')},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['session_id']

    def test_dtypes_survive_round_trip(self):
        frame = pd.DataFrame({
            'count': pd.array([1, None, 3], dtype='Int64'),
            'group': pd.Categorical(['a', 'b', 'a']),
            'when': pd.to_datetime(['2026-01-01', '2026-02-01', '2026-03-01']),
            'mixed': ['x', 2, None],
        })
        session = session_store.create_session(self.user, 'frame.csv', frame, [])
        loaded = session_store.load_dataframe(session)
        pd.testing.assert_frame_equal(loaded, frame)

    def test_session_is_shared_through_the_database_not_process_memory(self):
        session_id = self._upload()
        self.assertTrue(AnalyzerSession.objects.filter(pk=session_id).exists())
        report = self.client.get('/api/research-analyzer/report/', {'session_id': session_id})
        self.assertEqual(report.status_code, 200)

    def test_other_users_cannot_open_a_session(self):
        session_id = self._upload()
        other = User.objects.create_user('other-analyst', 'other@example.com', 'pass12345')
        other.membership_profile.tier = 'premium'
        other.membership_profile.save(update_fields=['tier', 'updated_at'])
        client = Client()
        client.force_login(other)
        response = client.get('/api/research-analyzer/report/', {'session_id': session_id})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post(f'/api/research-analyzer/session/{session_id}/clear/').status_code, 200)

    @override_settings(ANALYZER_MAX_SESSIONS_PER_USER=2)
    def test_per_user_cap_removes_oldest_sessions(self):
        first = self._upload()
        self._upload()
        self._upload()
        self.assertEqual(AnalyzerSession.objects.filter(user=self.user).count(), 2)
        self.assertFalse(AnalyzerSession.objects.filter(pk=first).exists())

    def test_expired_sessions_are_rejected_and_cleaned_up(self):
        session_id = self._upload()
        session = AnalyzerSession.objects.get(pk=session_id)
        AnalyzerSession.objects.filter(pk=session_id).update(updated_at=timezone.now() - timedelta(hours=3))
        self.assertEqual(self.client.get('/api/research-analyzer/report/', {'session_id': session_id}).status_code, 404)
        from django.core.management import call_command
        call_command('cleanup_analyzer_sessions', stdout=io.StringIO())
        self.assertFalse(AnalyzerSession.objects.filter(pk=session_id).exists())
        self.assertFalse((session_store._root() / session.storage_path).exists())

    def test_tampered_dataset_file_is_never_loaded(self):
        session_id = self._upload()
        session = AnalyzerSession.objects.get(pk=session_id)
        (session_store._root() / session.storage_path).write_bytes(b'not the pickle we wrote')
        self.assertIsNone(session_store.load_dataframe(session))
        self.assertEqual(self.client.get('/api/research-analyzer/report/', {'session_id': session_id}).status_code, 404)

    def test_invalid_session_id_is_404_not_500(self):
        response = self.client.get('/api/research-analyzer/report/', {'session_id': '../../etc/passwd'})
        self.assertEqual(response.status_code, 404)

    def test_wide_xlsx_is_rejected_before_full_parse(self):
        from openpyxl import Workbook
        from research_analyzer.services.data_service import MAX_COLS
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([f'c{index}' for index in range(MAX_COLS + 5)])
        sheet.append(list(range(MAX_COLS + 5)))
        buffer = io.BytesIO()
        workbook.save(buffer)
        with patch('research_analyzer.services.data_service.pd.read_excel') as read_excel:
            with self.assertRaisesRegex(ValueError, 'column limit'):
                parse_uploaded_file(io.BytesIO(buffer.getvalue()), 'wide.xlsx')
        read_excel.assert_not_called()

    def test_xlsx_zip_bomb_is_rejected(self):
        import zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('xl/worksheets/sheet1.xml', b'0' * (151 * 1024 * 1024))
        with self.assertRaisesRegex(ValueError, 'too large once uncompressed'):
            parse_uploaded_file(io.BytesIO(buffer.getvalue()), 'bomb.xlsx')
