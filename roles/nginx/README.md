# NGINX CIS hardening

Audit and remediate an NGINX installation against the
[CIS NGINX Benchmark](https://www.cisecurity.org/cis-benchmarks) (v3.0.0).
The role assesses each rule and, when enabled, applies the remediation —
installing NGINX from the official repositories (version 1.28.0 or later),
tightening permissions and ownership, configuring TLS, request limits,
logging and browser-security headers. Every rule in the v3 benchmark is
classified Manual by CIS, so the role reports each rule's state and
remediates the ones with concrete prescribed configuration; site-specific
decisions (certificates, IP allowlists, port policy) are reported with the
prescribed steps instead of guessed.

> **Test before you enforce.** Remediation rewrites the NGINX
> configuration and can restart the service. Run in audit-only mode first,
> review the result, and validate on a disposable machine before applying
> to production.

## Supported platforms

Enterprise Linux (CentOS, Red Hat, Rocky, AlmaLinux) and Debian family
(Debian, Ubuntu). The role detects the platform and installs NGINX from
the official nginx.org repository for that platform. It also supports
hardening NGINX inside a container by setting `container: true`.

## Profiles (levels)

Request any combination of role and level through the `levels` variable:

- `web_server_level_1`, `web_server_level_2`
- `load_balancer_level_1`, `load_balancer_level_2`
- `reverse_proxy_level_1`, `reverse_proxy_level_2`

Level 1 is a conservative baseline; level 2 is stricter defense-in-depth.

## Requirements

- A control node with Ansible (see the collection requirements).
- The target runs a supported platform.
- `become` privileges on the target.

## Role variables

```yaml
# Remediation will not be applied unless the audit_only is set to false
audit_only: true

# Benchmark level
# Allowed values are `web_server_level_1`, `web_server_level_2`, `load_balancer_level_1` , `load_balancer_level_2` or 
# `reverse_proxy_level_1` , `reverse_proxy_level_2`
levels:
- web_server_level_2
- load_balancer_level_2
- reverse_proxy_level_2

# Set to true when hardening NGINX inside a container
container: false

# Server configuration

# keepalive_timeout should be between 1 and 10
keepalive_timeout: 10

# send_timeout should be between 1 and 10
send_timeout: 10

# client_body_timeout should be between 1 and 10
client_body_timeout: 10

# client_header_timeout should be between 1 and 10
client_header_timeout: 10

# client_max_body_size, the value can be adjusted depends on the application
client_max_body_size: "100K"

# large_client_header_buffers, the value can be adjusted depends on the application
large_client_header_buffers: "2 1k"

# SSL ciphers configuration.
# When enforce_remediation is set to true, the ssl ciphers will be updated according the value bellow.
# Default is true
ssl_ciphers:
  enforce_remediation: true
  value: ALL:!EXP:!NULL:!ADH:!LOW:!SSLv2:!SSLv3:!MD5:!RC4

# max-age directive with 15768000 seconds (six months) or longer
strict_transport_security_max_age: 15768000

# Security best practices
security_best_practices:
  enable: true
  # Configures X-XSS-Protection
  xss_protection_header: true
  # Hide 'Server' header
  hide_server_header: true
```

## Results

Every rule appends an entry to `audit_result`, which the role prints at the
end of the run — the rule name, whether it is scored and automated, and its
compliance status. Review this report before enabling remediation.

## Usage

The example below hardens an NGINX web server, load balancer and reverse
proxy at level 2:

```yaml
- name: Nginx hardening
  hosts: all # Make sure to select a machine based on your inventory
  become: yes
  gather_facts: yes
  any_errors_fatal: yes
  roles:
  - name: hasnimehdi91.cis_hardening.nginx
    vars:
      audit_only: false
      levels:
      - web_server_level_2
      - load_balancer_level_2
      - reverse_proxy_level_2
```

Set `audit_only: true` for a non-destructive assessment first.
