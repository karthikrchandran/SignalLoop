# Provider callback log redaction

SignalLoop's application logging filter redacts `correlation`, `token`, and
`media_token` query values from Python and Uvicorn log records. Twilio callback
correlation remains in callback URLs because Twilio must return that value, but
application code must never log the generated callback URL.

Reverse proxies, load balancers, CDNs, and observability agents can record a raw
request target before the application filter runs. Their access-log policy must
therefore either omit query strings or redact the same keys. This infrastructure
control is a deployment boundary and must be verified before enabling provider
traffic. Media-stream nonces are sent as TwiML custom parameters, not in the
WebSocket URL.
