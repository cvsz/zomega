# Security

- Never commit secrets.
- API keys are HMAC-hashed before storage.
- Paid skills reserve balance before execution.
- Production payment webhooks require canonical provider signature validation.
- test-double payment mode must not be used in production.
- Destructive agent capabilities default to denied.
- Use TLS at ingress.
- Use least privilege and secret manager injection in production.
- Configure rate limits and abuse controls before public launch.
