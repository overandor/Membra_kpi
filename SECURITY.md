# Security Policy

## Reporting

Do not disclose vulnerabilities publicly before coordinated remediation.

Report security issues privately to the maintainers.

## Operational Guidance

- Rotate secrets regularly.
- Do not commit .env files.
- Restrict admin endpoints.
- Use HTTPS in production.
- Store uploads outside the container filesystem when possible.
- Use managed Postgres for scaled deployments.

## Known limitations

- SQLite is not intended for large-scale concurrent workloads.
- Token-only admin auth should be replaced with identity-based authentication.
- Public upload endpoints should eventually include antivirus and MIME verification.
