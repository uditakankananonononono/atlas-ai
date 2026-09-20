# Billing and subscriptions

Module 23 exposes Free, Pro, and Team plan metadata and uses Stripe Checkout subscriptions. Every paid checkout begins as a tenant-bound Module 0 approval. The Stripe request uses the approval ID as its idempotency key, and a billing execution row prevents re-use. Webhook events are deduplicated by Stripe event ID. Atlas refuses live Stripe keys in this build; production launch requires a separate reviewed change, verified webhook signatures, and current prices/tax policy.

No route charges a card directly. The returned Stripe-hosted checkout URL is where the account owner reviews and authorizes the subscription.
