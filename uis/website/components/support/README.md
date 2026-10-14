# Public support UI

`SupportChat` is an accessible bilingual site-wide panel with keyboard dismissal, focus return,
country selection independent of language, loading/errors and complete answers. History exists
only in page memory; only bounded answered exchanges are carried as untrusted follow-up context.
Country changes clear the history. Private/action requests receive a contact link.

The launcher measures the footer's visible area and stays above it while scrolling, resizing
or changing page content. Mobile uses a compact icon with the full accessible button name;
desktop retains the text label. Footer links remain unobstructed.

Pure English/Spanish greetings receive an immediate static welcome, with no policy facts or AI
request and no country requirement. Policy queries still require country selection and the
configured backend. A disabled feature reports that answers have not been enabled, rather than
suggesting a transient outage or retry. This does not enable AI or bypass provider/gateway checks.

The same-origin server route authenticates a fixed gateway; no provider key, staff identity or
service secret enters this component. See [rollout](../../../../docs/runbooks/customer-demo.md).
