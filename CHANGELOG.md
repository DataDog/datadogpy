CHANGELOG
=========

# 0.29.1 / 2019-06-10

* [BUGFIX] Properly extend response headers to response object. [#397][]

# 0.29.0 / 2019-06-05

* [BUGFIX] Lambda wrapper: Always flush, even on exceptions, [#359][] (thanks [@jmehnle][])
* [BUGFIX] API: Do not send JSON body in GET requests, [#382][]
* [BUGFIX] API: Allow listing timeboards with empty descriptions, [#385][] (thanks [@Tenzer][])
* [BUGFIX] Dogwrap: Better string handling and python3 support, [#379][]
* [BUGFIX] Threadstats: ensure MetricsAggregator is threadsafe, [#370][] (thanks [@TheKevJames][])
* [BUGFIX] Dogshell: Fixes the `--tags` argument for service_checks, [#387][] (thanks [@gordlea][])
* [FEATURE] API: Add support for dashboard list API v2, [#374][]
* [IMPROVEMENT] API: Handle http code 429 rate limiting in external python library, [#376][]
* [IMPROVEMENT] API: Add ability to not attach_host_name to metrics, events and distributions, [#383][]
* [IMPROVEMENT] API: Return Rate Limit Headers, [#378][] (thanks [@fdhoff][])
* [IMPROVEMENT] API: Do not override API parameters with default when calling initialize if they are already set, [#386][]
* [IMPROVEMENT] Dogshell: Add `--tags` support to monitors, [#356][]
* [IMPROVEMENT] Dogshell: Add documentation for environment variables, [#388][] (thanks [@sc68cal][])
* [IMPROVEMENT] Dogstatsd: Added a new parameter `statsd_default_namespace` to the `initialize` method, [#353][] (thanks [@lceS2][])
* [IMPROVEMENT] Import Iterable from collections.abc on python3 to avoid deprecation warning, [#381][]
* [IMPROVEMENT] Do not capture `/bin/hostname` stderr, [#368][] (thanks [@brendanlong][])
* [IMPROVEMENT] Add support for environment variables `DD_API_KEY` and `DD_APP_KEY` for setting API and APP keys respectively, [#373][]

=========

# 0.28.0 / 2019-03-27

* [BUGFIX] Dogshell: Properly require `handle` as an argument to the `comment` subcommand, [#364][]
* [FEATURE] API: Add support for the `Dashboard.get_all` API, [#362][]
* [FEATURE] Dogshell: Add support for defining monitors as JSON files, [#322][] (thanks [@Hefeweizen][])
* [FEATURE] DogStatsD: Add support for the `DD_AGENT_HOST`, `DD_DOGSTATSD_PORT`, and `DD_ENTITY_ID` environment variables, [#363][]
* [IMPROVEMENT] API: Add support for the `free` layout_type in `Dashboard.create` and `Dashboard.update`, [#362][]

# 0.27.0 / 2019-03-06

**New Dashboards API: https://docs.datadoghq.com/api/?lang=python#dashboards**

The Timeboard and Screenboard API resources are deprecated in favor of the new Dashboard resource. See https://docs.datadoghq.com/api/?lang=python#dashboards for more details.

* [BUGFIX] API: Fix `UnicodeError` exceptions raised by the API client on errors that contain non ascii characters, [#223][], [#346][]
* [BUGFIX] DogStatsD: Fix unsafe socket creation on multithreaded applications and catch more exceptions, [#212][], [#349][]
* [FEATURE] API: Add support for the new Dashboard API, [#351][]
* [OTHER] Support `tox` for testing, [#342][]
* [OTHER] Support Python 3.7, **drop support for Python 3.3**, [#345][]

# 0.26.0 / 2018-11-29

* [IMPROVEMENT] API: Keep HTTP connections alive when using `requests`, [#328][]

# 0.25.0 / 2018-11-27

* [FEATURE] ThreadStats: Add AWS Lambda wrapper, [#324][]

# 0.24.0 / 2018-11-12

* [BUGFIX] DogStatsD: Do not send empty UDP packets, [#264][] (thanks [@Tenzer][])
* [FEATURE] API: Add support for distributions, [#312][]
* [FEATURE] ThreadStats: Add support for distributions, [#312][]
* [OTHER] Remove `simplejson` 3p dependency, [#304][], [#309][] (thanks [@alexpjohnson][])

# 0.23.0 / 2018-10-18

* [BUGFIX] Dogshell: Submit `--date_happened` timestamp when posting events, [#287][], [#301][] (thanks [@gplasky][])
* [FEATURE] API: Add [search](https://docs.datadoghq.com/api/?lang=python#monitors-search) and [groups search](https://docs.datadoghq.com/api/?lang=python#monitors-group-search) methods to the `Monitor` resource, [#299][]
* [IMPROVEMENT] Dogshell: Set API and APP keys with environment variables, [#228][] (thanks [@taraslayshchuk][])
* [IMPROVEMENT] DogStatsD: Prevent an issue that was causing the `timed` context manager object from overwritting a method with an instance variable, [#263][] (thanks [@florean][])
* [OTHER] Include tests in PyPI tarball, [#259][] (thanks [@dotlambda][])

# 0.22.0 / 2018-06-27

**New API endpoint: https://api.datadoghq.com/api**

The Datadog API client now uses https://api.datadoghq.com/api endpoint instead of https://app.datadoghq.com/api.
See [#257][] for more details.

* [BUGFIX] API: Close requests' sessions to limit memory usage, [#272][] (thanks [@thehesiod][])
* [BUGFIX] Dogwrap: Fix `TypeError` exceptions when truncating `stdout`, `stderr` with Python 3, [#260][], [#267][] (thanks [@cabouffard][], [@glasnt][])
* [FEATURE] DogStatsD: Add client level tags to status checks, [#279][] (thanks [@marshallbrekka][])
* [FEATURE] DogStatsD: Add support for `statsd_socket_path` option in `initialize` function, [#282][]
* [IMPROVEMENT] Dogwrap: Default output encoding to UTF-8, [#268][] (thanks [@glasnt][])

# 0.21.0 / 2018-06-04

**Search hosts: `Infrastructure.search` is deprecated**
The `Infrastructure.search` method is deprecated in favor of the new `Hosts.search` method.

* [BUGFIX] API: Prevent exception contexts from logging URLs and credentials, [#266][]
* [FEATURE] API: Add `search` and `totals` methods to the `Hosts` resource, [#261][]

# 0.20.0 / 2018-03-23
* [FEATURE] API: New `DashboardList` resource, [#252][]

# 0.19.0 / 2018-02-08

**ThreadStats: metric type change**

`ThreadStats` count metrics (produced from the `increment`/`decrement` and `histogram` methods) are now reported with the `count`/`rate` metric type, instead of `gauge`.
As a result, for the corresponding metrics:
1. Metric queries can use the `.as_count()`/ `.as_rate()` functions to switch between count and rate representations.
2. The default time aggregation uses a sum instead of an average. **This may affect the representation of existing metric queries, thus, monitors' definitions and metric graphs.**

See [#242][] (thanks [@nilabhsagar][]) for more details.


* [BUGFIX] ThreadStats: Send count metrics with `Rate` metric type, [#242][] (thanks [@nilabhsagar][])
* [IMPROVEMENT] ThreadStats: Flush all metrics on exit, [#221][]


# 0.18.0 / 2018-01-24
* [BUGFIX] Dogshell: Service checks can be sent with optional parameters set to null values, [#241][] (thanks [@timvisher][])
* [BUGFIX] Dogwrap: Respect the ouput channel encoding format, [#236][] (thanks [@martin308][])
* [FEATURE] DogstatsD: Add beta support for sending global distribution metrics, [#249][]

# 0.17.0 / 2017-11-06
* [BUGFIX] API: Discard non-null parameters in `api.ServiceCheck.check`method, [#206][], [#207][] (thanks [@ronindesign][])
* [BUGFIX] API: Update HTTP method from `GET` to `POST` for `api.Screenboard.share` method, [#234][] (thanks [@seiro-ogasawara][])
* [BUGFIX] Dogwrap: Encode from unicode before writing to stdout, stderr, [#201][], [#203][] (thanks [@ronindesign][])
* [FEATURE] API: Add `list` method to `Metric` resource, [#230][] (thanks [@jbain][])
* [FEATURE] DogStatsD: Add `socket_path` option to enable Unix socket traffic to DogStatsD 6, [#199][]
* [IMPROVEMENT] DogStatsD: Improve performances, speed up payload construction, [#233][] (thanks [@shargan][])

# 0.16.0 / 2017-04-26
* [FEATURE] Dogshell: Add filtering options to the `monitor show_all` command, [#194][]

# 0.15.0 / 2017-01-24
* [FEATURE] API: Add metric metadata endpoints [#181][]
* [IMPROVEMENT] API: Disable redirection following with `urlfetch` HTTP library [#168][] (thanks [@evanj][])
* [IMPROVEMENT] API: Increase default timeout from 3 to 60 seconds [#174][] (thanks [@ojongerius][])
* [IMPROVEMENT] DogStatsD: Better exceptions on system default route resolution failures [#166][], [#156][]
* [IMPROVEMENT] DogStatsD: Close sockets when freed [#167][] (thanks [@thehesiod][])

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
* [FEATURE] API: Add `delete` method to `Event` resource, [#145][]
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
[#6]: https://github.com/Datadog/datadogpy/issues/6
[#7]: https://github.com/Datadog/datadogpy/issues/7
[#8]: https://github.com/Datadog/datadogpy/issues/8
[#9]: https://github.com/Datadog/datadogpy/issues/9
[#30]: https://github.com/Datadog/datadogpy/issues/30
[#34]: https://github.com/Datadog/datadogpy/issues/34
[#36]: https://github.com/Datadog/datadogpy/issues/36
[#39]: https://github.com/Datadog/datadogpy/issues/39
[#41]: https://github.com/Datadog/datadogpy/issues/41
[#42]: https://github.com/Datadog/datadogpy/issues/42
[#43]: https://github.com/Datadog/datadogpy/issues/43
[#45]: https://github.com/Datadog/datadogpy/issues/45
[#46]: https://github.com/Datadog/datadogpy/issues/46
[#47]: https://github.com/Datadog/datadogpy/issues/47
[#51]: https://github.com/Datadog/datadogpy/issues/51
[#53]: https://github.com/Datadog/datadogpy/issues/53
[#57]: https://github.com/Datadog/datadogpy/issues/57
[#58]: https://github.com/Datadog/datadogpy/issues/58
[#59]: https://github.com/Datadog/datadogpy/issues/59
[#60]: https://github.com/Datadog/datadogpy/issues/60
[#62]: https://github.com/Datadog/datadogpy/issues/62
[#63]: https://github.com/Datadog/datadogpy/issues/63
[#64]: https://github.com/Datadog/datadogpy/issues/64
[#65]: https://github.com/Datadog/datadogpy/issues/65
[#67]: https://github.com/Datadog/datadogpy/issues/67
[#68]: https://github.com/Datadog/datadogpy/issues/68
[#70]: https://github.com/Datadog/datadogpy/issues/70
[#71]: https://github.com/Datadog/datadogpy/issues/71
[#76]: https://github.com/Datadog/datadogpy/issues/76
[#77]: https://github.com/Datadog/datadogpy/issues/77
[#78]: https://github.com/Datadog/datadogpy/issues/78
[#83]: https://github.com/Datadog/datadogpy/issues/83
[#87]: https://github.com/Datadog/datadogpy/issues/87
[#89]: https://github.com/Datadog/datadogpy/issues/89
[#90]: https://github.com/Datadog/datadogpy/issues/90
[#92]: https://github.com/Datadog/datadogpy/issues/92
[#94]: https://github.com/Datadog/datadogpy/issues/94
[#96]: https://github.com/Datadog/datadogpy/issues/96
[#101]: https://github.com/Datadog/datadogpy/issues/101
[#103]: https://github.com/Datadog/datadogpy/issues/103
[#104]: https://github.com/Datadog/datadogpy/issues/104
[#105]: https://github.com/Datadog/datadogpy/issues/105
[#106]: https://github.com/Datadog/datadogpy/issues/106
[#110]: https://github.com/Datadog/datadogpy/issues/110
[#111]: https://github.com/Datadog/datadogpy/issues/111
[#114]: https://github.com/Datadog/datadogpy/issues/114
[#117]: https://github.com/Datadog/datadogpy/issues/117
[#118]: https://github.com/Datadog/datadogpy/issues/118
[#119]: https://github.com/Datadog/datadogpy/issues/119
[#120]: https://github.com/Datadog/datadogpy/issues/120
[#122]: https://github.com/Datadog/datadogpy/issues/122
[#123]: https://github.com/Datadog/datadogpy/issues/123
[#124]: https://github.com/Datadog/datadogpy/issues/124
[#126]: https://github.com/Datadog/datadogpy/issues/126
[#132]: https://github.com/Datadog/datadogpy/issues/132
[#134]: https://github.com/Datadog/datadogpy/issues/134
[#140]: https://github.com/Datadog/datadogpy/issues/140
[#143]: https://github.com/Datadog/datadogpy/issues/143
[#145]: https://github.com/Datadog/datadogpy/issues/145
[#146]: https://github.com/Datadog/datadogpy/issues/146
[#147]: https://github.com/Datadog/datadogpy/issues/147
[#151]: https://github.com/Datadog/datadogpy/issues/151
[#152]: https://github.com/Datadog/datadogpy/issues/152
[#154]: https://github.com/Datadog/datadogpy/issues/154
[#155]: https://github.com/Datadog/datadogpy/issues/155
[#156]: https://github.com/Datadog/datadogpy/issues/156
[#161]: https://github.com/Datadog/datadogpy/issues/161
[#166]: https://github.com/Datadog/datadogpy/issues/166
[#167]: https://github.com/Datadog/datadogpy/issues/167
[#168]: https://github.com/Datadog/datadogpy/issues/168
[#174]: https://github.com/Datadog/datadogpy/issues/174
[#175]: https://github.com/Datadog/datadogpy/issues/175
[#176]: https://github.com/Datadog/datadogpy/issues/176
[#178]: https://github.com/Datadog/datadogpy/issues/178
[#181]: https://github.com/Datadog/datadogpy/issues/181
[#184]: https://github.com/Datadog/datadogpy/issues/184
[#185]: https://github.com/Datadog/datadogpy/issues/185
[#194]: https://github.com/Datadog/datadogpy/issues/194
[#199]: https://github.com/Datadog/datadogpy/issues/199
[#201]: https://github.com/Datadog/datadogpy/issues/201
[#203]: https://github.com/Datadog/datadogpy/issues/203
[#206]: https://github.com/Datadog/datadogpy/issues/206
[#207]: https://github.com/Datadog/datadogpy/issues/207
[#212]: https://github.com/Datadog/datadogpy/issues/212
[#221]: https://github.com/Datadog/datadogpy/issues/221
[#223]: https://github.com/Datadog/datadogpy/issues/223
[#228]: https://github.com/Datadog/datadogpy/issues/228
[#230]: https://github.com/Datadog/datadogpy/issues/230
[#233]: https://github.com/Datadog/datadogpy/issues/233
[#234]: https://github.com/Datadog/datadogpy/issues/234
[#236]: https://github.com/Datadog/datadogpy/issues/236
[#241]: https://github.com/Datadog/datadogpy/issues/241
[#242]: https://github.com/Datadog/datadogpy/issues/242
[#249]: https://github.com/Datadog/datadogpy/issues/249
[#252]: https://github.com/Datadog/datadogpy/issues/252
[#257]: https://github.com/Datadog/datadogpy/issues/257
[#259]: https://github.com/Datadog/datadogpy/issues/259
[#260]: https://github.com/Datadog/datadogpy/issues/260
[#261]: https://github.com/Datadog/datadogpy/issues/261
[#263]: https://github.com/Datadog/datadogpy/issues/263
[#264]: https://github.com/Datadog/datadogpy/issues/264
[#266]: https://github.com/Datadog/datadogpy/issues/266
[#267]: https://github.com/Datadog/datadogpy/issues/267
[#268]: https://github.com/Datadog/datadogpy/issues/268
[#272]: https://github.com/Datadog/datadogpy/issues/272
[#279]: https://github.com/Datadog/datadogpy/issues/279
[#282]: https://github.com/Datadog/datadogpy/issues/282
[#287]: https://github.com/Datadog/datadogpy/issues/287
[#299]: https://github.com/Datadog/datadogpy/issues/299
[#301]: https://github.com/Datadog/datadogpy/issues/301
[#304]: https://github.com/Datadog/datadogpy/issues/304
[#309]: https://github.com/Datadog/datadogpy/issues/309
[#312]: https://github.com/Datadog/datadogpy/issues/312
[#322]: https://github.com/Datadog/datadogpy/issues/322
[#324]: https://github.com/Datadog/datadogpy/issues/324
[#328]: https://github.com/Datadog/datadogpy/issues/328
[#342]: https://github.com/Datadog/datadogpy/issues/342
[#345]: https://github.com/Datadog/datadogpy/issues/345
[#346]: https://github.com/Datadog/datadogpy/issues/346
[#349]: https://github.com/Datadog/datadogpy/issues/349
[#351]: https://github.com/Datadog/datadogpy/issues/351
[#353]: https://github.com/Datadog/datadogpy/issues/353
[#356]: https://github.com/Datadog/datadogpy/issues/356
[#359]: https://github.com/Datadog/datadogpy/issues/359
[#362]: https://github.com/Datadog/datadogpy/issues/362
[#363]: https://github.com/Datadog/datadogpy/issues/363
[#364]: https://github.com/Datadog/datadogpy/issues/364
[#368]: https://github.com/Datadog/datadogpy/issues/368
[#370]: https://github.com/Datadog/datadogpy/issues/370
[#373]: https://github.com/Datadog/datadogpy/issues/373
[#374]: https://github.com/Datadog/datadogpy/issues/374
[#376]: https://github.com/Datadog/datadogpy/issues/376
[#378]: https://github.com/Datadog/datadogpy/issues/378
[#379]: https://github.com/Datadog/datadogpy/issues/379
[#381]: https://github.com/Datadog/datadogpy/issues/381
[#382]: https://github.com/Datadog/datadogpy/issues/382
[#383]: https://github.com/Datadog/datadogpy/issues/383
[#385]: https://github.com/Datadog/datadogpy/issues/385
[#386]: https://github.com/Datadog/datadogpy/issues/386
[#387]: https://github.com/Datadog/datadogpy/issues/387
[#388]: https://github.com/Datadog/datadogpy/issues/388
[#397]: https://github.com/Datadog/datadogpy/issues/397
[@GrahamDumpleton]: https://github.com/GrahamDumpleton
[@Hefeweizen]: https://github.com/Hefeweizen
[@Tenzer]: https://github.com/Tenzer
[@TheKevJames]: https://github.com/TheKevJames
[@aknuds1]: https://github.com/aknuds1
[@alexpjohnson]: https://github.com/alexpjohnson
[@aristiden7o]: https://github.com/aristiden7o
[@benweatherman]: https://github.com/benweatherman
[@brendanlong]: https://github.com/brendanlong
[@cabouffard]: https://github.com/cabouffard
[@clokep]: https://github.com/clokep
[@dcrosta]: https://github.com/dcrosta
[@dotlambda]: https://github.com/dotlambda
[@drstevens]: https://github.com/drstevens
[@emad]: https://github.com/emad
[@evanj]: https://github.com/evanj
[@ewdurbin]: https://github.com/ewdurbin
[@fdhoff]: https://github.com/fdhoff
[@florean]: https://github.com/florean
[@g--]: https://github.com/g--
[@glasnt]: https://github.com/glasnt
[@gnarf]: https://github.com/gnarf
[@gordlea]: https://github.com/gordlea
[@gplasky]: https://github.com/gplasky
[@jbain]: https://github.com/jbain
[@jmehnle]: https://github.com/jmehnle
[@jofusa]: https://github.com/jofusa
[@kuzmich]: https://github.com/kuzmich
[@lceS2]: https://github.com/lceS2
[@leozc]: https://github.com/leozc
[@marshallbrekka]: https://github.com/marshallbrekka
[@martin308]: https://github.com/martin308
[@meawoppl]: https://github.com/meawoppl
[@mgood]: https://github.com/mgood
[@miketheman]: https://github.com/miketheman
[@nilabhsagar]: https://github.com/nilabhsagar
[@ogst]: https://github.com/ogst
[@ojongerius]: https://github.com/ojongerius
[@ronindesign]: https://github.com/ronindesign
[@ross]: https://github.com/ross
[@sc68cal]: https://github.com/sc68cal
[@seiro-ogasawara]: https://github.com/seiro-ogasawara
[@shargan]: https://github.com/shargan
[@steven-liu]: https://github.com/steven-liu
[@taraslayshchuk]: https://github.com/taraslayshchuk
[@thehesiod]: https://github.com/thehesiod
[@timed]: https://github.com/timed
[@timvisher]: https://github.com/timvisher
[@tuukkamustonen]: https://github.com/tuukkamustonen
