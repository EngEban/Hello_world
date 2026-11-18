"""Research Analyzer engine: extra analyses, the method registry and automatic test selection.

``services.stats_service`` keeps the original, validated basic tests. This package builds on it:

* ``methods``   – additional and extended analyses (2×2 risk measures, factorial / repeated-measures
                  ANOVA, ANCOVA, partial correlation, multinomial / ordinal / count regression,
                  reliability and agreement, diagnostic accuracy, Table 1 by group).
* ``registry``  – every method with its family, level (basic / advanced) and inputs, for the UI.
* ``selection`` – the rule table that turns a research question into a recommended test and reasons.
"""
