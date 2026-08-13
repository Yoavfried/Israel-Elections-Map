# Locality Result-Presence Audit

Reviewed snapshot backed by `docs/LOCALITY_RESULT_PRESENCE_AUDIT.csv`,
`docs/LOCALITY_PARTIAL_GAP_AUDIT.csv`,
`data/manual/locality_result_presence_reviews.csv`, the published locality
aggregates, and the official historical locality workbooks.

## Scope and Method

This audit asks whether each 2022 CBS display feature has its own standalone row in each K17-K25 locality-result file. It does not test whether all published election rows are mapped; locality-mode row coverage is independently 100%.

The 1700-1799 special-purpose facilities, 5500-5599 regional-council footprints, and 9900-9999 no-jurisdiction/background footprints are structural display geometry, not candidate election localities, and are excluded from the exception inventory.

The structural exclusion was checked against the official 2022 CBS locality workbook. All 56 special-purpose records have a blank 2022 population; the other 104 features are regional-council or no-jurisdiction footprints rather than locality records. No additional never-result polygon with an expected locality electorate sits outside the 36-row review set.

Partial-presence gaps are checked against the closest official pre-election
CBS locality register: 2005 for K17, 2008 for K18, 2012 for K19, 2014 for K20,
2018 for K21, 2019 for K22-K23, 2020 for K24, and 2022 for K25.

## Review Status

The 36 features with no standalone K17-K25 result have evidence-level
explanations. The 80 partial-presence features create 227 election-specific
missing-result cells. Of those cells, 215 now have a supported historical,
joined-register, or reviewed-display explanation. Seventy-two of the 80
locality histories are fully explained; 12 cells across 8 localities remain
neutral under a closed review policy because no source supports a host.

| Gap classification | Election-specific cells | Treatment |
|---|---:|---|
| source-backed joined register | 138 | host and attached polygons are shown as one election-specific feature |
| locality absent from the election-year CBS locality register | 54 | no independent locality result is expected; no host is invented |
| election-time composite municipality | 16 | the historical municipality's component polygons are unioned |
| reviewed hidden tribal/component footprint | 7 | represented by the reviewed aggregate geography instead |
| CBS locality with population, but no supported result host | 7 | closed; polygon remains neutral |
| CBS place record without independent population | 3 | closed; no electorate or host is asserted |
| CBS record without a population value | 2 | closed; no electorate or host is asserted |
| **Total** | **227** | |

The 12 closed-neutral cells are:

- K17: מכחול (`1343`), תרבין א-צאנע (`1346`), and ביר הדאג' (`1348`);
- K18: מכחול (`1343`) and כחלה (`1367`);
- K21-K24: שבי דרום (`1377`);
- K24: עמיחי (`3824`);
- K25: כפר הנוער הדתי (`890`) and נווה אבות (`926`).

The K17 records are classified as places without an independent population in
the official 2005 locality workbook. The two K18 records have no usable
population value. Shavei Darom has no separate polling row before K25, and
Amihai is absent from both the K24 result and polling-place rows. The K25
polling report lists 45 registered voters for Kfar HaNoar HaDati and 18 for
Neve Avot, but the result file contains neither locality. Exact arithmetic
produces multiple unrelated coincidental host deltas, so no host is accepted.

A joined polling area cannot be split back into locality-specific party totals. The published host row contains one secret-ballot aggregate for the host and every attached register, so moving the whole result to an attached locality would be incorrect.

For `כפר עבודה` and `צופייה`, youth-institution context makes the absence of an
adult locality register unsurprising. `ידידה` is an adult residential
institution: its absence from every available ordinary ballot list is
confirmed, but whether its residents remain registered elsewhere is not
established by the election sources.

## Election-Specific Joined Polygons

The locality map substitutes reviewed host-plus-attached polygon unions only in elections supported by the source evidence. The canonical locality-result CSV remains under the published host locality; the web bundle aliases that one result to the combined display feature without copying or splitting votes. The visible title remains the published host locality, while an info tooltip lists every attached 2022 polygon represented by the union. Historical source registers without a 2022 polygon cannot add geometry and remain documented only in the source evidence.

| Election | Combined polygons | Attached 2022 polygons | Evidence |
|---|---|---|---|
| K17 | 45 | 49 | official polling rows, strict backward register continuity, or historical membership |
| K18 | 44 | 49 | explicit official polling-register attachments, register continuity, or historical membership |
| K19 | 47 | 54 | exact host-level arithmetic or historical membership |
| K20 | 46 | 51 | official polling rows or historical membership |
| K21 | 9 | 11 | combined-register or strictly bracketed continuity |
| K22 | 10 | 11 | combined-register or strictly bracketed continuity |
| K23 | 10 | 11 | combined-register or strictly bracketed continuity |
| K24 | 7 | 8 | combined-register or strictly bracketed continuity |
| K25 | 8 | 9 | exact arithmetic, register continuity, or reviewed under-100 host-delta inference |

`scripts/audit_joined_locality_continuity.py` makes this election-specific
review reproducible. Of 175 continuity leads, 38 pass strict direct or bounded
continuity rules and 137 are already covered, contradicted, or insufficient.
The machine-readable evidence remains under `data/processed/audits/`; no
address geocoding or ballot-to-area reassignment is involved.

Across elections, 33 of the 36 never-present meaningful polygons participate in at least one supported host union; the other 3 are the institution/place cases with no ordinary polling-list row. The unions also include 51 of the 80 partial-presence polygons where the source identifies their host, including Ganei Modi'in with Modi'in Illit in K17-K20.

The election-year CBS locality registers explain later-established localities
without guessing a host, while source polling rows and cross-election register
continuity support the explicit unions. The 12 cells listed above remain
without a supported host, but their neutral treatment is final unless explicit
new source evidence appears.

## Counts

| Feature class | Count |
|---|---|
| All 2022 metadata features | 1387 |
| Structural display features excluded | 160 |
| Meaningful features with results in all 9 elections | 1111 |
| Meaningful features with results in some elections | 80 |
| Meaningful features with no standalone result | 36 |

No-standalone-result explanation breakdown:

| Explanation | Count |
|---|---|
| K19 joined register; exact eligible-voter arithmetic | 28 |
| attached row is explicitly located at the host | 2 |
| under-100 register; host strongly inferred | 3 |
| no ordinary voter-list row in available K17-K25 sources | 3 |

Review confidence:

| Status | Count |
|---|---|
| confirmed | 31 |
| strong inference | 5 |

Structural breakdown:

| Structural class | Count |
|---|---|
| special-purpose facilities | 56 |
| regional-council footprints | 48 |
| no-jurisdiction/background footprints | 56 |

## West Bank Review Set

These are the 2022 localities in the West Bank code range that lack a standalone result in at least one election. `אבנת` and `מבואות יריחו` are already reviewed as hidden for K17-K25; the other missing-election cases remain visible until explicitly reviewed.

| Code | 2022 name | Results present | Missing | Reviewed display rule |
|---|---|---|---|---|
| 3620 | נערן | K17-K21 | K22-K25 | K17-K21: Hebrew name=נירן, English name=NIRAN |
| 3646 | חמדת | K21-K25 | K17-K20 | none |
| 3720 | שערי תקווה | K17-K24 | K25 | none |
| 3724 | נגוהות | K20-K25 | K17-K19 | none |
| 3744 | ברוכין | K19-K25 | K17-K18 | none |
| 3777 | סנסנה | K17, K20-K25 | K18-K19 | none |
| 3778 | עץ אפרים | K17-K24 | K25 | none |
| 3782 | רותם | K24-K25 | K17-K23 | none |
| 3785 | משכיות | K22-K25 | K17-K21 | none |
| 3786 | אבנת | none | K17-K25 | K17-K25: hidden |
| 3822 | רחלים | K20-K25 | K17-K19 | none |
| 3823 | גני מודיעין | K21-K25 | K17-K20 | K17-K20: joined to מודיעין עילית (`3797`) |
| 3824 | עמיחי | K21-K23, K25 | K17-K20, K24 | none |
| 3825 | מבואות יריחו | none | K17-K25 | K17-K25: hidden |

## No Standalone Result in K17-K25

The CBS form and population values are a reviewed 2022 snapshot from the
official locality workbook. `place` is a CBS location that is not counted as an
independent locality population. Exact joins are validated against the archived
K19 ballot list and published K19 eligible-voter totals; strong inferences use
explicit attached-row evidence or an under-100 K25 register plus the nearby
host delta.

| Code | 2022 display name | CBS form / population | Explanation | Evidence | Joined host | Confidence |
|---|---|---|---|---|---|---|
| 88 | כרם בן שמן | other rural Jewish / 96 | K19 joined register; exact eligible-voter arithmetic | K19: 62 eligible | בן שמן (כפר נוער) (1084), station 1 | confirmed |
| 328 | עזוז | community settlement / 86 | K19 joined register; exact eligible-voter arithmetic | K19: 42 eligible | ניצני סיני (1280), station 1 | confirmed |
| 371 | כדורי | institutional Jewish / 209 | K19 joined register; exact eligible-voter arithmetic | K19: 60 eligible | כפר תבור (47), station 2 | confirmed |
| 392 | קדמה | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 31 eligible | ניר בנים (553), station 1 | confirmed |
| 412 | קריית שלמה | institutional Jewish / 374 | K19 joined register; exact eligible-voter arithmetic | K19: 9 eligible | חרוצים (1024), station 1 | confirmed |
| 493 | דייר ראפאת | institutional non-Jewish / 97 | K19 joined register; exact eligible-voter arithmetic | K19: 40 eligible | צרעה (567), station 1 | confirmed |
| 566 | גבעת שמש | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 15 eligible | צרעה (567), station 1 | confirmed |
| 875 | כפר עבודה | institutional Jewish / 204 | no ordinary voter-list row in available K17-K25 sources | K17-K25: no ordinary polling-list row | none | confirmed |
| 882 | אורנים | institutional Jewish / 116 | K19 joined register; exact eligible-voter arithmetic | K19: 6 eligible | קריית טבעון (2300), station 8 | confirmed |
| 886 | איתנים | institutional Jewish / 61 | K19 joined register; exact eligible-voter arithmetic | K19: 6 eligible | צובה (465), station 1 | confirmed |
| 897 | מדרשת רופין | institutional Jewish / 281 | K19 joined register; exact eligible-voter arithmetic | K19: 8 eligible | כפר מונש (387), station 1 | confirmed |
| 1053 | עין חצבה | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 25 eligible | חצבה (13), station 1 | confirmed |
| 1056 | עין כרם-בי"ס חקלאי | institutional Jewish / 175 | K19 joined register; exact eligible-voter arithmetic | K19: 18 eligible | ירושלים (3000), station 322 | confirmed |
| 1076 | בית ברל | institutional Jewish / 268 | K19 joined register; exact eligible-voter arithmetic | K19: 52 eligible | צופית (198), station 2 | confirmed |
| 1111 | צופייה | place / not separate | no ordinary voter-list row in available K17-K25 sources | K17-K25: no ordinary polling-list row | none | confirmed |
| 1117 | יעל | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 20 eligible | פרזון (2053), station 1 | confirmed |
| 1144 | ידידה | institutional Jewish / 222 | no ordinary voter-list row in available K17-K25 sources | K17-K25: no ordinary polling-list row | none | confirmed |
| 1154 | מלכישוע | institutional Jewish / 188 | K19 joined register; exact eligible-voter arithmetic | K19: 6 eligible | בית שאן (9200), station 17 | confirmed |
| 1187 | עיר אובות | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 16 eligible | חצבה (13), station 1 | confirmed |
| 1196 | מחנה יתיר | other rural Jewish / 306 | K19 joined register; exact eligible-voter arithmetic | K19: 44 eligible | הר עמשא (1261), station 1 | confirmed |
| 1225 | רביד | kibbutz / 108 | K19 joined register; exact eligible-voter arithmetic | K19: 99 eligible | מסד (1258), station 1 | confirmed |
| 1267 | שיטים | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 5 eligible | נאות סמדר (1197), station 1 | confirmed |
| 1276 | אשבל | kibbutz / 141 | K19 joined register; exact eligible-voter arithmetic | K19: 66 eligible | אשחר (1188), station 1 | confirmed |
| 1279 | נווה חריף | kibbutz / 111 | K19 joined register; exact eligible-voter arithmetic | K19: 81 eligible | נאות סמדר (1197), station 1 | confirmed |
| 1318 | מבואות ים | institutional Jewish / 445 | K19 joined register; exact eligible-voter arithmetic | K19: 27 eligible | מכמורת (382), station 1 | confirmed |
| 1322 | הודיות | institutional Jewish / 329 | K19 joined register; exact eligible-voter arithmetic | K19: 33 eligible | לביא (585), station 1 | confirmed |
| 1325 | כפר זוהרים | institutional Jewish / 155 | attached row is explicitly located at the host | K20\|K25: source row names host | שריגים (לי-און) (1114), station 1 | strong |
| 1339 | אל -עזי | other rural non-Jewish / 200 | K19 joined register; exact eligible-voter arithmetic | K19: 72 eligible | כפר מנחם (274), station 1 | confirmed |
| 1341 | רוח מדבר | institutional Jewish / 57 | attached row is explicitly located at the host | K20: source row names host | טללים (1177), station 1 | strong |
| 1373 | שלווה במדבר | place / not separate | K19 joined register; exact eligible-voter arithmetic | K19: 7 eligible | מדרשת בן גוריון (1140), station 1 | confirmed |
| 1378 | שיזף | community settlement / 130 | under-100 register; host strongly inferred | K25: 45 eligible | טללים (1177), station 1 | strong |
| 2006 | כנות | institutional Jewish / 364 | K19 joined register; exact eligible-voter arithmetic | K19: 41 eligible | נווה מבטח (827), station 1 | confirmed |
| 2039 | קריית יערים (מוסד) | institutional Jewish / 175 | K19 joined register; exact eligible-voter arithmetic | K19: 23 eligible | קריית יערים (1137), station 2 | confirmed |
| 3786 | אבנת | community settlement / 249 | K19 joined register; exact eligible-voter arithmetic | K19: 36 eligible | קליה (3601), station 1 | confirmed |
| 3825 | מבואות יריחו | community settlement / 308 | under-100 register; host strongly inferred | K25: 81 eligible | ייט"ב (3607), station 1 | strong |
| 4035 | נמרוד | place / not separate | under-100 register; host strongly inferred | K25: 19 eligible | נווה אטי"ב (4303), station 1 | strong |

Detailed arithmetic, source-name discrepancies, and display decisions are retained in `docs/LOCALITY_RESULT_PRESENCE_AUDIT.csv` and `data/manual/locality_result_presence_reviews.csv`.

## Other Partial-Result Localities

| Code | 2022 name | Results present | Missing |
|---|---|---|---|
| 21 | באר אורה | K19-K25 | K17-K18 |
| 212 | בית צבי | K21-K25 | K17-K20 |
| 353 | בית זיד | K19-K25 | K17-K18 |
| 483 | בענה | K19-K25 | K17-K18 |
| 490 | דייר אל-אסד | K19-K25 | K17-K18 |
| 494 | דאלית אל-כרמל | K19-K25 | K17-K18 |
| 516 | מג'ד אל-כרום | K19-K25 | K17-K18 |
| 534 | עספיא | K19-K25 | K17-K18 |
| 628 | ג'ת | K19-K25 | K17-K18 |
| 833 | נורית | K21-K25 | K17-K20 |
| 890 | כפר הנוער הדתי | K17-K19 | K20-K25 |
| 926 | נווה אבות | K17-K18 | K19-K25 |
| 1044 | יעף | K19-K25 | K17-K18 |
| 1057 | נווה זוהר | K17, K19-K25 | K18 |
| 1134 | יד השמונה | K21-K25 | K17-K20 |
| 1143 | נס עמים | K21-K25 | K17-K20 |
| 1153 | כישור | K19-K25 | K17-K18 |
| 1185 | פלך | K24-K25 | K17-K23 |
| 1195 | ניצנה (קהילת חינוך) | K17, K20-K25 | K18-K19 |
| 1198 | כרמים | K19-K25 | K17-K18 |
| 1211 | קדרים | K19-K25 | K17-K18 |
| 1213 | צבעון | K21-K25 | K17-K20 |
| 1239 | חולית | K18-K25 | K17 |
| 1248 | אליפז | K21-K25 | K17-K20 |
| 1251 | עין תמר | K18-K25 | K17 |
| 1257 | חנתון | K18-K25 | K17 |
| 1260 | רתמים | K19-K25 | K17-K18 |
| 1261 | הר עמשא | K19-K25 | K17-K18 |
| 1262 | צוקים | K19-K25 | K17-K18 |
| 1265 | שומרייה | K18-K25 | K17 |
| 1266 | שחרות | K21-K25 | K17-K20 |
| 1278 | באר מילכה | K24-K25 | K17-K23 |
| 1280 | ניצני סיני | K18-K25 | K17 |
| 1291 | כמהין | K19-K25 | K17-K18 |
| 1316 | אל -עריאן | K19-K25 | K17-K18 |
| 1320 | עין חוד | K18-K25 | K17 |
| 1324 | ארסוף | K21-K25 | K17-K20 |
| 1335 | ערב אל נעים | K18-K25 | K17 |
| 1336 | אירוס | K21-K25 | K17-K20 |
| 1338 | כדיתה | K19-K25 | K17-K18 |
| 1340 | מרחב עם | K20-K25 | K17-K19 |
| 1343 | מכחול | K19-K25 | K17-K18 |
| 1344 | גבעות בר | K18-K25 | K17 |
| 1345 | צור יצחק | K18-K25 | K17 |
| 1346 | תרבין א-צאנע (יישוב)* | K19-K25 | K17-K18 |
| 1348 | ביר הדאג' | K18-K25 | K17 |
| 1360 | סעוה | K20-K25 | K17-K19 |
| 1361 | בת חן | K18-K25 | K17 |
| 1363 | בני נצרים | K19-K25 | K17-K18 |
| 1364 | שלומית | K21-K25 | K17-K20 |
| 1365 | אליאב | K21-K25 | K17-K20 |
| 1366 | נווה | K19-K25 | K17-K18 |
| 1367 | כחלה | K21-K25 | K17-K20 |
| 1368 | בני דקלים | K20-K25 | K17-K19 |
| 1369 | נטע | K20-K25 | K17-K19 |
| 1370 | מצפה אילן | K19-K25 | K17-K18 |
| 1371 | גני טל | K20-K25 | K17-K19 |
| 1372 | נצר חזני | K20-K25 | K17-K19 |
| 1374 | כרמי קטיף | K21-K25 | K17-K20 |
| 1375 | אבו תלול | K21-K25 | K17-K20 |
| 1376 | באר גנים | K20-K25 | K17-K19 |
| 1377 | שבי דרום | K25 | K17-K24 |
| 1419 | ניצן ב' | K18-K25 | K17 |
| 4014 | נטור | K19-K25 | K17-K18 |
| 4019 | מיצר | K21-K25 | K17-K20 |
| 4024 | קלע | K18-K25 | K17 |
| 4502 | עין קנייא | K21-K25 | K17-K20 |
| 6000 | באקה אל-גרביה | K19-K25 | K17-K18 |

The feature-level exception inventory is
`docs/LOCALITY_RESULT_PRESENCE_AUDIT.csv`. The 227-row election-specific
classification is `docs/LOCALITY_PARTIAL_GAP_AUDIT.csv`.
