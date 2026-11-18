"""Tidy the research-database topics.

* Merge Psychiatry into Psychology: every Psychiatry article moves to Psychology,
  Anxiety and Depression become Psychology subtopics, and Psychiatry is hidden.
* Fold duplicate topics into the main one: Gastroenterology and Hepatology into
  Gastroenterology and Hepatology, "Generic or Cross-Disciplinary M" into Generic.
* Move misfiled articles to the right topics (an article stays in every topic
  that genuinely fits it).
* Old topic addresses redirect permanently to the topic they were merged into.

Missing topics or articles are skipped, so the migration is safe on any copy of
the database. Nothing is deleted.
"""
from django.db import migrations

# (old topic slug, topic it is merged into)
TOPIC_MERGES = [
    ('psychiatry', 'psychology'),
    ('gastroenterology', 'gastroenterology-and-hepatology'),
    ('hepatology', 'gastroenterology-and-hepatology'),
    ('generic-or-cross-disciplinary-m', 'generic'),
]

# (article slug, topics to add, topics to remove) -- applied before the merges
ARTICLE_MOVES = [
    ('dry-eye-questionnaire-5-guide', ['ophthalmology'], ['psychiatry', 'psychology']),
    ('speed-questionnaire-standard-patient-evaluation-of-eye-dryness-guide', [], ['psychology', 'orthopedics-and-physical-medici']),
    ('mcgill-pain-questionnaire-guide', [], ['psychiatry']),
    ('pittsburgh-sleep-quality-index-psqi-a-full-guide-for-researchers-and-clinicians', ['neurology'], []),
    ('hooked-on-nicotine-checklist-honc-guide', ['public-health'], []),
    ('alcohol-dependence-scale-ads-a-full-guide-for-researchers-and-clinicians', ['public-health'], []),
    ('prhds-perception-risk-heart-disease-scale-guide', [], ['ophthalmology', 'rheumatology-and-immunology']),
    ('rose-angina-questionnaire-raq-a-full-guide-for-researchers-and-clinicians', [], ['ophthalmology', 'rheumatology-and-immunology']),
    ('pituitary-outcome-score-pos-guide', [], ['ophthalmology', 'rheumatology-and-immunology']),
    ('hemophilia-joint-health-score-guide', ['hematology'], ['ophthalmology', 'rheumatology-and-immunology']),
    ('ocular-surface-disease-index-osdi-guide', [], ['rheumatology-and-immunology']),
    ('career-orientations-inventory-coi-guide', [], ['orthopedics-and-physical-medici']),
    ('vancouver-obsessional-compulsive-inventory-guide', ['psychology'], ['nutrition']),
    ('facebook-intensity-scale-fbi-research-guide', [], ['neurology']),
    ('telehealth-usability-questionnaire-tuq-guide', [], ['uncategorized']),
    ('brief-abuse-screen-elderly-base-guide', ['public-health'], ['generic', 'psychiatry']),
    ('glasgow-dyspepsia-severity-score-gdss-a-full-guide-for-researchers-and-clinicians', ['gastroenterology-and-hepatology'], ['gastroenterology']),
    ('self-efficacy-for-managing-chronic-disease-6-item-scale-semcd-6s-a-full-guide-for-researchers-and-clinicians', ['generic'], ['generic-or-cross-disciplinary-m']),
    ('functional-assessment-of-cancer-therapy-hepatobiliary-fact-hep', ['oncology'], []),
    ('functional-assessment-of-cancer-therapy-prostate-questionnaire-fact-p-a-full-guide-for-researchers-and-clinicians', ['oncology'], []),
    ('expanded-prostate-cancer-index-composite-epic-guide', ['oncology'], []),
    ('qol-oc-ovarian-cancer-guide', ['oncology'], []),
    ('brief-fatigue-inventory-bfi-guide', ['oncology'], []),
    ('fertility-quality-of-life-questionnaire-fertiqol-a-full-guide-for-researchers-and-clinicians', ['obstetrics-and-gynecology'], ['public-health']),
    ('fertility-problem-inventory-guide', ['obstetrics-and-gynecology'], []),
    ('fear-of-birth-scale-fobs-guide', ['obstetrics-and-gynecology'], []),
    ('edinburgh-postnatal-depression-scale-epds-guide', ['obstetrics-and-gynecology'], []),
    ('hypoglycemia-fear-survey-ii-hfs-diabetes', ['diabetes'], []),
    ('addisons-disease-specific-quality-of-life-questionnaire-addiqol-30-a-guide-to-addiqol-30', ['addisons-disease'], []),
    ('coronary-revascularisation-outcome-questionnaire-guide', [], ['peripheral-arterial-disease']),
    ('vascular-quality-of-life-25-vascuqol-25-a-full-guide-for-researchers-and-clinicians', ['peripheral-arterial-disease'], []),
    ('kccq-heart-failure-assessment-guide', ['heart-failure'], []),
    ('minnesota-living-with-heart-failure-a-full-guide-for-researchers-and-clinicians', ['heart-failure'], []),
    ('asthma-quality-of-life-questionnaire-aqlq-a-comprehensive-guide-for-researchers-and-clinicians', ['asthma'], []),
    ('quality-of-recovery-15-qor-15-a-full-guide-for-researchers-and-clinicians', ['surgery'], []),
    ('qualeffo-31-osteoporosis-quality-of-life', ['rheumatology-and-immunology'], []),
    ('quality-of-life-questionnaire-of-the-european-foundation-for-osteoporosis-41-qualeffo-41-a-full-guide-for-researchers-and-clinicians', ['orthopedics-and-physical-medici'], []),
    ('assessment-of-quality-of-life-in-osteoporosis-16-ecos-16-a-full-guide-for-researchers-and-clinicians', ['orthopedics-and-physical-medici'], []),
    ('medication-adherence-report-scale-mars-a-full-guide-for-researchers-and-clinicians', ['public-health'], ['psychiatry']),
    ('daily-fatigue-impact-scale-guide', ['neurology'], ['psychiatry']),
    ('cardiac-anxiety-questionnaire-guide', ['cardiology'], []),
    ('strengths-and-difficulties-questionnaire-sdq', ['pediatrics'], []),
    ('the-screen-for-child-anxiety-related-disorders-scared-questionnaire-a-full-guide-for-researchers-and-clinicians', ['pediatrics'], []),
    ('mood-disorder-questionnaire-adolescents-mdq-a', ['pediatrics'], []),
    ('children-hope-scale-chs-a-full-guide-for-researchers-and-clinicians', ['pediatrics'], []),
    ('freiburg-questionnaire-competence-medicine-fkm-guide', [], ['psychology']),
    ('pain-catastrophizing-scale-overview', ['neurology'], []),
    ('pain-self-efficacy-questionnaire-guide', ['neurology'], []),
]


def apply(apps, schema_editor):
    Category = apps.get_model('blog', 'Category')
    Post = apps.get_model('blog', 'Post')
    Redirect = apps.get_model('resref_redirects', 'Redirect')
    categories = {category.slug: category for category in Category.objects.all()}

    for slug, add, remove in ARTICLE_MOVES:
        post = Post.objects.filter(slug=slug).first()
        if not post:
            continue
        post.categories.add(*[categories[s] for s in add if s in categories])
        post.categories.remove(*[categories[s] for s in remove if s in categories])

    for old_slug, new_slug in TOPIC_MERGES:
        old, new = categories.get(old_slug), categories.get(new_slug)
        if not old or not new:
            continue
        for post in Post.objects.filter(categories=old):
            post.categories.add(new)
            post.categories.remove(old)
        Category.objects.filter(parent=old).update(parent=new)
        old.show_in_database = False
        old.save(update_fields=['show_in_database'])
        Redirect.objects.update_or_create(
            old_path=f'/database/{old_slug}',
            defaults={
                'new_url': f'/database/{new_slug}', 'status_code': 301, 'is_prefix': True,
                'is_active': True, 'source': 'manual', 'note': f'Topic merged into {new.name}',
            },
        )

    # Signals do not fire for migration models, so refresh the redirect cache here.
    from redirects.cache import bump_version
    bump_version()


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0011_seed_category_order'),
        ('resref_redirects', '0001_initial'),
    ]
    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
