# Signed Private Registry and Marketplace

## Publisher identity

A tenant registers an Ed25519 public key. zomega validates that the supplied PEM contains an Ed25519
public key before accepting it.

## Manifest canonicalization

Private skill manifests are serialized as sorted compact UTF-8 JSON. Publishers sign those exact
bytes with their Ed25519 private key.

zomega stores:

- canonical manifest content
- SHA-256 content-integrity digest
- Ed25519 signature
- publisher public-key snapshot

The SHA-256 digest is used only for non-secret content integrity; publisher authenticity comes from
Ed25519 signature verification.

## Key rotation

A publisher may rotate the profile key for future versions. Historical private-skill versions retain
the signer public key used when they were published, so old signatures remain independently
verifiable.

## Marketplace purchase

A purchase is serialized by buyer tenant + idempotency key and atomically commits:

1. buyer wallet debit
2. buyer ledger entry
3. publisher wallet revenue-share credit
4. publisher ledger entry
5. marketplace gross/publisher/platform accounting
6. buyer entitlement grant

Buyer and publisher wallet rows are locked in tenant-ID order to reduce cross-purchase deadlock risk.

Platform revenue is accounting data; external fiat payout is intentionally outside the source
baseline and requires a payment/payout provider.
