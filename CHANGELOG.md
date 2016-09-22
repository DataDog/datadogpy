CHANGELOG
=========

# 0.14.0 / 2016-09-22

**Logging**

`dd.datadogpy` logger name is no longer. `datadog` now uses logger names matching the project hierarchy, i.e.
* `datadog.api`
* `datadog.statsd`
* `datadog.threadstats`

By default, `datadog` loggers are set with a do-nothing handler ([`NullHandler`](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library)).

To setup a different handler, one can add a handler
```python
import logging

logging.getLogger("datadog").addHandler(...)
```

### Changes
* [FEATURE] DogStatsD: Provide elapsed time from the `timed` decorator, [#154][] (thanks [@tuukkamustonen][])
* [FEATURE] DogStatsD: Allow starting and stopping `timed` manually, [#155][] (thanks [@tuukkamustonen][])
* [IMPROVEMENT] DogStatsD: Support timing for coroutine functions on Python 3.5 or higher, [#146][] (thanks [@thehesiod][])
* [OTHER] Rename loggers and set null handlers, [#161][]

# 0.13.0 / 2016-08-24
* [BUGFIX] Dogshell: Fix `UnicodeError` exceptions when a timeboard name contains non ascii characters, [#140][]
* [BUGFIX] DogStatsD: Support unicode characters in tags, [#132][], [#152][]
* [BUGFIX] ThreadStats: Fix `RuntimeError` exceptions on flush caused by an unsafe thread operation, [#143][], [#151][] (thanks [@leozc][])
* [FEATURE] API: Add `delete` method for `Event` resource, [#145][]
* [IMPROVEMENT] DogStatsD: Have `timed` context manager to return itself, [#147][] (thanks [@ross][])

# 0.12.0 / 2016-05-27
* [BUGFIX] API: Do not raise on hostname resolution failures, [#106][]
* [FEATURE] DogStatsD: Allow to dynamically use default route as a StatsD host, [#134][]
* [IMPROVEMENT] API: Enhance compatibility with Google App Engine, support `urlfetch` as a HTTP library [#106][]

# 0.11.0 / 2016-03-14

* [BUGFIX] Dogshell: Print usage when no argument is given on Python 3, [#123][]
* [BUGFIX] DogStatsD: Do not modify metric-level `tags` parameters when `constant_tags` is set, [#94][] (thanks [@steven-liu][])
* [BUGFIX] DogStatsD: Fix thread-safety of the `[@timed][]` decorator, [#126][] (thanks [@mgood][])
* [BUGFIX] ThreadStats: Do not modify metric-level `tags` parameters when `constant_tags` is set, [#94][], [#117][] (thanks [@steven-liu][])
* [FEATURE] Dogshell: Add an `alert_type` option for `event post`, [#120][] (thanks [@drstevens][])
* [FEATURE] DogStatD: Set constant tags from `DATADOG_TAGS` environment variable, [#114][] (thanks [@ewdurbin][] )
* [FEATURE] DogStatsD: Support namespace, [#118][]
* [FEATURE] ThreadStats: Set constant tags from `DATADOG_TAGS` environment variable, [#114][] (thanks [@ewdurbin][] )
* [FEATURE] ThreadStats: Support namespace, [#118][]
* [IMPROVEMENT] API: Support real numerical data types in `Metrics`, [#103][]
* [IMPROVEMENT] Dogshell: Attach hostname by default to event and metric posts, [#122][]
* [IMPROVEMENT] DogStatsD: Discard `None` values, [#119][] (thanks [@dcrosta][])
* [IMPROVEMENT] DogStatsD: Import from top level, [#105][]
* [IMPROVEMENT] Dogwrap: Trim output and update event format, [#104][] (thanks [@gnarf][])
* [OTHER] API: Adjust the documentation, [#96][], [#101][], [#110][], [#111][] (thanks [@aristiden7o][], [@emad][], [@aknuds1][], [@meawoppl][])
* [OTHER] Dogshell: Update misleading help message for `event stream`, [#124][]

# 0.10.0 / 2015-10-19
* [BUGFIX] Fix typo in Dogshell breaking the Timeboard `pull_all` method, [#92][]
* [FEATURE] Enhance `constant_tags` support to ThreadStats and Statsd events, [#90][] (thanks [@jofusa][])
* [FEATURE] New CRUD User API, [#89][]
* [OTHER] Fix Dogwrap documentation output typo, [#87][] (thanks [@gnarf][])

# 0.9.0 / 2015-08-31
* [FEATURE] Option to time in ms with `statsd`, [#78][] (thanks [@g--][])
* [FEATURE] Option to unmute `api` ApiError exceptions, [#76][]
* [OTHER] Use `simplejson` with Python 3.x, [#83][]

# 0.8.0 / 2015-07-30
* [FEATURE] Constant tags client option to append tags to every submitted metrics, [#68][] (thanks [@jofusa][])
* [FEATURE] Embeddable graphs API, [#62][]
* [FEATURE] Optional metric name for the timed decorator, [#71][] (thanks [@clokep][])
* [IMPROVEMENT] Option to use the verify parameter in requests to configure a ca certificates file or to disable verification, [#70][] (thanks [@ogst][])

# 0.7.0 / 2015-07-01
* [BUGFIX] Fix `Metric.send` method to play nice with multiple metrics, [#59][] (thanks [@kuzmich][])
* [BUGFIX] Fix socket creation thread-unsafe code, [#57][] [#60][] (thanks [@GrahamDumpleton][])
* [BUGFIX] Rename `metric_type` parameter to `type` in `Metric.send` method, [#64][]
* [FEATURE] Add new monitor `unmute` arg (`all_scopes`) to allow clearing all mute settings for a given monitor, [#58][]
* [FEATURE] Revoke a shared screenboard, [#46][]
* [IMPROVEMENT] Add a timed context manager to `statsd`, [#65][] (thanks [@clokep][])
* [IMPROVEMENT] Adjust Dogshell descriptions to distinguish between `mute_all`/`unmute_all` and `mute`/`unmute` methods, [#58][]
* [IMPROVEMENT] Include additional information in 403 response exceptions, [#58][]
* [OTHER] Update `requests` library, per CVE-2015-2296, [#63][]

# 0.6.1 // 2016.09.09
* [BUGFIX] Fix socket creation thread-unsafe code, [#57][] [#60][] (thanks [@GrahamDumpleton][])

# 0.6.0 / 2015-06-01
* [BUGFIX] Always fall back when unable to determine hostname from `datadog.conf`, [#53][]
* [FEATURE] Add `message` parameter support to host muting commands, [#51][]

# 0.5.0 / 2015-05-19
* [BUGFIX] Fix an unexpected exception raised in `initialize` method on Windows with Python3.4, [#47][]
* [FEATURE] Add support for metric query API, [#45][]

# 0.4.0 / 2015-04-24
* [BUGFIX] Fix a wrong event post parameter in Dogshell/Dogwrap, [#36][]
* [BUGFIX] Fix wrong keys in auto-generated .dogrc, [#34][]
* [FEATURE] Add a priority option to Dogwrap, or auto-detect it based on output, [#42][]
* [FEATURE] Initialize API parameters from environment variables, [#43][]
* [FEATURE] Stream Dogwrap command output during its execution or buffer it, [#39][]
* [OTHER] Add PyPI classifiers, [#41][]

# 0.3.0 / 2015-04-08
* [FEATURE] `DATADOG_HOST` environment variable to determine which API host to use, [#30][]

# 0.2.2 / 2015-04-06
* [BUGFIX] Fix a leftover debug statement

# 0.2.1 / REMOVED
* [BUGFIX] Fix test requirements
* [BUGFIX] Import json module from `datadog.compat`
* [OTHER] Contributing update

See [#8][], thanks [@benweatherman][]

# 0.2.0 / 2015-03-31
* [BUGFIX] Fixes `threadstats` unsafe thread operations, [#6][]
* [FEATURE] Add tests to check `statsd` and `threadstats` thread safety, [#6][]
* [OTHER] Changelog update, [#9][] [@miketheman][]

# 0.1.2 / 2015-03-23

* [BUGFIX] Fix a typo that was causing an initialization issue with `datadog.dogshell`, [#7][]

# 0.1 / 2015-03-10
* First release

<!--- The following link definition list is generated by PimpMyChangelog --->
[#6]: https://github.com/DataDog/datadogpy/issues/6
[#7]: https://github.com/DataDog/datadogpy/issues/7
[#8]: https://github.com/DataDog/datadogpy/issues/8
[#9]: https://github.com/DataDog/datadogpy/issues/9
[#30]: https://github.com/DataDog/datadogpy/issues/30
[#34]: https://github.com/DataDog/datadogpy/issues/34
[#36]: https://github.com/DataDog/datadogpy/issues/36
[#39]: https://github.com/DataDog/datadogpy/issues/39
[#41]: https://github.com/DataDog/datadogpy/issues/41
[#42]: https://github.com/DataDog/datadogpy/issues/42
[#43]: https://github.com/DataDog/datadogpy/issues/43
[#45]: https://github.com/DataDog/datadogpy/issues/45
[#46]: https://github.com/DataDog/datadogpy/issues/46
[#47]: https://github.com/DataDog/datadogpy/issues/47
[#51]: https://github.com/DataDog/datadogpy/issues/51
[#53]: https://github.com/DataDog/datadogpy/issues/53
[#57]: https://github.com/DataDog/datadogpy/issues/57
[#58]: https://github.com/DataDog/datadogpy/issues/58
[#59]: https://github.com/DataDog/datadogpy/issues/59
[#60]: https://github.com/DataDog/datadogpy/issues/60
[#62]: https://github.com/DataDog/datadogpy/issues/62
[#63]: https://github.com/DataDog/datadogpy/issues/63
[#64]: https://github.com/DataDog/datadogpy/issues/64
[#65]: https://github.com/DataDog/datadogpy/issues/65
[#67]: https://github.com/DataDog/datadogpy/issues/67
[#68]: https://github.com/DataDog/datadogpy/issues/68
[#70]: https://github.com/DataDog/datadogpy/issues/70
[#71]: https://github.com/DataDog/datadogpy/issues/71
[#76]: https://github.com/DataDog/datadogpy/issues/76
[#77]: https://github.com/DataDog/datadogpy/issues/77
[#78]: https://github.com/DataDog/datadogpy/issues/78
[#83]: https://github.com/DataDog/datadogpy/issues/83
[#87]: https://github.com/DataDog/datadogpy/issues/87
[#89]: https://github.com/DataDog/datadogpy/issues/89
[#90]: https://github.com/DataDog/datadogpy/issues/90
[#92]: https://github.com/DataDog/datadogpy/issues/92
[#94]: https://github.com/DataDog/datadogpy/issues/94
[#96]: https://github.com/DataDog/datadogpy/issues/96
[#101]: https://github.com/DataDog/datadogpy/issues/101
[#103]: https://github.com/DataDog/datadogpy/issues/103
[#104]: https://github.com/DataDog/datadogpy/issues/104
[#105]: https://github.com/DataDog/datadogpy/issues/105
[#106]: https://github.com/DataDog/datadogpy/issues/106
[#110]: https://github.com/DataDog/datadogpy/issues/110
[#111]: https://github.com/DataDog/datadogpy/issues/111
[#114]: https://github.com/DataDog/datadogpy/issues/114
[#117]: https://github.com/DataDog/datadogpy/issues/117
[#118]: https://github.com/DataDog/datadogpy/issues/118
[#119]: https://github.com/DataDog/datadogpy/issues/119
[#120]: https://github.com/DataDog/datadogpy/issues/120
[#122]: https://github.com/DataDog/datadogpy/issues/122
[#123]: https://github.com/DataDog/datadogpy/issues/123
[#124]: https://github.com/DataDog/datadogpy/issues/124
[#126]: https://github.com/DataDog/datadogpy/issues/126
[#132]: https://github.com/DataDog/datadogpy/issues/132
[#134]: https://github.com/DataDog/datadogpy/issues/134
[#140]: https://github.com/DataDog/datadogpy/issues/140
[#143]: https://github.com/DataDog/datadogpy/issues/143
[#145]: https://github.com/DataDog/datadogpy/issues/145
[#146]: https://github.com/DataDog/datadogpy/issues/146
[#147]: https://github.com/DataDog/datadogpy/issues/147
[#151]: https://github.com/DataDog/datadogpy/issues/151
[#152]: https://github.com/DataDog/datadogpy/issues/152
[#154]: https://github.com/DataDog/datadogpy/issues/154
[#155]: https://github.com/DataDog/datadogpy/issues/155
[#161]: https://github.com/DataDog/datadogpy/issues/161
[@GrahamDumpleton]: https://github.com/GrahamDumpleton
[@aknuds1]: https://github.com/aknuds1
[@aristiden7o]: https://github.com/aristiden7o
[@benweatherman]: https://github.com/benweatherman
[@clokep]: https://github.com/clokep
[@dcrosta]: https://github.com/dcrosta
[@drstevens]: https://github.com/drstevens
[@emad]: https://github.com/emad
[@ewdurbin]: https://github.com/ewdurbin
[@g--]: https://github.com/g--
[@gnarf]: https://github.com/gnarf
[@jofusa]: https://github.com/jofusa
[@kuzmich]: https://github.com/kuzmich
[@leozc]: https://github.com/leozc
[@meawoppl]: https://github.com/meawoppl
[@mgood]: https://github.com/mgood
[@miketheman]: https://github.com/miketheman
[@ogst]: https://github.com/ogst
[@ross]: https://github.com/ross
[@steven-liu]: https://github.com/steven-liu
[@thehesiod]: https://github.com/thehesiod
[@timed]: https://github.com/timed
[@tuukkamustonen]: https://github.com/tuukkamustonen
