// Branding lives here — rename the product in one place.
export const PRODUCT = "Tamheed";
export const COMPANY = "Rimal Engineering & Technology";
export const TAGLINE = "A confident start. A future of possibilities.";

export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <rect width="40" height="40" rx="11" fill="var(--brand)" />
      <path d="M9 29h7v-7h7v-7h7" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="30.5" cy="9.5" r="3" fill="var(--gold)" />
    </svg>
  );
}

export function Wordmark({ size = 34 }: { size?: number }) {
  return (
    <div className="wordmark"><Logo size={size} /><span style={{ fontSize: size * 0.62 }}>{PRODUCT}</span></div>
  );
}
