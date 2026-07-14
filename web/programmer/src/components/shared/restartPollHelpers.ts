// Poll-decision helpers for RestartProgressDialog, split out so the cert-error
// heuristic is unit-testable without React.

// Consecutive fetch failures before we consider that the browser might be
// rejecting the new self-signed cert (rather than the server still being down).
export const CERT_ERROR_THRESHOLD = 5;

// ...but only once polling has run long enough that a healthy restart would have
// come back. A normal HTTP->HTTPS restart rebinds within a few seconds; requiring
// this many poll attempts first stops a slow-but-healthy restart (server still
// rebinding, so every fetch throws) from being misread as a cert rejection —
// which would wrongly push the user to install a CA certificate they may not need.
export const CERT_ERROR_MIN_ATTEMPTS = 15;

/**
 * Whether persistent poll failures should be attributed to the browser
 * rejecting the new cert rather than the server still coming up. Requires the
 * page to expect a new cert, enough consecutive failures, AND that polling has
 * run past the window a normal restart needs — so transient port-rebind
 * failures early in the restart don't trip the cert-error state.
 */
export function shouldEnterCertError(
  expectsNewCert: boolean,
  consecutiveFailures: number,
  attempt: number,
): boolean {
  return (
    expectsNewCert &&
    consecutiveFailures >= CERT_ERROR_THRESHOLD &&
    attempt >= CERT_ERROR_MIN_ATTEMPTS
  );
}
