Role Name
=========

This role is to harden NGINX server following the Center of Internet Security CIS v2.0.1 - 06-15-2023

# Variables:

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

# Example:

The example bellow harden NGINX web server, load balancer and reverse proxy with level 2:

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