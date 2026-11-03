import Link from "next/link";

// Set NEXT_PUBLIC_CONTACT_URL (a mailto: or booking link) to turn on the "Talk to us" buttons.
export const CONTACT = process.env.NEXT_PUBLIC_CONTACT_URL || null;

export const Logo = () => (
  <Link href="/" className="logo demo-brand">
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="5" cy="6" r="2.500" /><circle cx="5" cy="18" r="2.500" /><circle cx="19" cy="12" r="2.500" />
      <path d="M7.500 6c6 0 4 6 9 6M7.500 18c6 0 4-6 9-6" />
    </svg>
    ProductOlogy
  </Link>
);
