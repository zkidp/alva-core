# DNS failure attribution and process-local routed continuation

The first authorized continuation stopped at Q01-B before receiving any model
response. The original exception context now establishes
`ProviderFault -> URLError -> gaierror(errno=11001)`: Windows name resolution
failed. This does not establish that the earlier Q01-A failure had the same
cause. Q01-A and Q01-B stay censored and are never retried or replaced.

Ordinary DNS resolution subsequently failed in a no-model diagnostic too.
An explicit public DNS query (`nslookup ... 1.1.1.1`) eventually returned an A
answer after timeouts. An experimental process-local route to that answer then
passed three unauthenticated HTTPS checks and the original two-request toy tool
canary (748 reported tokens). This is a local workaround, not a permanent repair
of Windows DNS. No system DNS, adapter, firewall, proxy or global TLS setting was
changed. DNS lookup discloses only the public provider hostname, not credentials.

The wrapper uses the exact same API URL, Host header, request body, SDK adapter,
model, reasoning and tool loop. Only TCP destination selection avoids repeated
hostname lookups. HTTPSConnection retains `api.deepseek.com` for SNI and normal
certificate/hostname verification. The address is an actual current public DNS
answer, not an alternative provider. No credential is sent in an IP-based URL.
Foreign origins, redirects, nonpublic addresses and existing proxy configurations
fail closed. The process-local answer expires in300 seconds and is never silently
refreshed or extended. Expiry/failure stops the wave; no paid request retries.

DNS-CONTINUATION-FREEZE.json binds actual code bytes, original inputs and current
route hash (address retained only in private runtime config), old archives and
the seven remaining positions before generation. Fresh sessions/workspaces:
Q01-C, Q02-C, Q02-A, Q02-B, Q03-B, Q03-C, Q03-A. Budget, order, public task,
documents, source, tool schemas, Guard and independent tests are unchanged.

Every successful request still passes through the original API once. Diagnostic
telemetry is observational. There are no system changes, TLS bypass, model hints,
hidden-test inputs, task substitutions, budget expansion or new language feature.
Candidate builds/tests remain inside the existing Linux OS boundary.

The first two wave records, freezes, archives and dispositions are preserved.
This seven-slot wave is separately archived. At most Q02/Q03 have complete
A/B/C triples; report these descriptively, with all failures and costs retained.
Q01 remains unpaired. The original nine-slot primary screen cannot be called
complete or passed. Overall scientific spend remains UNKNOWN because the two
earlier submitted attempts lack usage. All six non-scientific canary requests
are separate from scientific totals. No automatic additional wave follows.
