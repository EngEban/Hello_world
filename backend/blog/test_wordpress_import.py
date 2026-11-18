"""WordPress migration: parsers, safe/idempotent merge, media copy, users, redirects."""
import json
import shutil
import struct
import tempfile
import zlib
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from blog.models import Author, Category, MediaAsset, Post, Tag
from blog.wordpress import phpserial
from blog.wordpress.hashers import phpass_crypt, verify_wordpress_hash
from blog.wordpress.importer import resolve_seo
from blog.wordpress.sources import read_sql_dump, read_wxr
from blog.wordpress.sqldump import read_tables
from redirects.models import Redirect, WordPressImportRecord

WP_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'blog.wordpress.hashers.WordPressPasswordHasher',
]


def tiny_png(color=(255, 0, 0)):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b'\x00' + bytes(color)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def wxr(title='Understanding Cohort Studies', content='<p>Original body</p>', extra_items=''):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/" xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:wp="http://wordpress.org/export/1.2/">
<channel>
  <title>ResRef</title><link>https://resref.com</link>
  <wp:base_site_url>https://resref.com</wp:base_site_url><wp:base_blog_url>https://resref.com</wp:base_blog_url>
  <wp:author><wp:author_id>7</wp:author_id><wp:author_login><![CDATA[dr-sara]]></wp:author_login>
    <wp:author_email><![CDATA[sara@example.com]]></wp:author_email><wp:author_display_name><![CDATA[Dr Sara Ali]]></wp:author_display_name></wp:author>
  <wp:category><wp:term_id>3</wp:term_id><wp:category_nicename><![CDATA[methods]]></wp:category_nicename>
    <wp:category_parent><![CDATA[]]></wp:category_parent><wp:cat_name><![CDATA[Methods]]></wp:cat_name></wp:category>
  <wp:category><wp:term_id>4</wp:term_id><wp:category_nicename><![CDATA[cohort]]></wp:category_nicename>
    <wp:category_parent><![CDATA[methods]]></wp:category_parent><wp:cat_name><![CDATA[Cohort Designs]]></wp:cat_name></wp:category>
  <wp:tag><wp:term_id>9</wp:term_id><wp:tag_slug><![CDATA[epidemiology]]></wp:tag_slug><wp:tag_name><![CDATA[Epidemiology]]></wp:tag_name></wp:tag>
  <item>
    <title>Cohort figure</title><wp:post_id>50</wp:post_id><wp:post_type>attachment</wp:post_type><wp:status>inherit</wp:status>
    <wp:attachment_url>https://resref.com/wp-content/uploads/2024/05/cohort.png</wp:attachment_url>
    <excerpt:encoded><![CDATA[Figure 1]]></excerpt:encoded><content:encoded><![CDATA[]]></content:encoded>
    <wp:postmeta><wp:meta_key>_wp_attached_file</wp:meta_key><wp:meta_value><![CDATA[2024/05/cohort.png]]></wp:meta_value></wp:postmeta>
    <wp:postmeta><wp:meta_key>_wp_attachment_image_alt</wp:meta_key><wp:meta_value><![CDATA[Cohort diagram]]></wp:meta_value></wp:postmeta>
  </item>
  <item>
    <title>{title}</title><link>https://resref.com/2024/05/understanding-cohort-studies/</link>
    <dc:creator><![CDATA[dr-sara]]></dc:creator>
    <content:encoded><![CDATA[{content}]]></content:encoded><excerpt:encoded><![CDATA[Short summary]]></excerpt:encoded>
    <wp:post_id>101</wp:post_id><wp:post_date>2024-05-02 10:00:00</wp:post_date><wp:post_date_gmt>2024-05-02 08:00:00</wp:post_date_gmt>
    <wp:post_name>understanding-cohort-studies</wp:post_name><wp:status>publish</wp:status><wp:post_type>post</wp:post_type>
    <category domain="category" nicename="cohort"><![CDATA[Cohort Designs]]></category>
    <category domain="post_tag" nicename="epidemiology"><![CDATA[Epidemiology]]></category>
    <wp:postmeta><wp:meta_key>_thumbnail_id</wp:meta_key><wp:meta_value>50</wp:meta_value></wp:postmeta>
    <wp:postmeta><wp:meta_key>_yoast_wpseo_title</wp:meta_key><wp:meta_value><![CDATA[Cohort studies explained %%sep%% %%sitename%%]]></wp:meta_value></wp:postmeta>
    <wp:postmeta><wp:meta_key>rank_math_description</wp:meta_key><wp:meta_value><![CDATA[A practical guide.]]></wp:meta_value></wp:postmeta>
    <wp:postmeta><wp:meta_key>acf_reading_level</wp:meta_key><wp:meta_value><![CDATA[advanced]]></wp:meta_value></wp:postmeta>
  </item>
  <item>
    <title>About ResRef</title><link>https://resref.com/about-resref/</link><dc:creator><![CDATA[dr-sara]]></dc:creator>
    <content:encoded><![CDATA[<p>About</p>]]></content:encoded><excerpt:encoded><![CDATA[]]></excerpt:encoded>
    <wp:post_id>102</wp:post_id><wp:post_date_gmt>2024-01-01 00:00:00</wp:post_date_gmt>
    <wp:post_name>about-resref</wp:post_name><wp:status>publish</wp:status><wp:post_type>page</wp:post_type>
  </item>
  <item>
    <title>Auto draft</title><wp:post_id>103</wp:post_id><wp:post_name></wp:post_name><wp:status>auto-draft</wp:status><wp:post_type>post</wp:post_type>
  </item>
  {extra_items}
</channel></rss>'''


SQL_DUMP = r"""-- MySQL dump 10.13
/*!40101 SET NAMES utf8mb4 */;
DROP TABLE IF EXISTS `wp_options`;
CREATE TABLE `wp_options` (
  `option_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `option_name` varchar(191) NOT NULL DEFAULT '',
  `option_value` longtext NOT NULL,
  `autoload` varchar(20) NOT NULL DEFAULT 'yes',
  PRIMARY KEY (`option_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_options` VALUES (1,'home','https://resref.com','yes'),(2,'permalink_structure','/%year%/%monthnum%/%postname%/','yes');
CREATE TABLE `wp_users` (
  `ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_login` varchar(60) NOT NULL DEFAULT '',
  `user_pass` varchar(255) NOT NULL DEFAULT '',
  `user_nicename` varchar(50) NOT NULL DEFAULT '',
  `user_email` varchar(100) NOT NULL DEFAULT '',
  `user_url` varchar(100) NOT NULL DEFAULT '',
  `user_registered` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `display_name` varchar(250) NOT NULL DEFAULT '',
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_users` VALUES (7,'dr-sara','$P$9IQRaTwmfeRo7ud9Fh4E2PdI0S3r.L0','dr-sara','Sara@Example.com','https://sara.example.com','2023-02-01 09:00:00','Dr Sara Ali'),(8,'member1','$P$9IQRaTwmfeRo7ud9Fh4E2PdI0S3r.L0','member1','member1@example.com','','2023-03-01 09:00:00','Member One');
CREATE TABLE `wp_usermeta` (
  `umeta_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL DEFAULT '0',
  `meta_key` varchar(255) DEFAULT NULL,
  `meta_value` longtext,
  PRIMARY KEY (`umeta_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_usermeta` VALUES (1,7,'description','Epidemiologist.\nWrites about cohorts.'),(2,7,'wp_capabilities','a:1:{s:13:\"administrator\";b:1;}'),(3,7,'first_name','Sara'),(4,8,'wp_capabilities','a:1:{s:10:\"subscriber\";b:1;}');
CREATE TABLE `wp_posts` (
  `ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `post_author` bigint(20) unsigned NOT NULL DEFAULT '0',
  `post_date` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `post_date_gmt` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `post_content` longtext NOT NULL,
  `post_title` text NOT NULL,
  `post_excerpt` text NOT NULL,
  `post_status` varchar(20) NOT NULL DEFAULT 'publish',
  `post_name` varchar(200) NOT NULL DEFAULT '',
  `post_modified_gmt` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `post_parent` bigint(20) unsigned NOT NULL DEFAULT '0',
  `guid` varchar(255) NOT NULL DEFAULT '',
  `post_type` varchar(20) NOT NULL DEFAULT 'post',
  PRIMARY KEY (`ID`),
  KEY `post_name` (`post_name`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_posts` VALUES (101,7,'2024-05-02 10:00:00','2024-05-02 08:00:00','<p>It\'s a \"cohort\" guide; see (1),(2).</p>\r\n<p>Line two</p>','Understanding Cohort Studies','Short summary','publish','understanding-cohort-studies','2024-05-03 08:00:00',0,'https://resref.com/?p=101','post'),(50,7,'2024-05-01 10:00:00','2024-05-01 08:00:00','','Cohort figure','Figure 1','inherit','cohort-figure','2024-05-01 08:00:00',101,'https://resref.com/wp-content/uploads/2024/05/cohort.png','attachment'),(104,7,'2024-05-02 10:00:00','2024-05-02 08:00:00','x','Revision','','inherit','101-revision-v1','2024-05-02 08:00:00',101,'','revision'),(105,7,'2024-06-02 10:00:00','2024-06-02 08:00:00','Body','Team page','','publish','team','2024-06-02 08:00:00',106,'','page'),(106,7,'2024-06-01 10:00:00','2024-06-01 08:00:00','Body','About','','publish','about-us','2024-06-01 08:00:00',0,'','page');
CREATE TABLE `wp_postmeta` (
  `meta_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `post_id` bigint(20) unsigned NOT NULL DEFAULT '0',
  `meta_key` varchar(255) DEFAULT NULL,
  `meta_value` longtext,
  PRIMARY KEY (`meta_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_postmeta` VALUES (1,101,'_thumbnail_id','50'),(2,50,'_wp_attached_file','2024/05/cohort.png'),(3,50,'_wp_attachment_image_alt','Cohort diagram'),(4,101,'rank_math_title','%title% %sep% %sitename%'),(5,101,'_elementor_data',NULL);
CREATE TABLE `wp_terms` (
  `term_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL DEFAULT '',
  `slug` varchar(200) NOT NULL DEFAULT '',
  `term_group` bigint(10) NOT NULL DEFAULT '0',
  PRIMARY KEY (`term_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_terms` VALUES (3,'Methods','methods',0),(4,'Cohort Designs','cohort',0),(9,'Epidemiology','epidemiology',0);
CREATE TABLE `wp_term_taxonomy` (
  `term_taxonomy_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `term_id` bigint(20) unsigned NOT NULL DEFAULT '0',
  `taxonomy` varchar(32) NOT NULL DEFAULT '',
  `description` longtext NOT NULL,
  `parent` bigint(20) unsigned NOT NULL DEFAULT '0',
  `count` bigint(20) NOT NULL DEFAULT '0',
  PRIMARY KEY (`term_taxonomy_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_term_taxonomy` VALUES (13,3,'category','Research methods',0,0),(14,4,'category','',3,1),(19,9,'post_tag','',0,1);
CREATE TABLE `wp_term_relationships` (
  `object_id` bigint(20) unsigned NOT NULL DEFAULT '0',
  `term_taxonomy_id` bigint(20) unsigned NOT NULL DEFAULT '0',
  `term_order` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`object_id`,`term_taxonomy_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_term_relationships` VALUES (101,14,0),(101,19,0);
CREATE TABLE `wp_redirection_items` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `url` mediumtext NOT NULL,
  `regex` int(11) unsigned NOT NULL DEFAULT '0',
  `status` enum('enabled','disabled') NOT NULL DEFAULT 'enabled',
  `action_type` varchar(20) NOT NULL,
  `action_code` int(11) unsigned NOT NULL,
  `action_data` mediumtext,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `wp_redirection_items` (`id`, `url`, `regex`, `status`, `action_type`, `action_code`, `action_data`) VALUES
(1, '/old-cohort-guide/', 0, 'enabled', 'url', 301, 'https://resref.com/2024/05/understanding-cohort-studies/'),
(2, '/legacy/(.*)', 1, 'enabled', 'url', 301, '/$1'),
(3, '/gone/', 0, 'disabled', 'url', 301, '/');
"""


class Workspace(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.media_root = self.tmp / 'media'
        self.uploads = self.tmp / 'uploads'
        (self.uploads / '2024' / '05').mkdir(parents=True)
        (self.uploads / '2024' / '05' / 'cohort.png').write_bytes(tiny_png())
        (self.uploads / '2024' / '05' / 'cohort-300x200.png').write_bytes(tiny_png((0, 255, 0)))
        (self.uploads / '2024' / '05' / 'shell.php').write_text('<?php echo 1;')
        self.settings_override = override_settings(MEDIA_ROOT=str(self.media_root), STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding='utf-8')
        return str(path)

    def run_import(self, source, *args):
        out = StringIO()
        call_command('import_wordpress', source, '--no-input', *args, stdout=out)
        return out.getvalue()


class ParserTests(TestCase):
    def test_phpass_reference_vector_and_formats(self):
        self.assertTrue(verify_wordpress_hash('test12345', '$P$9IQRaTwmfeRo7ud9Fh4E2PdI0S3r.L0'))
        self.assertFalse(verify_wordpress_hash('wrong', '$P$9IQRaTwmfeRo7ud9Fh4E2PdI0S3r.L0'))
        self.assertTrue(verify_wordpress_hash('secret', '5ebe2294ecd0e0f08eab7690d2a6ee69'))  # legacy md5
        self.assertFalse(verify_wordpress_hash('secret', 'not-a-hash'))
        self.assertIsNone(phpass_crypt('x', '$X$9IQRaTwm'))

    def test_php_unserialize_is_safe(self):
        self.assertEqual(phpserial.loads('a:2:{s:13:"administrator";b:1;s:3:"key";i:5;}'), {'administrator': True, 'key': 5})
        self.assertIsNone(phpserial.loads('O:8:"stdClass":0:{}'))
        self.assertIsNone(phpserial.loads('garbage'))

    def test_seo_templates(self):
        self.assertEqual(resolve_seo('Cohort studies explained %%sep%% %%sitename%%', 'T'), 'Cohort studies explained')
        self.assertEqual(resolve_seo('%title% %sep% %sitename%', 'Title'), '')
        self.assertEqual(resolve_seo('Plain description', 'Title'), 'Plain description')

    def test_sql_dump_values_and_escapes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dump.sql'
            path.write_text(SQL_DUMP, encoding='utf-8')
            rows, columns = read_tables(path, ['wp_posts', 'wp_redirection_items'])
            post = next(row for row in rows['wp_posts'] if row['ID'] == '101')
            self.assertEqual(post['post_content'], '<p>It\'s a "cohort" guide; see (1),(2).</p>\r\n<p>Line two</p>')
            self.assertEqual(len(rows['wp_redirection_items']), 3)
            data = read_sql_dump(path)
        self.assertEqual(data.site_url, 'https://resref.com')
        self.assertEqual([item['wordpress_id'] for item in data.items], [101, 105, 106])  # revision ignored
        cohort = data.items[0]
        self.assertEqual(cohort['link'], 'https://resref.com/2024/05/understanding-cohort-studies/')
        self.assertEqual(cohort['categories'], ['cohort'])
        self.assertEqual(data.items[1]['link'], 'https://resref.com/about-us/team/')  # hierarchical page
        self.assertEqual(data.users[0]['roles'], ['administrator'])
        self.assertEqual(data.users[0]['bio'], 'Epidemiologist.\nWrites about cohorts.')
        self.assertEqual(data.categories[1]['parent_slug'], 'methods')
        self.assertEqual(data.attachments[0]['url'], 'https://resref.com/wp-content/uploads/2024/05/cohort.png')
        self.assertEqual(len(data.redirects), 2)  # disabled rule ignored

    def test_wxr_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'export.xml'
            path.write_text(wxr(), encoding='utf-8')
            data = read_wxr(path)
        self.assertEqual(len(data.items), 3)
        self.assertEqual(data.items[0]['meta']['_thumbnail_id'], '50')
        self.assertEqual(data.authors[0]['login'], 'dr-sara')


class ImportTests(Workspace):
    def test_dry_run_changes_nothing(self):
        source = self.write('export.xml', wxr())
        before = (Post.objects.count(), Author.objects.count(), Category.objects.count(), WordPressImportRecord.objects.count())
        output = self.run_import(source, '--dry-run', '--uploads-dir', str(self.uploads))
        self.assertIn('DRY RUN', output)
        self.assertEqual(before, (Post.objects.count(), Author.objects.count(), Category.objects.count(), WordPressImportRecord.objects.count()))
        self.assertFalse((self.media_root / 'wp-content').exists())
        self.assertRegex(output, r'posts\s+2\s')  # 2 would be created (auto-draft skipped)

    def test_import_is_complete_and_idempotent(self):
        source = self.write('export.xml', wxr())
        self.run_import(source, '--uploads-dir', str(self.uploads))
        post = Post.objects.get(wordpress_id=101)
        self.assertEqual(post.author.login, 'dr-sara')
        self.assertEqual(post.seo_title, 'Cohort studies explained')
        self.assertEqual(post.seo_description, 'A practical guide.')
        self.assertEqual(list(post.categories.values_list('slug', flat=True)), ['cohort'])
        self.assertEqual(Category.objects.get(slug='cohort').parent.slug, 'methods')
        self.assertTrue(post.tags.filter(slug='epidemiology').exists())
        asset = MediaAsset.objects.get(wordpress_id=50)
        self.assertEqual(asset.alt_text, 'Cohort diagram')
        self.assertEqual(asset.file.name, 'wp-content/uploads/2024/05/cohort.png')
        self.assertTrue((self.media_root / 'wp-content/uploads/2024/05/cohort-300x200.png').is_file())
        self.assertFalse((self.media_root / 'wp-content/uploads/2024/05/shell.php').exists())
        self.assertEqual(post.featured_image, asset.source_url())
        self.assertFalse(Post.objects.filter(title='Auto draft').exists())
        counts = (Post.objects.count(), Author.objects.count(), Category.objects.count(), Tag.objects.count(), MediaAsset.objects.count(), WordPressImportRecord.objects.count(), Redirect.objects.count())

        report_path = self.tmp / 'report.json'
        self.run_import(source, '--uploads-dir', str(self.uploads), '--report', str(report_path))
        self.assertEqual(counts, (Post.objects.count(), Author.objects.count(), Category.objects.count(), Tag.objects.count(), MediaAsset.objects.count(), WordPressImportRecord.objects.count(), Redirect.objects.count()))
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['counts']['posts'], {'unchanged': 2})
        self.assertNotIn('conflict', report['counts']['media'])
        self.assertEqual(report['extra']['upload files']['exists'], 2)
        self.assertEqual(report['extra']['posts: WordPress fields not imported'], {'acf_reading_level': 1})

    def test_new_site_edits_are_never_overwritten_without_flag(self):
        source = self.write('export.xml', wxr())
        self.run_import(source)
        post = Post.objects.get(wordpress_id=101)
        post.title = 'Edited in the dashboard'
        post.save()
        changed = self.write('export2.xml', wxr(title='Changed in WordPress', content='<p>New WordPress body</p>'))
        output = self.run_import(changed)
        post.refresh_from_db()
        self.assertEqual(post.title, 'Edited in the dashboard')
        self.assertEqual(post.content, '<p>New WordPress body</p>')  # untouched locally -> WordPress wins
        self.assertIn('CONFLICT', output)
        self.assertIn('title', output)
        # Same export again: the conflict was already reported, the local edit stays quietly.
        self.run_import(changed)
        post.refresh_from_db()
        self.assertEqual(post.title, 'Edited in the dashboard')
        self.run_import(changed, '--overwrite')
        post.refresh_from_db()
        self.assertEqual(post.title, 'Changed in WordPress')

    def test_existing_new_site_post_with_same_slug_is_linked_not_duplicated(self):
        existing = Post.objects.create(title='Written in the new app', slug='understanding-cohort-studies', content='<p>New app body</p>', status='publish')
        output = self.run_import(self.write('export.xml', wxr()))
        existing.refresh_from_db()
        self.assertEqual(existing.wordpress_id, 101)
        self.assertEqual(existing.title, 'Written in the new app')
        self.assertEqual(existing.content, '<p>New app body</p>')
        self.assertEqual(Post.objects.filter(slug__startswith='understanding-cohort-studies').count(), 1)
        self.assertIn('CONFLICT', output)

    def test_rows_from_the_earlier_importer_update_only_when_unedited(self):
        untouched = Post.objects.create(title='Old title', slug='understanding-cohort-studies', content='old', wordpress_id=101, status='publish')
        edited = Post.objects.create(title='Old page', slug='about-resref', content='old', wordpress_id=102, post_type='page', status='publish')
        Post.objects.filter(pk=edited.pk).update(updated_at=edited.created_at + timedelta(days=3))
        self.run_import(self.write('export.xml', wxr()))
        untouched.refresh_from_db()
        edited.refresh_from_db()
        self.assertEqual(untouched.title, 'Understanding Cohort Studies')
        self.assertEqual(edited.title, 'Old page')

    def test_redirects_never_hijack_live_addresses(self):
        Post.objects.create(title='Journal finder page', slug='journal-finder', content='x', wordpress_id=999, post_type='page', status='publish')
        duplicate = '''<item><title>Journal finder post</title><link>https://resref.com/journal-finder/</link>
          <content:encoded><![CDATA[x]]></content:encoded><wp:post_id>120</wp:post_id><wp:post_date_gmt>2024-01-01 00:00:00</wp:post_date_gmt>
          <wp:post_name>journal-finder</wp:post_name><wp:status>publish</wp:status><wp:post_type>post</wp:post_type></item>'''
        output = self.run_import(self.write('export.xml', wxr(extra_items=duplicate)))
        self.assertEqual(Post.objects.get(wordpress_id=120).slug, 'journal-finder-2')
        self.assertFalse(Redirect.objects.filter(old_path='/journal-finder').exists())
        self.assertIn('CONFLICT', output)
        # Re-running does not keep reporting the numbered slug as a conflict.
        self.assertNotIn('CONFLICT', self.run_import(self.write('export.xml', wxr(extra_items=duplicate))))

    def test_nothing_is_ever_deleted(self):
        keep = Post.objects.create(title='Only in the new site', slug='only-new', content='x')
        self.run_import(self.write('export.xml', wxr()))
        post = Post.objects.get(wordpress_id=101)
        local_category = Category.objects.create(name='Local', slug='local')
        post.categories.add(local_category)
        self.run_import(self.write('export.xml', wxr()))
        self.assertTrue(Post.objects.filter(pk=keep.pk).exists())
        self.assertTrue(post.categories.filter(slug='local').exists())

    def test_media_conflict_keeps_existing_file(self):
        target = self.media_root / 'wp-content/uploads/2024/05/cohort.png'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'different bytes')
        output = self.run_import(self.write('export.xml', wxr()), '--uploads-dir', str(self.uploads), '--only', 'media')
        self.assertEqual(target.read_bytes(), b'different bytes')
        self.assertIn('CONFLICT', output)

    def test_only_and_validation(self):
        source = self.write('export.xml', wxr())
        self.run_import(source, '--only', 'categories,tags')
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 2)
        with self.assertRaises(CommandError):
            self.run_import(source, '--only', 'comments')
        with self.assertRaises(CommandError):
            self.run_import(str(self.tmp / 'missing.xml'))

    def test_real_run_requires_confirmation_when_interactive(self):
        source = self.write('export.xml', wxr())
        from unittest import mock

        with mock.patch('builtins.input', return_value='no'):
            with self.assertRaises(CommandError):
                call_command('import_wordpress', source, stdout=StringIO())
        self.assertEqual(Post.objects.count(), 0)


class SqlImportTests(Workspace):
    def test_sql_dump_import_with_redirects(self):
        output = self.run_import(self.write('dump.sql', SQL_DUMP))
        post = Post.objects.get(wordpress_id=101)
        self.assertEqual(post.author.bio, 'Epidemiologist.\nWrites about cohorts.')
        self.assertEqual(post.seo_title, '')
        self.assertEqual(Category.objects.get(slug='cohort').parent.slug, 'methods')
        dated = Redirect.objects.get(old_path='/2024/05/understanding-cohort-studies')
        self.assertEqual(dated.new_url, '/database/cohort/understanding-cohort-studies')
        plugin = Redirect.objects.get(old_path='/old-cohort-guide')
        self.assertEqual(plugin.new_url, '/database/cohort/understanding-cohort-studies')
        self.assertEqual(plugin.source, 'wp_redirection')
        self.assertTrue(Redirect.objects.filter(old_path='/about-us/team', new_url='/team').exists())
        self.assertIn('regular-expression', self.run_import(self.write('dump.sql', SQL_DUMP), '-v', '2'))
        self.assertNotIn('Error', output)

    def test_staff_redirects_are_kept(self):
        Redirect.objects.create(old_path='/old-cohort-guide/', new_url='/somewhere-else')
        self.run_import(self.write('dump.sql', SQL_DUMP))
        self.assertEqual(Redirect.objects.get(old_path='/old-cohort-guide').new_url, '/somewhere-else')

    def test_users_need_explicit_opt_in(self):
        self.run_import(self.write('dump.sql', SQL_DUMP))
        self.assertFalse(User.objects.filter(email='member1@example.com').exists())

    @override_settings(PASSWORD_HASHERS=WP_HASHERS)
    def test_users_keep_wordpress_password_and_existing_accounts_are_untouched(self):
        existing = User.objects.create_user('sara@example.com', 'sara@example.com', 'local-password-123')
        output = self.run_import(self.write('dump.sql', SQL_DUMP), '--only', 'users', '--import-password-hashes')
        existing.refresh_from_db()
        self.assertTrue(existing.check_password('local-password-123'))
        self.assertFalse(existing.is_staff)
        member = User.objects.get(email='member1@example.com')
        self.assertFalse(member.is_staff or member.is_superuser)
        self.assertTrue(member.password.startswith('wordpress$'))
        self.assertTrue(member.check_password('test12345'))
        member.refresh_from_db()
        self.assertTrue(member.password.startswith('pbkdf2_sha256$'))  # upgraded on first sign-in
        self.assertTrue(check_password('test12345', member.password))
        self.assertEqual(member.membership_profile.display_name, 'Member One')
        self.assertIn('administrator', output)  # WordPress admin role reported, never granted

    # Explicit: the site settings now include the WordPress hasher, so this case must turn it off.
    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher'])
    def test_users_without_hasher_get_no_password(self):
        self.run_import(self.write('dump.sql', SQL_DUMP), '--only', 'users', '--import-password-hashes')
        member = User.objects.get(email='member1@example.com')
        self.assertFalse(member.has_usable_password())
